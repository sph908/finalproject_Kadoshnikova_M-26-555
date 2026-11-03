from datetime import datetime

from valutatrade_hub.core import utils
from valutatrade_hub.core.currencies import BASE_CURRENCY, exchange_rates
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.infra import database, settings

SEPARATOR = "-" * 33


def register(username: str, password: str) -> str:
    """
    Создаёт нового пользователя и пустой портфель для него
    """
    users = utils.load_jsondata(settings.USERS_FILE, [])
    if any(saved["username"] == username for saved in users):
        raise ValueError(f"Имя пользователя '{username}' уже занято")

    user_id = max((saved["user_id"] for saved in users), default=0) + 1
    user = User(user_id, username, "", "", datetime.now())
    user.change_password(password)

    users.append({
        "user_id": user.user_id,
        "username": user.username,
        "hashed_password": user.hashed_password,
        "salt": user.salt,
        "registration_date": user.registration_date.isoformat(),
    })
    utils.save_jsondata(settings.USERS_FILE, users)

    portfolio = Portfolio(user.user_id, {})
    portfolios = utils.load_jsondata(settings.PORTFOLIOS_FILE, [])
    portfolios.append({
        "user_id": portfolio.user,
        "wallets": {
            code: {"balance": wallet.balance}
            for code, wallet in portfolio.wallets.items()
        },
    })
    utils.save_jsondata(settings.PORTFOLIOS_FILE, portfolios)

    return (
        f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}). "
        f"Войдите: login --username {user.username} --password <пароль>"
    )


def login(username: str, password: str) -> User:
    """
    Проверяет пароль и возвращает объект вошедшего пользователя
    """
    users = utils.load_jsondata(settings.USERS_FILE, [])
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
    base = (base_currency or BASE_CURRENCY).strip().upper()
    if base not in exchange_rates:
        raise ValueError(f"Неизвестная базовая валюта '{base_currency}'")

    portfolio = database.load_portfolio(user.user_id)
    if not portfolio.wallets:
        return f"Портфель пользователя '{user.username}' пуст"

    lines = [f"Портфель пользователя '{user.username}' (база: {base}):"]
    for code, wallet in portfolio.wallets.items():
        if code not in exchange_rates:
            raise ValueError(f"Неизвестен курс валюты {code}")
        value = wallet.balance * exchange_rates[code] / exchange_rates[base]
        balance = (
            f"{wallet.balance:,.4f}"
            if 0 < wallet.balance < 1
            else f"{wallet.balance:,.2f}"
        )
        lines.append(f"- {code}: {balance} → {value:,.2f} {base}")
    lines.append(SEPARATOR)
    lines.append(f"ИТОГО: {portfolio.get_total_value(base):,.2f} {base}")
    return "\n".join(lines)


def buy(user: User, currency_code: str, amount: float) -> str:
    """
    Покупает валюту и зачисляет её на кошелёк пользователя
    """
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")

    code = currency_code.strip().upper()
    if code not in exchange_rates:
        raise ValueError(
            f"Не удалось получить курс для {code}→{BASE_CURRENCY}"
        )
    rate = exchange_rates[code] / exchange_rates[BASE_CURRENCY]

    portfolio = database.load_portfolio(user.user_id)
    if code not in portfolio.wallets:
        portfolio.add_currency(code)
    wallet = portfolio.get_wallet(code)

    before = wallet.balance
    wallet.deposit(amount)
    database.save_portfolio(portfolio)

    return "\n".join([
        f"Покупка выполнена: {amount:,.4f} {code} по курсу "
        f"{rate:.2f} {BASE_CURRENCY}/{code}",
        "Изменения в портфеле:",
        f"- {code}: было {before:,.4f} → стало {wallet.balance:,.4f}",
        f"Оценочная стоимость покупки: {amount * rate:,.2f} {BASE_CURRENCY}",
    ])

def sell(user: User, currency_code: str, amount: float) -> str:
    """
    Продаёт валюту и списывает её с кошелька пользователя
    """
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")

    code = currency_code.strip().upper()
    if code not in exchange_rates:
        raise ValueError(
            f"Не удалось получить курс для {code}→{BASE_CURRENCY}"
        )
    rate = exchange_rates[code] / exchange_rates[BASE_CURRENCY]

    portfolio = database.load_portfolio(user.user_id)
    if code not in portfolio.wallets:
        raise ValueError(
            f"У вас нет кошелька '{code}'. Добавьте валюту: "
            f"она создаётся автоматически при первой покупке"
        )

    wallet = portfolio.get_wallet(code)
    if amount > wallet.balance:
        raise ValueError(
            f"Недостаточно средств: доступно {wallet.balance:,.4f} {code}, "
            f"требуется {amount:,.4f} {code}"
        )

    before = wallet.balance
    wallet.withdraw(amount)
    database.save_portfolio(portfolio)

    return "\n".join([
        f"Продажа выполнена: {amount:,.4f} {code} по курсу "
        f"{rate:.2f} {BASE_CURRENCY}/{code}",
        "Изменения в портфеле:",
        f"- {code}: было {before:,.4f} → стало {wallet.balance:,.4f}",
        f"Оценочная выручка: {amount * rate:,.2f} {BASE_CURRENCY}",
    ])

def format_rate(rate: float) -> str:
    """
    Печатает курс: мелкие значения с восемью знаками, остальные с двумя
    """
    if 0 < rate < 1:
        return f"{rate:.8f}"
    return f"{rate:.2f}"


def get_rate(from_currency: str, to_currency: str) -> str:
    """
    Возвращает курс одной валюты к другой с отметкой времени обновления
    """
    source = from_currency.strip().upper()
    target = to_currency.strip().upper()
    if not source or not target:
        raise ValueError("Коды валют не должны быть пустыми")

    cached = database.load_cached_rate(source, target)
    if cached is None:
        if source not in exchange_rates or target not in exchange_rates:
            raise ValueError(
                f"Курс {source}→{target} недоступен. Повторите попытку позже."
            )
        rate = exchange_rates[source] / exchange_rates[target]
        updated_at = datetime.now()
        database.save_cached_rate(source, target, rate, updated_at)
    else:
        rate, updated_at = cached

    moment = updated_at.isoformat(sep=" ", timespec="seconds")
    return "\n".join([
        f"Курс {source}→{target}: {format_rate(rate)} (обновлено: {moment})",
        f"Обратный курс {target}→{source}: {format_rate(1 / rate)}",
    ])
