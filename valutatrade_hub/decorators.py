from functools import wraps
from inspect import signature

from valutatrade_hub.core import utils
from valutatrade_hub.core.currencies import BASE_CURRENCY
from valutatrade_hub.core.exceptions import ValutatradeError
from valutatrade_hub.infra.database import DATABASE
from valutatrade_hub.logging_config import setup_logging

logger = setup_logging()


def log_action(action: str, verbose: bool = False):
    """
    Записывает в лог вызов функции, ее аргументы и результат
    """
    def decorator(func):
        """
        Оборачивает функцию сценария, не меняя ее поведения
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            """
            Собирает поля, вызывает функцию и записывает итог в журнал
            """
            fields = _collect_fields(func, args, kwargs)
            before = _wallet_balance(fields) if verbose else 0.0

            try:
                result = func(*args, **kwargs)
            except Exception as error:
                logger.info(
                    "%s result=ERROR error_type=%s error_message=%r",
                    _format_fields(action, fields),
                    type(error).__name__,
                    str(error),
                )
                raise

            message = f"{_format_fields(action, fields)} result=OK"
            if verbose:
                after = _wallet_balance(fields)
                message += f" balance={before:.4f}->{after:.4f}"
            logger.info(message)
            return result

        return wrapper

    return decorator


def _collect_fields(func, args: tuple, kwargs: dict) -> dict:
    """
    Сопоставляет аргументы вызова с именами параметров функции
    """
    bound = signature(func).bind(*args, **kwargs)
    bound.apply_defaults()
    values = bound.arguments

    user = values.get("user")
    currency = values.get("currency_code")
    return {
        "user_object": user,
        "user": values.get("username") or (user.username if user else None),
        "currency": currency.strip().upper() if isinstance(currency, str) else None,
        "amount": values.get("amount"),
    }


def _format_fields(action: str, fields: dict) -> str:
    """
    Склеивает заполненные поля в одну строку
    """
    parts = [action]
    if fields["user"] is not None:
        parts.append(f"user={fields['user']!r}")

    currency = fields["currency"]
    if currency is not None:
        parts.append(f"currency={currency!r}")
    if fields["amount"] is not None:
        parts.append(f"amount={fields['amount']:.4f}")

    if currency is not None:
        try:
            rate = utils.get_exchange_rate(currency)
        except ValutatradeError:
            rate = None
        if rate is not None:
            parts.append(f"rate={rate:.2f}")
            parts.append(f"base={BASE_CURRENCY!r}")
    return " ".join(parts)


def _wallet_balance(fields: dict) -> float:
    """
    Читает баланс кошелька из файла портфелей
    """
    user = fields["user_object"]
    currency = fields["currency"]
    if user is None or not isinstance(currency, str):
        return 0.0

    try:
        portfolio = DATABASE.load_portfolio(user.user_id)
        return portfolio.get_wallet(currency).balance
    except ValueError:
        return 0.0
