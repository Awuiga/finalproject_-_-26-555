# ValutaTrade Hub — итоговый Python-проект

**Выполнил:** Кислощаев, группа М26-555.

**Папка проекта:** `finalproject_Кислощаев_М26-555`.

**Виртуальный** валютный кошелёк с регистрацией, торговыми операциями и сервисом получения курсов. Реальные деньги и биржевые аккаунты не используются. Приложение оформлено как Python-пакет и запускается из терминала.

## Требования

- Python 3.11 или новее;
- `uv` — управление зависимостями и запуск;
- интернет для установки зависимостей и обновления рыночных курсов;
- ключ **ExchangeRate-API** для курсов фиатных валют; CoinGecko получает цены криптовалют.

## Установка и запуск

```bash
# Перейти в распакованную папку с pyproject.toml
cd finalproject_Кислощаев_М26-555
uv sync --group dev
uv run valutatrade
```

Альтернативный запуск после установки: `uv run python main.py`. Если `uv` не установлен: <https://docs.astral.sh/uv/getting-started/installation/>.

**Зависимости и сборка проверены:** `uv.lock` создан и сохранён в Git; `uv sync --group dev`, `uv run ruff check .`, `uv run ruff format --check .` и `uv build` успешно выполнены на Windows (Python 3.12). Проверка реальных ответов API выполняется отдельно при наличии сети и ключа.

### Реальные курсы и ключ API

1. Зарегистрируйте учебный ключ на <https://www.exchangerate-api.com/>.
2. В PowerShell **локально**, до запуска приложения, задайте переменную `$env:EXCHANGERATE_API_KEY="ваш_ключ"` (в Linux/WSL: `export EXCHANGERATE_API_KEY="ваш_ключ"`). Даже учебный ключ не публикуйте в репозитории; не добавляйте его в Git.
3. Запустите `uv run valutatrade`; в приложении выполните `update-rates`, затем `show-rates`, `get-rate --from EUR --to USD` и `get-rate --from BTC --to USD`.
4. Ключ не вставляется в исходники. Файлы `.env` исключены из Git. Наличие `.env` само по себе не загружает ключ: переменную нужно экспортировать в окружение.

Если нет ключа, `update-rates` продолжит загрузку криптовалют CoinGecko; ошибка второго API появится отдельно. При отсутствии интернета используйте **`demo-rates`**: загрузятся **фиксированные учебные, а не настоящие курсы**.

## Как пользоваться

Команды вводятся в **одной** запущенной оболочке после `uv run valutatrade`. Это важно: `login` хранит текущую сессию в оперативной памяти процесса, поэтому при повторном запуске приложения нужно войти снова.

```text
valutatrade> demo-rates
valutatrade> register --username alice --password 1234
valutatrade> login --username alice --password 1234
valutatrade> deposit-demo --amount 10000
valutatrade> buy --currency BTC --amount 0.05
valutatrade> sell --currency BTC --amount 0.01
valutatrade> show-portfolio
valutatrade> get-rate --from USD --to BTC
valutatrade> show-rates --top 2
valutatrade> history
valutatrade> exit
```

Основные команды: `register`, `login`, `logout`, `show-portfolio`, `buy`, `sell`, `get-rate`, `update-rates`, `show-rates`, `currencies`, `history`, `deposit-demo`, `demo-rates`, `scheduler`, `help`, `exit`.

Для проверки ошибок попробуйте `sell --currency BTC --amount 100` и `get-rate --from ABC --to USD`. Пароль не отображается при регистрации и не пишется в файл логов (в консоли при вводе команды его видно: для реального приложения понадобился бы скрытый ввод).

### Важное уточнение логики торговли

В разных частях исходного ТЗ указаны два варианта: **просто увеличить баланс при buy** и **списать стоимость с USD-кошелька**. Реализован второй, экономически согласованный вариант:

- регистрация создаёт **пустой** портфель;
- `deposit-demo --amount 10000` кладёт *виртуальные* USD (дополнительная команда для демонстрации);
- `buy BTC 0.05` увеличивает BTC, уменьшает USD на `0.05 × BTC_USD`;
- `sell BTC 0.01` уменьшает BTC, увеличивает USD на `0.01 × BTC_USD`;
- без денег или при продаже слишком большого количества показывается `InsufficientFundsError`;
- новые кошельки создаются автоматически; история хранится в `portfolios.json`.

Это симулятор, а не платёжная система. Для сохранения денежных сумм в реальной торговле лучше использовать `Decimal` и базу данных с транзакциями, а не `float` и JSON.

## Архитектура

```text
finalproject_Кислощаев_М26-555/
├── data/
│   ├── users.json                 # пользователи с солью и хешем SHA-256
│   ├── portfolios.json            # кошельки и виртуальные операции
│   ├── rates.json                 # последний снимок курсов и last_refresh
│   └── exchange_rates.json        # исторические замеры
├── valutatrade_hub/
│   ├── __init__.py
│   ├── logging_config.py          # INFO/DEBUG, RotatingFileHandler
│   ├── decorators.py              # @log_action
│   ├── core/
│   │   ├── currencies.py          # ABC Currency, FiatCurrency, CryptoCurrency
│   │   ├── exceptions.py          # доменные ошибки
│   │   ├── models.py              # User, Wallet, Portfolio
│   │   ├── usecases.py            # TradeService, RateService
│   │   └── utils.py               # проверки и время
│   ├── infra/
│   │   ├── settings.py            # SettingsLoader (Singleton)
│   │   └── database.py            # DatabaseManager (Singleton)
│   ├── parser_service/
│   │   ├── config.py              # URL, env, таймауты, списки валют
│   │   ├── api_clients.py         # BaseApiClient и 2 реализации
│   │   ├── updater.py             # RatesUpdater, объединение результатов
│   │   ├── storage.py             # кэш и история (tmp → os.replace)
│   │   └── scheduler.py           # обновление по таймеру
│   └── cli/
│       ├── interface.py           # shlex + argparse + prettytable
├── docs/
│   └── valutatrade_demo.gif       # демонстрация полного CLI-сценария
├── main.py
├── uv.lock                       # зафиксированные версии зависимостей
├── pyproject.toml
├── .gitignore
└── README.md
```

