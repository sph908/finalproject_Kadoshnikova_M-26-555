import time

from valutatrade_hub.logging_config import setup_logging
from valutatrade_hub.parser_service.config import CONFIG, ParserConfig
from valutatrade_hub.parser_service.updater import RatesUpdater

logger = setup_logging()


class RatesScheduler:
    """
    Периодический запуск обновления курсов
    """

    def __init__(
        self,
        updater: RatesUpdater | None = None,
        config: ParserConfig = CONFIG,
    ) -> None:
        """
        Задает обновление курсов и паузу между запусками
        """
        self.config = config
        self.updater = updater or RatesUpdater(config=config)
        self.interval = config.UPDATE_INTERVAL_SECONDS

    def run_forever(self, limit: int | None = None) -> int:
        """
        Повторяет обновление с паузой, пока его не прервут с клавиатуры
        """
        logger.info(
            "SCHEDULE start interval=%d budget=%d/%d",
            self.interval,
            self.config.daily_requests(),
            self.config.DAILY_REQUEST_LIMIT,
        )
        runs = 0
        try:
            while limit is None or runs < limit:
                self._run_once()
                runs += 1
                if runs != limit:
                    time.sleep(self.interval)
        except KeyboardInterrupt:
            pass

        logger.info("SCHEDULE stop runs=%d", runs)
        return runs

    def _run_once(self) -> None:
        """
        Делает одно обновление, не давая сбою остановить расписание
        """
        try:
            self.updater.run_update()
        except Exception as error:
            logger.info(
                "SCHEDULE result=ERROR error_type=%s error_message=%r",
                type(error).__name__,
                str(error),
            )


if __name__ == "__main__":
    RatesScheduler().run_forever()
