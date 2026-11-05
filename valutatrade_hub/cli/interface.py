import math
import sys

from valutatrade_hub.core import currencies, usecases
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.infra import settings
from valutatrade_hub.parser_service.updater import RatesUpdater, build_clients

COMMAND_REGISTER = "register"
COMMAND_LOGIN = "login"
COMMAND_BUY = "buy"
COMMAND_SELL = "sell"
COMMAND_SHOW_PORTFOLIO = "show-portfolio"
COMMAND_GET_RATE = "get-rate"
COMMAND_EXIT = "exit"

SUPPORTED_CODES = "Поддерживаемые коды валют:"
RETRY_LATER = "Повторите попытку позже или проверьте подключение к сети."
PROMPT = "> "
NOT_LOGGED_IN = "Сначала выполните вход командой login"
GOODBYE = "До свидания"
COMMAND_UPDATE_RATES = "update-rates"
COMMAND_SHOW_RATES = "show-rates"
COMMAND_LIST_CURRENCIES = "list-currencies"


def parse_args(parts: list[str]) -> dict:
    """
    Превращает ['--username', 'alice', '--password', '1234'] в словарь
    """
    args = {}
    for index in range(0, len(parts), 2):
        key = parts[index]
        if not key.startswith("--") or index + 1 >= len(parts):
            raise ValueError(f"Неверный формат аргументов: {' '.join(parts)}")
        args[key[2:]] = parts[index + 1]
    return args


def require(args: dict, name: str) -> str:
    """
    Возвращает обязательный аргумент или сообщает, что он пропущен
    """
    if name not in args:
        raise ValueError(f"Аргумент --{name} обязателен")
    return args[name]


def require_amount(args: dict, name: str) -> float:
    """
    Возвращает числовой аргумент или сообщает о некорректной сумме
    """
    value = require(args, name)
    try:
        number = float(value)
    except ValueError:
        raise ValueError(f"'{name}' должен быть положительным числом") from None

    if not math.isfinite(number):
        raise ValueError(f"'{name}' должен быть положительным числом")
    return number


def require_top(args: dict) -> int | None:
    """
    Возвращает значение --top числом или None, если флага нет
    """
    if "top" not in args:
        return None
    try:
        value = int(args["top"])
    except ValueError:
        raise ValueError("'top' должен быть целым числом") from None
    if value <= 0:
        raise ValueError("'top' должен быть больше нуля")
    return value


def list_currencies() -> str:
    """
    Перечисляет поддерживаемые валюты с их описанием
    """
    return "\n".join(
        currency.get_display_info() for currency in currencies.CURRENCIES.values()
    )


def update_rates(source: str | None) -> str:
    """
    Запускает обновление курсов и возвращает отчет для пользователя
    """
    clients = build_clients(source)
    print("Обновление курсов...")
    result = RatesUpdater(clients=clients).run_update()

    lines = [
        f"Обновление завершено. Курсов обновлено: {len(result['pairs'])}.",
        f"Последнее обновление: {result['last_refresh']}",
    ]
    if result["failed_sources"]:
        lines.append(
            f"Не ответили источники: {', '.join(result['failed_sources'])}. "
            f"Подробности в {settings.LOGS_FILE.name}"
        )
    return "\n".join(lines)


def run() -> None:
    """
    Читает команды пользователя и выполняет их до команды exit
    """
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    current_user = None
    while True:
        parts = input(PROMPT).strip().split()
        if not parts:
            continue
        name, rest = parts[0], parts[1:]
        try:
            if name == COMMAND_EXIT:
                print(GOODBYE)
                break
            args = parse_args(rest)
            if name == COMMAND_REGISTER:
                print(usecases.register(require(args, "username"),
                                        require(args, "password")))
            elif name == COMMAND_LOGIN:
                current_user = usecases.login(require(args, "username"),
                                              require(args, "password"))
                print(f"Вы вошли как '{current_user.username}'")
            elif name == COMMAND_BUY:
                if current_user is None:
                    raise ValueError(NOT_LOGGED_IN)
                print(usecases.buy(
                    current_user,
                    require(args, "currency"),
                    require_amount(args, "amount"),
                ))
            elif name == COMMAND_SELL:
                if current_user is None:
                    raise ValueError(NOT_LOGGED_IN)
                print(usecases.sell(
                    current_user,
                    require(args, "currency"),
                    require_amount(args, "amount"),
                ))
            elif name == COMMAND_SHOW_PORTFOLIO:
                if current_user is None:
                    raise ValueError(NOT_LOGGED_IN)
                print(usecases.show_portfolio(current_user, args.get("base")))
            elif name == COMMAND_LIST_CURRENCIES:
                print(list_currencies())
            elif name == COMMAND_UPDATE_RATES:
                print(update_rates(args.get("source")))
            elif name == COMMAND_SHOW_RATES:
                print(usecases.show_rates(
                    args.get("currency"),
                    require_top(args),
                    args.get("base"),
                ))
            elif name == COMMAND_GET_RATE:
                print(usecases.get_rate(
                    require(args, "from"), require(args, "to")
                ))
            else:
                print(f"Неизвестная команда: {name}")
        except InsufficientFundsError as error:
            print(error)
        except CurrencyNotFoundError as error:
            print(error)
            print(f"{SUPPORTED_CODES} {', '.join(currencies.CURRENCIES)}")
        except ApiRequestError as error:
            print(error)
            print(RETRY_LATER)
        except ValueError as error:
            print(error)
