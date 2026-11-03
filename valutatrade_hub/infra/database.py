from datetime import datetime

from valutatrade_hub.core import utils
from valutatrade_hub.core.models import Portfolio, Wallet
from valutatrade_hub.infra import settings


def load_portfolio(user_id: int) -> Portfolio:
    """
    Собирает портфель пользователя из portfolios.json
    """
    portfolios = utils.load_jsondata(settings.PORTFOLIOS_FILE, [])
    saved = next((p for p in portfolios if p["user_id"] == user_id), None)
    if saved is None:
        raise ValueError(f"Портфель пользователя с id={user_id} не найден")

    wallets = {
        code: Wallet(code, data["balance"])
        for code, data in saved["wallets"].items()
    }
    return Portfolio(user_id, wallets)


def save_portfolio(portfolio: Portfolio) -> None:
    """
    Записывает портфель в portfolios.json, заменяя прежнюю запись
    """
    portfolios = utils.load_jsondata(settings.PORTFOLIOS_FILE, [])
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
    utils.save_jsondata(settings.PORTFOLIOS_FILE, portfolios)


def load_cached_rate(source: str, target: str) -> tuple[float, datetime] | None:
    """
    Возвращает курс и время обновления из кеша, если он ещё не устарел
    """
    cache = utils.load_jsondata(settings.RATES_FILE, {})
    saved = cache.get(f"{source}/{target}")
    if saved is None:
        return None

    updated_at = datetime.fromisoformat(saved["updated_at"])
    if (datetime.now() - updated_at).total_seconds() > settings.RATE_TTL_SECONDS:
        return None
    return saved["rate"], updated_at


def save_cached_rate(
    source: str, target: str, rate: float, updated_at: datetime
) -> None:
    """
    Записывает курс в локальный кеш rates.json
    """
    cache = utils.load_jsondata(settings.RATES_FILE, {})
    cache[f"{source}/{target}"] = {
        "rate": rate,
        "updated_at": updated_at.isoformat(timespec="seconds"),
    }
    utils.save_jsondata(settings.RATES_FILE, cache)
