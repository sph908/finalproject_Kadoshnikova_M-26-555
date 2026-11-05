# ValutaTrade Hub

Консольный учёт валютного портфеля: покупка и продажа валюты по реальным
курсам, оценка портфеля в любой базовой валюте.

Курсы берутся из двух API (ExchangeRate-API и CoinGecko) и кешируются в файл,
поэтому обычные операции работают без сети.

Валюты: USD, EUR, GBP, RUB, CNY, BTC, ETH, SOL. База расчётов USD.

## Структура

```
├── data/
│   ├── users.json             # аккаунты: хеш пароля и соль
│   ├── portfolios.json        # кошельки
│   ├── rates.json             # кеш курсов для Core Service
│   └── exchange_rates.json    # история замеров Parser Service
├── valutatrade_hub/
│   ├── logging_config.py      # журнал с ротацией
│   ├── decorators.py          # @log_action
│   ├── core/
│   │   ├── currencies.py      # иерархия валют и справочник
│   │   ├── exceptions.py      # свои исключения
│   │   ├── models.py          # User, Wallet, Portfolio
│   │   ├── usecases.py        # сценарии
│   │   └── utils.py           # проверка кодов и конвертация
│   ├── infra/
│   │   ├── settings.py        # SettingsLoader, пути и TTL
│   │   └── database.py        # DatabaseManager, чтение и запись JSON
│   ├── parser_service/
│   │   ├── config.py          # ключ, адреса API, списки валют, лимиты
│   │   ├── api_clients.py     # CoinGeckoClient, ExchangeRateApiClient
│   │   ├── updater.py         # опрос источников и сборка снимка
│   │   ├── storage.py         # запись снимка и истории
│   │   └── scheduler.py       # периодическое обновление
│   └── cli/interface.py       # разбор команд и вывод
├── main.py
├── pyproject.toml
└── uv.lock
```

## Установка

Нужен Python 3.12 и [uv](https://docs.astral.sh/uv/).

```bash
git clone <адрес репозитория>
cd finalproject_Kadoshnikova_M-26-555
uv sync
```

## Ключ API

Ключ ExchangeRate-API в коде не хранится. Задайте его одним из двух способов,
проверяются они в этом порядке:

1. Переменная окружения `EXCHANGERATE_API_KEY`.
2. Файл `.env` в корне проекта (занесён в `.gitignore`):

   ```
   EXCHANGERATE_API_KEY=ваш_ключ
   ```

CoinGecko работает без ключа. Без ключа ExchangeRate-API обновятся только
криптовалюты, по фиатным придёт сообщение об ошибке.

## Запуск

```bash
uv run valutatrade
```

Команды вводятся в приглашении `>`, выход по `exit`.

## Команды

- `register --username alice --password 1234` — аккаунт и пустой портфель
- `login --username alice --password 1234` — вход
- `buy --currency BTC --amount 0.05` — покупка, кошелёк создаётся сам
- `sell --currency BTC --amount 0.01` — продажа с проверкой остатка
- `show-portfolio [--base EUR]` — таблица кошельков и общая оценка
- `get-rate --from EUR --to RUB` — курс пары и обратный курс
- `update-rates [--source coingecko|exchangerate]` — обновить кеш
- `show-rates [--currency BTC] [--top 3] [--base EUR]` — курсы из кеша
- `list-currencies` — справочник валют
- `exit` — выход

Пример:

```
> update-rates
Обновление курсов...
Обновление завершено. Курсов обновлено: 7.
Последнее обновление: 2026-11-05T09:24:10Z

> buy --currency BTC --amount 0.05
Покупка выполнена: 0.0500 BTC по курсу 80317.00 USD/BTC
Изменения в портфеле:
- BTC: было 0.0000 → стало 0.0500
Оценочная стоимость покупки: 4,015.85 USD

> show-portfolio
Портфель пользователя 'alice' (база: USD):
+--------+--------+--------------+
| Валюта | Баланс | Оценка в USD |
+--------+--------+--------------+
| BTC    | 0.0500 |     4,015.85 |
| EUR    | 100.00 |       112.37 |
+--------+--------+--------------+
ИТОГО: 4,128.22 USD

> get-rate --from EUR --to RUB
Курс EUR→RUB: 91.86 (обновлено: 2026-11-05T09:24:10Z)
Обратный курс RUB→EUR: 0.01088604

> sell --currency BTC --amount 999
Недостаточно средств: доступно 0.0400 BTC, требуется 999.0000 BTC
```

## Кеш и TTL

Core Service в сеть не ходит, он читает `data/rates.json`:

```json
{
    "pairs": {
        "BTC_USD": {
            "rate": 80317.0,
            "updated_at": "2026-11-05T09:24:10Z",
            "source": "CoinGecko"
        }
    },
    "last_refresh": "2026-11-05T09:24:10Z"
}
```

Время жизни снимка в `pyproject.toml`:

```toml
[tool.valutatrade]
rates_ttl_seconds = 900
base_currency = "USD"
```

- `get-rate` сравнивает `last_refresh` с текущим временем. Снимок свежее TTL
  берётся из файла, устаревший запускает обновление сам.
- `buy`, `sell`, `show-portfolio`, `show-rates` работают только по кешу.
  Обновлять его перед ними нужно вручную.
- Пока кеш пустой, `show-rates` просит выполнить `update-rates`.

Остальные настройки (папка данных, имена файлов, уровень логов) лежат в
`infra/settings.py`, значения из `pyproject.toml` их перекрывают.

## Parser Service

Разовое обновление делает команда `update-rates`. Если один источник не
ответил, берётся то, что пришло от второго:

```
Обновление завершено. Курсов обновлено: 3.
Не ответили источники: ExchangeRate-API. Подробности в actions.log
```

Фоновый режим, пауза 900 секунд (`UPDATE_INTERVAL_SECONDS` в
`parser_service/config.py`), остановка по Ctrl+C:

```bash
uv run python -m valutatrade_hub.parser_service.scheduler
```

В консоль планировщик не печатает, всё пишется в журнал:

```
INFO 2026-11-05T12:26:11 SCHEDULE start interval=900 budget=96/1500
INFO 2026-11-05T12:26:13 UPDATE result=OK pairs=7 new_records=7 failed_sources=нет
```

`budget` показывает, сколько запросов уйдёт за сутки при текущем интервале
и каков лимит тарифа.

Снимок пишется через временный файл с переименованием, оборванная запись
`rates.json` не портит. Записи истории проверяются на дубли по `id`.

## Журнал

`logs/actions.log`, ротация при 1 МБ, хранятся 5 копий.

```
INFO 2026-11-05T12:10:45 BUY user='alice' currency='BTC' amount=0.0500 rate=80331.00 base='USD' result=OK balance=0.0000->0.0500
INFO 2026-11-05T12:12:01 SELL user='alice' currency='ETH' amount=1.0000 result=ERROR error_type=InsufficientFundsError error_message='Недостаточно средств: доступно 0.0000 ETH, требуется 1.0000 ETH'
```

## Линтер

```bash
uv run ruff check .
```

## Демонстрация работы
 
[Запись работы в asciinema](https://asciinema.org/a/BrbMW6mw8x6DXmpd)
