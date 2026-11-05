from datetime import UTC, datetime

from valutatrade_hub.core import utils
from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError
from valutatrade_hub.logging_config import setup_logging
from valutatrade_hub.parser_service.api_clients import (
    BaseApiClient,
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import CONFIG, ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage

logger = setup_logging()

TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class RatesUpdater:
    """
    Обновление курсов. Опрос источников и запись результата в файлы
    """

    def __init__(
        self,
        clients: list[BaseApiClient] | None = None,
        storage: RatesStorage | None = None,
        config: ParserConfig = CONFIG,
    ) -> None:
        """
        Задает список клиентов и хранилище для обновления
        """
        self.config = config
        self.clients = clients or build_clients(config=config)
        self.storage = storage or RatesStorage(config)

    def run_update(self) -> dict:
        """
        Опрашивает все источники и сохраняет курсы в снимок и историю
        """
        moment = datetime.now(UTC).strftime(TIMESTAMP_FORMAT)
        logger.info("UPDATE start sources=%d", len(self.clients))

        pairs = {}
        records = []
        failed = []
        for client in self.clients:
            try:
                rates = client.fetch_rates()
            except Exception as error:
                failed.append(client.source)
                logger.info(
                    "UPDATE source=%r result=ERROR error_type=%s error_message=%r",
                    client.source,
                    type(error).__name__,
                    str(error),
                )
                continue

            accepted = 0
            for pair, rate in rates.items():
                record = self._build_record(pair, rate, client.source, moment)
                if record is None:
                    continue
                pairs[pair] = {
                    "rate": record["rate"],
                    "updated_at": moment,
                    "source": client.source,
                }
                records.append(record)
                accepted += 1
            logger.info(
                "UPDATE source=%r result=OK received=%d accepted=%d",
                client.source,
                len(rates),
                accepted,
            )

        if not pairs:
            logger.info("UPDATE result=ERROR error_message='нет ни одного курса'")
            raise ApiRequestError("ни один источник не отдал курсы")

        saved = self.storage.load_snapshot().get("pairs", {})
        self.storage.save_snapshot(saved | pairs, moment)
        added = self.storage.append_history(records)
        logger.info(
            "UPDATE result=OK pairs=%d new_records=%d failed_sources=%s",
            len(pairs),
            added,
            ",".join(failed) or "нет",
        )
        return {
            "pairs": pairs,
            "last_refresh": moment,
            "failed_sources": failed,
        }

    def _build_record(
        self, pair: str, rate: float, source: str, moment: str
    ) -> dict | None:
        """
        Создает запись истории, проверяя код валюты и значение курса
        """
        from_code, _, to_code = pair.partition("_")
        try:
            from_code = utils.validate_currency_code(from_code)
            to_code = utils.validate_currency_code(to_code)
        except CurrencyNotFoundError as error:
            logger.info(
                "UPDATE pair=%r result=SKIP error_message=%r", pair, str(error)
            )
            return None

        if not isinstance(rate, (int, float)) or rate <= 0:
            logger.info(
                "UPDATE pair=%r result=SKIP error_message='курс не число'", pair
            )
            return None

        return {
            "id": f"{from_code}_{to_code}_{moment}",
            "from_currency": from_code,
            "to_currency": to_code,
            "rate": float(rate),
            "timestamp": moment,
            "source": source,
            "meta": {"raw_id": self.config.CRYPTO_ID_MAP.get(from_code, from_code)},
        }


SOURCES = {
    "coingecko": CoinGeckoClient,
    "exchangerate": ExchangeRateApiClient,
}


def build_clients(
    source: str | None = None, config: ParserConfig = CONFIG
) -> list[BaseApiClient]:
    """
    Возвращает клиентов для обновления: указанный источник или все
    """
    if source is None:
        return [client(config) for client in SOURCES.values()]

    name = source.strip().lower()
    if name not in SOURCES:
        raise ValueError(
            f"Неизвестный источник '{source}'. Доступны: {', '.join(SOURCES)}"
        )
    return [SOURCES[name](config)]
