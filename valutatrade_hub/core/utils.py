from valutatrade_hub.core.currencies import BASE_CURRENCY, exchange_rates, get_currency
from valutatrade_hub.core.exceptions import ApiRequestError


def validate_currency_code(code: str) -> str:
    """
    Проверяет код по справочнику валют и возвращает его в каноническом виде
    """
    return get_currency(code).code


def get_exchange_rate(from_code: str, to_code: str = BASE_CURRENCY) -> float:
    """
    Возвращает курс одной валюты к другой по таблице котировок
    """
    source = validate_currency_code(from_code)
    target = validate_currency_code(to_code)
    if source not in exchange_rates or target not in exchange_rates:
        raise ApiRequestError(f"нет котировки для пары {source}→{target}")
    return exchange_rates[source] / exchange_rates[target]


def convert(amount: float, from_code: str, to_code: str = BASE_CURRENCY) -> float:
    """
    Переводит сумму из одной валюты в другую
    """
    return amount * get_exchange_rate(from_code, to_code)
