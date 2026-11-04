from datetime import datetime

from valutatrade_hub.core import utils
from valutatrade_hub.core.currencies import BASE_CURRENCY
from valutatrade_hub.core.exceptions import InsufficientFundsError
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra import settings
from valutatrade_hub.infra.database import DATABASE

SEPARATOR = "-" * 33


@log_action("REGISTER")
def register(username: str, password: str) -> str:
    """
    Создаёт нового пользователя и пустой портфель для него
    """
    users = DATABASE.load_users()
    if any(saved["username"] == username for saved in users):
        raise ValueError(f"Имя пользователя '{username}' уже занято")

    user_id = max((saved["user_id"] for saved in users), default=0) + 1
    user = User(user_id, username, "", "", datetime.now())
    user.change_password(password)

    DATABASE.save_user({
        "user_id": user.user_id,
        "username": user.username,
        "hashed_password": user.hashed_password,
        "salt": user.salt,
        "registration_date": user.registration_date.isoformat(),
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
    Возвращает отчёт по кошелькам пользователя в указанной базовой валюте
    """
    base = utils.validate_currency_code(
        base_currency or settings.SETTINGS.get("base_currency")
    )

    portfolio = DATABASE.load_portfolio(user.user_id)
    if not portfolio.wallets:
        return f"Портфель пользователя '{user.username}' пуст"

    lines = [f"Портфель пользователя '{user.username}' (база: {base}):"]
    for code, wallet in portfolio.wallets.items():
        value = utils.convert(wallet.balance, code, base)
        balance = (
            f"{wallet.balance:,.4f}"
            if 0 < wallet.balance < 1
            else f"{wallet.balance:,.2f}"
        )
        lines.append(f"- {code}: {balance} → {value:,.2f} {base}")
    lines.append(SEPARATOR)
    lines.append(f"ИТОГО: {portfolio.get_total_value(base):,.2f} {base}")
    return "\n".join(lines)


@log_action("BUY", verbose=True)
def buy(user: User, currency_code: str, amount: float) -> str:
    """
    Покупает валюту и зачисляет её на кошелёк пользователя
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
    Продаёт валюту и списывает её с кошелька пользователя
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


def get_rate(from_currency: str, to_currency: str) -> str:
    """
    Возвращает курс одной валюты к другой с отметкой времени обновления
    """
    source = utils.validate_currency_code(from_currency)
    target = utils.validate_currency_code(to_currency)

    cached = DATABASE.load_cached_rate(source, target)
    if cached is None:
        rate = utils.get_exchange_rate(source, target)
        updated_at = datetime.now()
        DATABASE.save_cached_rate(source, target, rate, updated_at)
    else:
        rate, updated_at = cached

    moment = updated_at.isoformat(sep=" ", timespec="seconds")
    return "\n".join([
        f"Курс {source}→{target}: {format_rate(rate)} (обновлено: {moment})",
        f"Обратный курс {target}→{source}: {format_rate(1 / rate)}",
    ])