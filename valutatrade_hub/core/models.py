import hashlib
import secrets
from datetime import datetime

from valutatrade_hub.core.currencies import (
    BASE_CURRENCY,
    MAX_CURRENCY_LENGTH,
    MIN_CURRENCY_LENGTH,
    exchange_rates,
)

MIN_USERNAME_LENGTH = 3
MIN_PASSWORD_LENGTH = 4
SALT_BYTES = 8


class User:
    """
    Пользователь системы: хранит учётные данные и проверяет пароль
    """

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ) -> None:
        """
        Создаёт пользователя из уже сохранённых данных
        """
        self._user_id: int = user_id
        self.username = username
        self._hashed_password: str = hashed_password
        self._salt: str = salt
        self._registration_date: datetime = registration_date

    @property
    def user_id(self) -> int:
        """
        Уникальный идентификатор, изменению не подлежит
        """
        return self._user_id

    @property
    def username(self) -> str:
        """
        Имя пользователя
        """
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        """
        Задаёт имя пользователя, запрещая пустое значение
        """
        if not value or len(value) < MIN_USERNAME_LENGTH:
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = str(value)

    @property
    def hashed_password(self) -> str:
        """
        Хеш пароля, только для чтения
        """
        return self._hashed_password

    @property
    def salt(self) -> str:
        """
        Соль пользователя, только для чтения
        """
        return self._salt

    @property
    def registration_date(self) -> datetime:
        """
        Дата регистрации, изменению не подлежит
        """
        return self._registration_date

    def get_user_info(self) -> dict:
        """
        Возвращает данные пользователя без пароля и соли
        """
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def change_password(self, new_password: str) -> None:
        """
        Меняет пароль: генерирует новую соль и сохраняет хеш
        """
        if len(new_password) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов"
            )
        self._salt = secrets.token_hex(SALT_BYTES)
        self._hashed_password = hashlib.sha256(
            (new_password + self._salt).encode("utf-8")
        ).hexdigest()

    def verify_password(self, password: str) -> bool:
        """
        Проверяет, совпадает ли введённый пароль с сохранённым
        """
        candidate = hashlib.sha256(
            (password + self._salt).encode("utf-8")
        ).hexdigest()
        return candidate == self._hashed_password


class Wallet:
    """
    Кошелек пользователя одной конкретной валюты
    """

    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        """
        Создаёт кошелёк с указанной валютой и начальным балансом
        """
        if not isinstance(currency_code, str):
            raise ValueError("Код валюты должен быть строкой")
        code = currency_code.strip().upper()
        if not MIN_CURRENCY_LENGTH <= len(code) <= MAX_CURRENCY_LENGTH:
            raise ValueError(
                f"Код валюты должен содержать от {MIN_CURRENCY_LENGTH} "
                f"до {MAX_CURRENCY_LENGTH} символов"
            )
        self._currency_code: str = code
        self.balance = balance

    def deposit(self, amount: float) -> float:
        """
        Пополняет баланс и возвращает новое значение
        """
        if amount <= 0:
            raise ValueError(
                "Для пополнения баланса должно быть указано положительное число"
            )
        self.balance += amount
        return self.balance

    def get_balance_info(self) -> dict:
        """
        Вывод информации о текущем балансе
        """
        return {
            "currency": self.currency_code,
            "balance": self._balance
        }

    @property
    def currency_code(self) -> str:
        """
        Код валюты кошелька, изменению не подлежит
        """
        return self._currency_code

    @property
    def balance(self) -> float:
        """
        Баланс пользователя, только для чтения
        """
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        """
        Запрет на отрицательный или не числовой баланс
        """
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    def withdraw(self, amount: float) -> float:
        """
        Снятие средств со счета без превышения баланса
        """
        if amount <= 0:
            raise ValueError(
                "Сумма снятия должна быть положительным числом")
        if amount > self._balance:
            raise ValueError("Не хватает средств на снятие")
        self.balance -= amount
        return self.balance


class Portfolio:
    """
    Управление всеми кошельками одного пользователя
    """

    def __init__(self, user_id: int, wallets: dict[str, Wallet]) -> None:
        """
        Создаёт профиль пользователя со всеми его кошельками
        """
        self._user_id: int = user_id
        self._wallets = dict(wallets)

    def add_currency(self, currency_code: str) -> None:
        """
        Создаёт кошелёк новой валюты и добавляет его в профиль
        """
        wallet = Wallet(currency_code)
        if wallet.currency_code in self._wallets:
            raise ValueError(
                f"Пользователь уже имеет кошелек валюты {wallet.currency_code}"
            )
        self._wallets[wallet.currency_code] = wallet

    def get_total_value(self, base_currency: str = BASE_CURRENCY) -> float:
        """
        Возвращает общую стоимость всех кошельков в указанной базовой валюте
        """
        base = base_currency.strip().upper()
        if base not in exchange_rates:
            raise ValueError(f"Неизвестен курс валюты {base}")
        total = 0.0
        for wallet in self._wallets.values():
            if wallet.currency_code not in exchange_rates:
                raise ValueError(
                    f"Неизвестен курс валюты {wallet.currency_code}"
                )
            total += wallet.balance * exchange_rates[wallet.currency_code]
        return total / exchange_rates[base]

    def get_wallet(self, currency_code: str) -> Wallet:
        """
        Возвращает кошелёк пользователя по коду валюты
        """
        code = currency_code.strip().upper()
        if code not in self._wallets:
            raise ValueError(f"У пользователя нет кошелька валюты {code}")
        return self._wallets[code]

    @property
    def user(self) -> int:
        """
        Идентификатор владельца портфеля, изменению не подлежит
        """
        return self._user_id

    @property
    def wallets(self) -> dict[str, Wallet]:
        """
        Копия словаря кошельков: правки извне в портфель не попадают
        """
        return dict(self._wallets)