Все папки `core`, `infra`, `cli`, `parser_service` содержат `__init__.py`.

## Работа с API и форматы хранения

Два клиента реализуют `BaseApiClient.fetch_rates() -> dict[str, float]`: CoinGecko возвращает BTC/ETH/SOL к USD, ExchangeRate-API — EUR/GBP/RUB. Данные приводятся к парам `BTC_USD`, `EUR_USD` и т. д.

**Важно:** ExchangeRate-API с базой USD обычно возвращает `conversion_rates.EUR` как количество EUR за 1 USD. Чтобы записать именно `EUR_USD`, приложение **инвертирует** значение. Это исправляет расхождение направления пары в примерах ТЗ.

Структура `data/rates.json`:

```json
{
  "pairs": {
    "BTC_USD": {"rate": 59300.0, "updated_at": "2025-10-10T12:00:00Z", "source": "DEMO"}
  },
  "last_refresh": "2025-10-10T12:00:00Z"
}
```

Это **пример формата и учебного курса**, а не рыночная котировка. Значения этого примера устареют относительно текущей даты. Второй файл `exchange_rates.json` — JSON-список исторических записей с уникальным `id = FROM_TO_timestamp`, метками времени, источником и полем `meta`.

`RateService` проверяет время **каждой пары** с TTL по умолчанию **300 секунд**. Для обратного курса использует `1 / rate`, для кросс-курса — пересчёт через USD (например, EUR/BTC = EUR/USD ÷ BTC/USD). При устаревании `get-rate` пытается обновить курсы и сообщает об ошибке, если обновить нельзя. В `show-rates` выводится кэш, а для смены базы требуется актуальная конвертация.

`RatesUpdater` продолжает работу, если один из двух источников недоступен, пишет в журнал итог и сообщает об ошибках. Сохранение **каждого JSON-файла** атомарно (`tmp → os.replace`). Два файла обновляются последовательно, без общей межфайловой транзакции. Блокировки гарантируют согласованность **в пределах одного процесса**, но не между независимыми процессами. Для промышленного решения нужна СУБД.

## ООП, логирование, ошибки

- `User`: приватные поля, `@property`, генерация соли через `secrets.token_hex`, учебное хеширование `SHA-256(salt + password)`, ISO-дата; в `get_user_info` нет пароля.
- `Wallet`: `@property balance`, строгая проверка типов, `deposit/withdraw`, исключение `InsufficientFundsError`.
- `Portfolio`: один кошелёк на код валюты; возвращает копию словаря `wallets`; `get_total_value` конвертирует все остатки.
- `Currency`: абстрактный класс; подклассы с переопределённым `get_display_info`, реестр и фабрика `get_currency()`.
- `SettingsLoader` и `DatabaseManager`: шаблон Singleton через `__new__`, потому что так проще проследить единственный экземпляр.
- `@log_action`: `timestamp/action/user_id/currency_code/amount/base/result`, при ошибках `error_type/error_message`, у торговых действий курс и остатки до/после. Логи — `logs/actions.log`, ротация при 1 МБ, хранится 3 предыдущих файла, уровень INFO, конфиг можно сменить на DEBUG.
- `CurrencyNotFoundError`, `InsufficientFundsError`, `ApiRequestError` доходят до CLI, который выводит понятные ошибки и не завершает сессию.

**Безопасность:** простое солёное SHA-256 по учебному ТЗ **не подходит для хранения реальных паролей**. Для настоящих сервисов используйте Argon2id или bcrypt, защищённое хранилище и скрытый ввод.

## Проверки качества

```bash
uv run ruff check .
uv run ruff format --check .
uv build
```

Проверку Ruff и сборку необходимо выполнить после установки зависимостей. Для сдачи оставлены только исходные файлы, конфигурация, JSON-хранилище, README, Git-история и GIF-демонстрация.

Изменение кода с помощью `uv run ruff format .` приведёт стиль к единому формату. После каждого этапа полезно делать осмысленный коммит:

```bash
git status
git log --oneline -5
# Проверка изменений:
git status
```

### Демо-запись

В комплект входит **`docs/valutatrade_demo.gif`** — 14 кадров, полученных из реального вывода приложения на виртуальных учебных данных. При желании можно записать собственную демонстрацию через `asciinema rec demo.cast`, выполнить команды из раздела «Как пользоваться» и завершить запись. Используйте тестовый пароль вроде `1234`, не настоящий.

## Известные ограничения

- Нет реальных финансовых операций, рыночных комиссий и синхронизации с биржей.
- `float` годится для учебного задания, но не для денежных расчётов в продакшне.
- Данные пользователей и портфелей — отдельные JSON: регистрация между записями двух файлов не полностью транзакционна.
- Ключ API действует только в окружении процесса; при сетевых ошибках показывается сообщение, а не ложный «текущий курс».
- Программа не рассчитана на одновременную запись несколькими запущенными процессами.
