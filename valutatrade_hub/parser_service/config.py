import os
from dataclasses import dataclass, field
from pathlib import Path

from valutatrade_hub.infra import settings

API_KEY_NAME = "EXCHANGERATE_API_KEY"
ENV_FILE = settings.BASE_DIR / ".env"
SECONDS_IN_DAY = 86_400


def read_api_key(name: str = API_KEY_NAME) -> str:
    """
    Берет ключ из переменной окружения, а если ее нет — из файла .env
    """
    key = os.getenv(name)
    if key:
        return key
    if not ENV_FILE.exists():
        return ""

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        stored_name, _, value = line.partition("=")
        if stored_name.strip() == name:
            return value.strip().strip("\"'")
    return ""


@dataclass(frozen=True)
class ParserConfig:
    """
    Настройки сервиса курсов: ключ, адреса, списки валют и ограничения
    """

    EXCHANGERATE_API_KEY: str = field(default_factory=read_api_key)

    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    BASE_FIAT_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple[str, ...] = ("EUR", "GBP", "RUB", "CNY")
    CRYPTO_CURRENCIES: tuple[str, ...] = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict[str, str] = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }
    )

    RATES_FILE: Path = settings.RATES_FILE
    HISTORY_FILE: Path = settings.EXCHANGE_RATES_FILE

    REQUEST_TIMEOUT: int = 25
    DAILY_REQUEST_LIMIT: int = 1500
    UPDATE_INTERVAL_SECONDS: int = 900

    def fiat_url(self) -> str:
        """
        Собирает адрес запроса фиатных курсов вместе с ключом
        """
        return (
            f"{self.EXCHANGERATE_API_URL}/{self.EXCHANGERATE_API_KEY}"
            f"/latest/{self.BASE_FIAT_CURRENCY}"
        )

    def crypto_url(self) -> str:
        """
        Собирает адрес запроса курсов криптовалют по их идентификаторам
        """
        ids = ",".join(self.CRYPTO_ID_MAP[code] for code in self.CRYPTO_CURRENCIES)
        return (
            f"{self.COINGECKO_URL}?ids={ids}"
            f"&vs_currencies={self.BASE_FIAT_CURRENCY.lower()}"
        )

    def daily_requests(self) -> int:
        """
        Считает, сколько запросов к ExchangeRate-API уйдет за сутки
        """
        return SECONDS_IN_DAY // self.UPDATE_INTERVAL_SECONDS


CONFIG = ParserConfig()
