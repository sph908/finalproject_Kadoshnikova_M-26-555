import tomllib
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_FILE = BASE_DIR / "pyproject.toml"
CONFIG_SECTION = "valutatrade"

DEFAULT_SETTINGS = {
    "data_dir": "data",
    "users_file": "users.json",
    "portfolios_file": "portfolios.json",
    "rates_file": "rates.json",
    "exchange_rates_file": "exchange_rates.json",
    "logs_file": "logs/actions.log",
    "log_level": "INFO",
    "rates_ttl_seconds": 300,
    "base_currency": "USD",
}


class SettingsLoader:
    """
    Единая точка доступа к настройкам проекта
    """

    # Синглтон сделан через __new__, а не через метакласс.
    # Короче и понятнее, вся логика видна в одном методе.
    _instance = None

    def __new__(cls) -> "SettingsLoader":
        """
        Возвращает единственный экземпляр, создавая его при первом обращении
        """
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._settings = cls._read_config()
            cls._instance = instance
        return cls._instance

    @staticmethod
    def _read_config() -> dict:
        """
        Читает секцию [tool.valutatrade] из pyproject.toml поверх умолчаний
        """
        config_values = dict(DEFAULT_SETTINGS)
        try:
            with open(CONFIG_FILE, "rb") as config_file:
                parsed = tomllib.load(config_file)
        except (FileNotFoundError, tomllib.TOMLDecodeError):
            return config_values

        config_values.update(parsed.get("tool", {}).get(CONFIG_SECTION, {}))
        return config_values

    def get(self, key: str, default: Any = None) -> Any:
        """
        Возвращает значение настройки или default, если ключа нет
        """
        return self._settings.get(key, default)

    def reload(self) -> None:
        """
        Перечитывает конфигурацию с диска
        """
        self._settings = self._read_config()


SETTINGS = SettingsLoader()

DATA_DIR = BASE_DIR / SETTINGS.get("data_dir")
USERS_FILE = DATA_DIR / SETTINGS.get("users_file")
PORTFOLIOS_FILE = DATA_DIR / SETTINGS.get("portfolios_file")
RATES_FILE = DATA_DIR / SETTINGS.get("rates_file")
EXCHANGE_RATES_FILE = DATA_DIR / SETTINGS.get("exchange_rates_file")
LOGS_FILE = BASE_DIR / SETTINGS.get("logs_file")
RATE_TTL_SECONDS = SETTINGS.get("rates_ttl_seconds")
