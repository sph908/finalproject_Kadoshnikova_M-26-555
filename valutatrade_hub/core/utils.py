import json

from valutatrade_hub.core.currencies import BASE_CURRENCY, get_currency
from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.infra import settings

UPDATE_HINT = "выполните 'update-rates'"


def validate_currency_code(code: str) -> str:
    """
    Проверяет код по справочнику валют и возвращает его в каноническом виде
    """
    return get_currency(code).code


def load_rates() -> dict:
    """
    Читает курсы к базовой валюте из локального кеша rates.json
    """
    try:
        with open(settings.RATES_FILE, encoding="utf-8") as f:
            snapshot = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

    rates = {
        name.partition("_")[0]: data["rate"]
        for name, data in snapshot.get("pairs", {}).items()
    }
    rates[BASE_CURRENCY] = 1.0
    return rates


def get_exchange_rate(from_code: str, to_code: str = BASE_CURRENCY) -> float:
    """
    Возвращает курс одной валюты к другой по сохранённым котировкам
    """
    source = validate_currency_code(from_code)
    target = validate_currency_code(to_code)
    if source == target:
        return 1.0
    rates = load_rates()
    if source not in rates or target not in rates:
        raise ApiRequestError(
            f"нет котировки для пары {source}→{target}, {UPDATE_HINT}"
        )
    return rates[source] / rates[target]


def convert(amount: float, from_code: str, to_code: str = BASE_CURRENCY) -> float:
    """
    Переводит сумму из одной валюты в другую
    """
    return amount * get_exchange_rate(from_code, to_code)
