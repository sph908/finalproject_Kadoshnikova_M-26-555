import logging
from logging.handlers import RotatingFileHandler

from valutatrade_hub.infra import settings

LOGGER_NAME = "valutatrade"
LOG_FORMAT = "%(levelname)s %(asctime)s %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 5
DEFAULT_LEVEL = "INFO"


def setup_logging(level: str | int | None = None) -> logging.Logger:
    """
    Настраивает журнал действий с ротацией файлов и возвращает логгер
    """
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    settings.LOGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        settings.LOGS_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

    logger.addHandler(handler)
    logger.setLevel(level or settings.SETTINGS.get("log_level", DEFAULT_LEVEL))
    logger.propagate = False
    return logger
