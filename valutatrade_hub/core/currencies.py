from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError

MIN_CURRENCY_LENGTH = 2
MAX_CURRENCY_LENGTH = 5
BASE_CURRENCY = "USD"


class Currency(ABC):
    """
    Базовый тип валюты, хранит название и код
    """

    def __init__(self, name: str, code: str) -> None:
        """
        Создает валюту, проверяя название и код
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Название валюты не может быть пустым")
        if not isinstance(code, str):
            raise ValueError("Код валюты должен быть строкой")
        if not MIN_CURRENCY_LENGTH <= len(code) <= MAX_CURRENCY_LENGTH:
            raise ValueError(
                f"Код валюты должен содержать от {MIN_CURRENCY_LENGTH} "
                f"до {MAX_CURRENCY_LENGTH} символов"
            )
        if code != code.upper() or not code.isalnum():
            raise ValueError("Код валюты пишется заглавными без пробелов")

        self.name: str = name.strip()
        self.code: str = code

    @abstractmethod
    def get_display_info(self) -> str:
        """
        Возвращает строковое представление валюты для интерфейса и логов
        """


class FiatCurrency(Currency):
    """
    Фиатная валюта с указанием страны
    """

    def __init__(self, name: str, code: str, issuing_country: str) -> None:
        """
        Создает фиатную валюту
        """
        super().__init__(name, code)
        if not isinstance(issuing_country, str) or not issuing_country.strip():
            raise ValueError("Страна эмиссии не может быть пустой")
        self.issuing_country: str = issuing_country.strip()

    def get_display_info(self) -> str:
        """
        Возвращает описание фиатной валюты со страной
        """
        return (
            f"[FIAT] {self.code} — {self.name} "
            f"(Issuing: {self.issuing_country})"
        )


class CryptoCurrency(Currency):
    """
    Криптовалюта с алгоритмом и краткой капитализацией
    """

    def __init__(
        self, name: str, code: str, algorithm: str, market_cap: float
    ) -> None:
        """
        Создает криптовалюту с алгоритмом и капитализацией
        """
        super().__init__(name, code)
        if not isinstance(algorithm, str) or not algorithm.strip():
            raise ValueError("Алгоритм не может быть пустым")
        if isinstance(market_cap, bool) or not isinstance(
            market_cap, (int, float)
        ):
            raise ValueError("Капитализация должна быть числом")
        if market_cap < 0:
            raise ValueError("Капитализация не может быть отрицательной")

        self.algorithm: str = algorithm.strip()
        self.market_cap: float = float(market_cap)

    def get_display_info(self) -> str:
        """
        Возвращает описание криптовалюты с алгоритмом и капитализацией
        """
        market_cap = f"{self.market_cap:.2e}".replace("e+", "e")
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {market_cap})"
        )


CURRENCIES: dict[str, Currency] = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "CNY": FiatCurrency("Chinese Yuan", "CNY", "China"),
    "GBP": FiatCurrency("British Pound", "GBP", "United Kingdom"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 4.2e11),
    "SOL": CryptoCurrency("Solana", "SOL", "Proof of History", 5.0e10),
}


def get_currency(code: str) -> Currency:
    """
    Возвращает валюту по ее коду
    """
    if not isinstance(code, str):
        raise CurrencyNotFoundError(str(code))

    normalized = code.strip().upper()
    if normalized not in CURRENCIES:
        raise CurrencyNotFoundError(code)
    return CURRENCIES[normalized]
