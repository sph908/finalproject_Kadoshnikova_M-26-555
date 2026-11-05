from datetime import datetime

from prettytable import PrettyTable

from valutatrade_hub.core import utils
from valutatrade_hub.core.currencies import (
    BASE_CURRENCY,
    CURRENCIES,
    CryptoCurrency,
)
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    InsufficientFundsError,
)
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra import settings
from valutatrade_hub.infra.database import DATABASE
from valutatrade_hub.parser_service.updater import RatesUpdater

CURRENCY_COLUMN = "Валюта"
BALANCE_COLUMN = "Баланс"
PAIR_COLUMN = "Пара"
SOURCE_COLUMN = "Источник"
UNKNOWN_SOURCE = "—"
CACHE_EMPTY = (
    "Локальный кеш курсов пуст. "
    "Выполните 'update-rates', чтобы загрузить данные."
)


@log_action("REGISTER")
def register(username: str, password: str) -> str:
    """
    Создает нового пользователя и пустой портфель для него
    """
    users = DATABASE.load_users()
    if any(saved["username"] == username for saved in users):
        raise ValueError(f"Имя пользователя '{username}' уже занято")

    user_id = max((saved["user_id"] for saved in users), default=0) + 1
    user = User(user_id, username, "", "", datetime.now())
    user.change_password(password)

    DATABASE.save_user({
        **user.get_user_info(),
        "hashed_password": user.hashed_password,
        "salt": user.salt,
    })
    DATABASE.save_portfolio(Portfolio(user.user_id, {}))

    return (
        f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}). "
        f"Войдите: login --username {user.username} --password <пароль>"
    )


@log_action("LOGIN")
def login(username: str, password: str) -> User:
    """
    Проверяет пароль и возвращает объект вошедшего пользователя
    """
    users = DATABASE.load_users()
    saved = next((s for s in users if s["username"] == username), None)
    if saved is None:
        raise ValueError(f"Пользователь '{username}' не найден")

    user = User(
        saved["user_id"],
        saved["username"],
        saved["hashed_password"],
        saved["salt"],
        datetime.fromisoformat(saved["registration_date"]),
    )
    if not user.verify_password(password):
        raise ValueError("Неверный пароль")

    return user


def show_portfolio(user: User, base_currency: str | None = None) -> str:
    """
    Возвращает отчет по кошелькам пользователя в указанной базовой валюте
    """
    base = utils.validate_currency_code(
        base_currency or settings.SETTINGS.get("base_currency")
    )

    portfolio = DATABASE.load_portfolio(user.user_id)
    if not portfolio.wallets:
        return f"Портфель пользователя '{user.username}' пуст"

    value_column = f"Оценка в {base}"
    table = PrettyTable([CURRENCY_COLUMN, BALANCE_COLUMN, value_column])
    table.align[CURRENCY_COLUMN] = "l"
    table.align[BALANCE_COLUMN] = "r"
    table.align[value_column] = "r"
    for wallet in portfolio.wallets.values():
        info = wallet.get_balance_info()
        balance = (
            f"{info['balance']:,.4f}"
            if 0 < info["balance"] < 1
            else f"{info['balance']:,.2f}"
        )
        value = utils.convert(info["balance"], info["currency"], base)
        table.add_row([info["currency"], balance, f"{value:,.2f}"])

    return "\n".join([
        f"Портфель пользователя '{user.username}' (база: {base}):",
        str(table),
        f"ИТОГО: {portfolio.get_total_value(base):,.2f} {base}",
    ])


@log_action("BUY", verbose=True)
def buy(user: User, currency_code: str, amount: float) -> str:
    """
    Покупает валюту и зачисляет ее на кошелек пользователя
    """
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")

    code = utils.validate_currency_code(currency_code)
    rate = utils.get_exchange_rate(code)

    portfolio = DATABASE.load_portfolio(user.user_id)
    if code not in portfolio.wallets:
        portfolio.add_currency(code)
    wallet = portfolio.get_wallet(code)

    before = wallet.balance
    wallet.deposit(amount)
    DATABASE.save_portfolio(portfolio)

    return "\n".join([
        f"Покупка выполнена: {amount:,.4f} {code} по курсу "
        f"{rate:.2f} {BASE_CURRENCY}/{code}",
        "Изменения в портфеле:",
        f"- {code}: было {before:,.4f} → стало {wallet.balance:,.4f}",
        f"Оценочная стоимость покупки: {amount * rate:,.2f} {BASE_CURRENCY}",
    ])


