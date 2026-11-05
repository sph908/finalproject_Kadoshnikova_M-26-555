import json
import os
from pathlib import Path

from valutatrade_hub.parser_service.config import CONFIG, ParserConfig


class RatesStorage:
    """
    Работа с файлами парсера, курсы и история замеров
    """

    def __init__(self, config: ParserConfig = CONFIG) -> None:
        """
        Сохраняет настройки, откуда берутся пути к файлам
        """
        self.config = config

    @staticmethod
    def _read(filepath: Path, default: list | dict) -> list | dict:
        """
        Читает JSON-файл, при его отсутствии возвращает значение по умолчанию
        """
        try:
            with open(filepath, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return default

    @staticmethod
    def _write(filepath: Path, data: list | dict) -> None:
        """
        Записывает JSON через временный файл, чтобы не испортить основной
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)
        temp_file = filepath.with_name(filepath.name + ".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        os.replace(temp_file, filepath)

    def save_snapshot(self, pairs: dict, last_refresh: str) -> None:
        """
        Перезаписывает rates.json текущими курсами
        """
        self._write(
            self.config.RATES_FILE,
            {"pairs": pairs, "last_refresh": last_refresh},
        )

    def load_snapshot(self) -> dict:
        """
        Возвращает содержимое rates.json
        """
        return self._read(self.config.RATES_FILE, {})

    def append_history(self, records: list) -> int:
        """
        Дописывает замеры в exchange_rates.json, пропуская уже записанные
        """
        history = self._read(self.config.HISTORY_FILE, [])
        known = {saved["id"] for saved in history}
        fresh = [record for record in records if record["id"] not in known]
        if fresh:
            self._write(self.config.HISTORY_FILE, history + fresh)
        return len(fresh)
