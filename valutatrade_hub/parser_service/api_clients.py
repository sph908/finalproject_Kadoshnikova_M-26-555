from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import CONFIG, ParserConfig

HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_TOO_MANY_REQUESTS = 429


class BaseApiClient(ABC):
    """
    Общий интерфейс клиента внешнего сервиса курсов
    """

    source: str

    def __init__(self, config: ParserConfig = CONFIG) -> None:
        """
        Сохраняет настройки запросов
        """
        self.config = config

    @abstractmethod
    def fetch_rates(self) -> dict:
        """
        Запрашивает курсы от базовой валюты и приводит их к общему виду
        """

    def _get_json(self, url: str) -> dict:
        """
        Делает GET-запрос и разбирает ответ, переводя сбои в ApiRequestError
        """
        try:
            response = requests.get(url, timeout=self.config.REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as error:
            raise ApiRequestError(
                f"{self.source} недоступен ({type(error).__name__})"
            ) from error

        if response.status_code in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN):
            raise ApiRequestError(
                f"{self.source}: ключ отклонён, код {response.status_code}"
            )
        if response.status_code == HTTP_TOO_MANY_REQUESTS:
            raise ApiRequestError(
                f"{self.source}: исчерпан лимит запросов, код 429"
            )
        if response.status_code != HTTP_OK:
            raise ApiRequestError(
                f"{self.source} ответил кодом {response.status_code}"
            )

        try:
            payload = response.json()
        except ValueError as error:
            raise ApiRequestError(f"{self.source}: ответ не разобрать") from error

        if not isinstance(payload, dict):
            raise ApiRequestError(f"{self.source}: в ответе нет словаря с курсами")
        return payload


class CoinGeckoClient(BaseApiClient):
    """
    Клиент CoinGecko, отвечает за криптовалюты
    """

    source = "CoinGecko"

    def fetch_rates(self) -> dict:
        """
        Запрашивает цены крипотвалюты и приводит их к общему виду
        """
        base = self.config.BASE_FIAT_CURRENCY
        payload = self._get_json(self.config.crypto_url())

        rates = {}
        for code in self.config.CRYPTO_CURRENCIES:
            quote = payload.get(self.config.CRYPTO_ID_MAP[code])
            if not isinstance(quote, dict):
                continue
            price = quote.get(base.lower())
            if isinstance(price, (int, float)) and price > 0:
                rates[f"{code}_{base}"] = float(price)

        if not rates:
            raise ApiRequestError(f"{self.source} не вернул ни одного курса")
        return rates


class ExchangeRateApiClient(BaseApiClient):
    """
    Клиент ExchangeRate-API, отвечает за фиатные валюты
    """

    source = "ExchangeRate-API"

    def fetch_rates(self) -> dict:
        """
        Запрашивает курсы от базовой валюты и переворачивает их к базовой
        """
        if not self.config.EXCHANGERATE_API_KEY:
            raise ApiRequestError(
                f"{self.source}: ключ не задан, проверьте файл .env"
            )

        base = self.config.BASE_FIAT_CURRENCY
        payload = self._get_json(self.config.fiat_url())
        if payload.get("result") != "success":
            reason = payload.get("error-type", "ответ без признака успеха")
            raise ApiRequestError(f"{self.source}: {reason}")

        quotes = payload.get("conversion_rates") or payload.get("rates", {})
        rates = {}
        for code in self.config.FIAT_CURRENCIES:
            price = quotes.get(code)
            if isinstance(price, (int, float)) and price > 0:
                rates[f"{code}_{base}"] = 1 / float(price)

        if not rates:
            raise ApiRequestError(f"{self.source} не вернул ни одного курса")
        return rates