@log_action("SELL", verbose=True)
def sell(user: User, currency_code: str, amount: float) -> str:
    """
    Продает валюту и списывает ее с кошелька пользователя
    """
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")

    code = utils.validate_currency_code(currency_code)
    rate = utils.get_exchange_rate(code)

    portfolio = DATABASE.load_portfolio(user.user_id)
    if code not in portfolio.wallets:
        raise InsufficientFundsError(code, 0.0, amount)

    wallet = portfolio.get_wallet(code)
    before = wallet.balance
    wallet.withdraw(amount)
    DATABASE.save_portfolio(portfolio)

    return "\n".join([
        f"Продажа выполнена: {amount:,.4f} {code} по курсу "
        f"{rate:.2f} {BASE_CURRENCY}/{code}",
        "Изменения в портфеле:",
        f"- {code}: было {before:,.4f} → стало {wallet.balance:,.4f}",
        f"Оценочная выручка: {amount * rate:,.2f} {BASE_CURRENCY}",
    ])


def format_rate(rate: float) -> str:
    """
    Печатает курс
    """
    if 0 < rate < 1:
        return f"{rate:.8f}"
    return f"{rate:.2f}"


def show_rates(
    currency: str | None = None,
    top: int | None = None,
    base: str | None = None,
) -> str:
    """
    Показывает курсы из локального кеша с отбором по валюте, базе или топу
    """
    snapshot = DATABASE.load_snapshot()
    pairs = snapshot.get("pairs", {})
    if not pairs:
        raise ValueError(CACHE_EMPTY)

    quotes = {}
    sources = {}
    for name, data in pairs.items():
        code = name.partition("_")[0]
        quotes[code] = data["rate"]
        sources[code] = data["source"]

    target = utils.validate_currency_code(base) if base else BASE_CURRENCY
    divisor = 1.0
    if target != BASE_CURRENCY:
        if target not in quotes:
            raise ValueError(f"Курс для '{target}' не найден в кеше")
        divisor = quotes[target]
        quotes[BASE_CURRENCY] = 1.0
        sources.setdefault(BASE_CURRENCY, UNKNOWN_SOURCE)

    if currency is not None:
        code = utils.validate_currency_code(currency)
        if code not in quotes:
            raise ValueError(f"Курс для '{code}' не найден в кеше")
        selected = [code]
    elif top is not None:
        crypto = [
            code for code in quotes
            if isinstance(CURRENCIES[code], CryptoCurrency)
        ]
        selected = sorted(crypto, key=lambda code: quotes[code], reverse=True)[:top]
    else:
        selected = sorted(code for code in quotes if code != target)

    rate_column = f"Курс в {target}"
    table = PrettyTable([PAIR_COLUMN, rate_column, SOURCE_COLUMN])
    table.align[PAIR_COLUMN] = "l"
    table.align[rate_column] = "r"
    table.align[SOURCE_COLUMN] = "l"
    for code in selected:
        table.add_row([
            f"{code}_{target}",
            format_rate(quotes[code] / divisor),
            sources.get(code, UNKNOWN_SOURCE),
        ])

    moment = snapshot.get("last_refresh", "неизвестно")
    return f"Курсы из кеша (обновлено: {moment}):\n{table}"


def get_rate(from_currency: str, to_currency: str) -> str:
    """
    Возвращает курс одной валюты к другой с отметкой времени обновления
    """
    source = utils.validate_currency_code(from_currency)
    target = utils.validate_currency_code(to_currency)

    cached = DATABASE.load_cached_rate(source, target)
    if cached is None:
        RatesUpdater().run_update()
        cached = DATABASE.load_cached_rate(source, target)
    if cached is None:
        raise ApiRequestError(f"нет котировки для пары {source}→{target}")

    rate, moment = cached

    return "\n".join([
        f"Курс {source}→{target}: {format_rate(rate)} (обновлено: {moment})",
        f"Обратный курс {target}→{source}: {format_rate(1 / rate)}",
    ])
