import json
from datetime import datetime
from pathlib import Path

from valutatrade_hub.core import utils
from valutatrade_hub.core.models import Portfolio, Wallet
from valutatrade_hub.infra import settings


class DatabaseManager:
    """
    Единая точка доступа к JSON-хранилищу проекта
    """
    # Хранилище одно на всё приложение,
    # пути к файлам читаются из настроек один раз.
    _instance = None

    def __new__(cls) -> "DatabaseManager":
        """
        Возвращает единственный экземпляр, создавая его при первом обращении
        """
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._users_file = settings.USERS_FILE
            instance._portfolios_file = settings.PORTFOLIOS_FILE
            instance._rates_file = settings.RATES_FILE
            cls._instance = instance
        return cls._instance

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
        Записывает данные в JSON-файл, создавая папку при необходимости
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load_users(self) -> list:
        """
        Читает список пользователей из users.json
        """
        return self._read(self._users_file, [])

    def save_user(self, record: dict) -> None:
        """
        Добавляет пользователя в users.json, заменяя запись с тем же id
        """
        users = self.load_users()
        for index, saved in enumerate(users):
            if saved["user_id"] == record["user_id"]:
                users[index] = record
                break
        else:
            users.append(record)
        self._write(self._users_file, users)

    def load_portfolio(self, user_id: int) -> Portfolio:
        """
        Собирает портфель пользователя из portfolios.json
        """
        portfolios = self._read(self._portfolios_file, [])
        saved = next((p for p in portfolios if p["user_id"] == user_id), None)
        if saved is None:
            raise ValueError(f"Портфель пользователя с id={user_id} не найден")

        wallets = {
            code: Wallet(code, data["balance"])
            for code, data in saved["wallets"].items()
        }
        return Portfolio(user_id, wallets)

    def save_portfolio(self, portfolio: Portfolio) -> None:
        """
        Записывает портфель в portfolios.json, заменяя прежнюю запись
        """
        portfolios = self._read(self._portfolios_file, [])
        record = {
            "user_id": portfolio.user,
            "wallets": {
                code: {"balance": wallet.balance}
                for code, wallet in portfolio.wallets.items()
            },
        }
        for index, saved in enumerate(portfolios):
            if saved["user_id"] == portfolio.user:
                portfolios[index] = record
                break
        else:
            portfolios.append(record)
        self._write(self._portfolios_file, portfolios)

    def load_cached_rate(
        self, source: str, target: str
    ) -> tuple[float, str] | None:
        """
        Возвращает курс и время обновления, если он ещё не устарел
        """
        moment = self.load_snapshot().get("last_refresh")
        if moment is None:
            return None

        updated_at = datetime.fromisoformat(moment)
        age = (datetime.now(updated_at.tzinfo) - updated_at).total_seconds()
        if age > settings.RATE_TTL_SECONDS:
            return None

        rates = utils.load_rates()
        if source not in rates or target not in rates:
            return None
        return rates[source] / rates[target], moment

    def load_snapshot(self) -> dict:
        """
        Возвращает весь снимок курсов из rates.json
        """
        return self._read(self._rates_file, {})


DATABASE = DatabaseManager()
