"""Консольная оболочка, обрабатывающая команды без бизнес-логики внутри."""

import argparse
import shlex
import sys
from typing import Any

try:
    from prettytable import PrettyTable
except ModuleNotFoundError:  # Без сети возможно просмотреть результаты.
    from valutatrade_hub.cli.table_fallback import PrettyTable

from valutatrade_hub.core.currencies import CURRENCY_REGISTRY, get_currency
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    ValutaTradeError,
)
from valutatrade_hub.core.usecases import RateService, TradeService
from valutatrade_hub.core.utils import iso_now
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.logging_config import configure_logging
from valutatrade_hub.parser_service.scheduler import run_scheduler
from valutatrade_hub.parser_service.updater import RatesUpdater

HELP = """Доступные команды:
  register --username NAME --password PASSWORD   регистрация
  login --username NAME --password PASSWORD      вход
  logout                                        выход из профиля
  show-portfolio [--base USD]                   портфель и оценка
  deposit-demo --amount 10000                   добавить виртуальные USD
  buy --currency BTC --amount 0.05              покупка за USD
  sell --currency BTC --amount 0.01             продажа за USD
  get-rate --from BTC --to USD                  курс валют
  update-rates [--source coingecko|exchangerate] обновить курсы API
  show-rates [--currency BTC] [--top 2] [--base USD] кеш курсов
  demo-rates                                    загрузить ТЕСТОВЫЕ курсы
  currencies                                    список валют
  history                                       история операций
  scheduler [--interval 300]                   автообновление (Ctrl+C)
  help                                          помощь
  exit                                          завершить программу

ВАЖНО: все сделки и пополнения — виртуальные, не реальные.
Сессия авторизации хранится только внутри запущенной оболочки.
"""


class CommandParser(argparse.ArgumentParser):
    """Аргументы команд: ошибка возвращается в оболочку, не завершает процесс."""

    def error(self, message: str) -> None:
        raise ValueError(f"Неверные аргументы: {message}")


class Console:
    """Оболочка с текущим пользователем и обработчиками команд."""

    def __init__(
        self,
        service: TradeService | None = None,
        database: DatabaseManager | None = None,
        rates: RateService | None = None,
    ) -> None:
        self.database = database or DatabaseManager()
        self.rates = rates or RateService(self.database)
        self.service = service or TradeService(self.database, self.rates)
        self.current_user_id: int | None = None
        self.current_username: str | None = None

    def _require_login(self) -> int:
        if self.current_user_id is None:
            raise ValueError("Сначала выполните login")
        return self.current_user_id

    @staticmethod
    def _parse(command: str, args: list[str]) -> argparse.Namespace:
        parser = CommandParser(prog=command, add_help=False)
        if command in ("register", "login"):
            parser.add_argument("--username", required=True)
            parser.add_argument("--password", required=True)
        elif command in ("buy", "sell"):
            parser.add_argument("--currency", required=True)
            parser.add_argument("--amount", required=True, type=float)
        elif command == "get-rate":
            parser.add_argument("--from", dest="from_code", required=True)
            parser.add_argument("--to", dest="to_code", required=True)
        elif command == "show-portfolio":
            parser.add_argument("--base", default="USD")
        elif command == "deposit-demo":
            parser.add_argument("--amount", required=True, type=float)
        elif command == "update-rates":
            parser.add_argument("--source", choices=["coingecko", "exchangerate"])
        elif command == "show-rates":
            parser.add_argument("--currency")
            parser.add_argument("--top", type=int)
            parser.add_argument("--base", default="USD")
        elif command == "scheduler":
            parser.add_argument("--interval", type=int, default=300)
        return parser.parse_args(args)

    @staticmethod
    def _display_trade(result: Any) -> None:
        action_name = "Покупка" if result.action == "BUY" else "Продажа"
        print(
            f"{action_name} выполнена: {result.amount:.4f} {result.currency_code} "
            f"по курсу {result.rate:.8f} USD/{result.currency_code}"
        )
        print(f"  {result.currency_code}: было {result.before:.4f} → стало {result.after:.4f}")
        print(f"  USD: было {result.usd_before:.4f} → стало {result.usd_after:.4f}")
        print(f"  {'Стоимость покупки' if result.action == 'BUY' else 'Выручка'}: "
              f"{result.total:,.2f} USD")

    def _update_rates(self, source: str | None) -> None:
        result = RatesUpdater().run_update(source)
        print(
            f"Обновлено курсов: {result.count}. "
            f"Последнее обновление: {result.refreshed_at}"
        )
        for failure in result.failures:
            print(f"Источник недоступен: {failure}")

    def _show_rates(self, args: argparse.Namespace) -> None:
        data = self.database.load_rates()
        records = data.get("pairs", {})
        if not records:
            print("Локальный кеш курсов пуст. Выполните 'update-rates'.")
            return
        base = get_currency(args.base).code
        selected = get_currency(args.currency).code if args.currency else None
        if args.top is not None and args.top <= 0:
            raise ValueError("--top должен быть положительным числом")
        rows: list[tuple[str, float, str, str]] = []
        for pair, entry in records.items():
            code = pair.split("_", 1)[0]
            if selected and selected != code:
                continue
            if base == "USD":
                rate = entry["rate"]
            else:
                rate = self.rates.get_rate(code, base).rate
            rows.append((code, rate, entry["updated_at"], entry["source"]))
        if args.top:
            rows = [row for row in rows if CURRENCY_REGISTRY[row[0]].__class__.__name__ == "CryptoCurrency"]
            rows.sort(key=lambda row: row[1], reverse=True)
            rows = rows[:args.top]
        else:
            rows.sort(key=lambda row: row[0])
        if not rows:
            print(f"Курс для '{selected or 'заданных условий'}' не найден в кеше.")
            return
        table = PrettyTable(["Валюта", f"Курс в {base}", "Обновлено (UTC)", "Источник"])
        for code, rate, timestamp, source in rows:
            table.add_row([code, f"{rate:.8f}", timestamp, source])
        print(table)

    def _demo_rates(self) -> None:
        """Только для проверки offline; значения НЕ рыночные и НЕ актуальные."""
        from valutatrade_hub.parser_service.storage import RatesStorage

        sample = {
            "EUR_USD": 1.08, "GBP_USD": 1.26, "RUB_USD": 0.011,
            "BTC_USD": 59300.0, "ETH_USD": 3720.0, "SOL_USD": 145.0,
        }
        now = iso_now()
        count = RatesStorage(self.database).save(
            {key: {"rate": value, "updated_at": now, "source": "DEMO"}
             for key, value in sample.items()},
            timestamp=now,
        )
        print(f"Загружено {count} учебных курсов DEMO. Это НЕ реальные рыночные данные.")

    def execute(self, line: str) -> bool:
        """Выполнить одну строку. Вернуть False для завершения оболочки."""
        try:
            parts = shlex.split(line)
            if not parts:
                return True
            command, *values = parts
            if command in ("exit", "quit"):
                print("До свидания!")
                return False
            if command == "help":
                print(HELP)
                return True
            if command == "currencies":
                for item in CURRENCY_REGISTRY.values():
                    print(item.get_display_info())
                return True
            if command == "logout":
                self.current_user_id = self.current_username = None
                print("Вы вышли из профиля")
                return True
            supported = {
                "register", "login", "show-portfolio", "deposit-demo", "buy", "sell",
                "get-rate", "update-rates", "show-rates", "demo-rates", "history", "scheduler",
            }
            if command not in supported:
                print(f"Неизвестная команда '{command}'. Введите help.")
                return True
            args = self._parse(command, values)
            if command == "register":
                user = self.service.register(args.username, args.password)
                print(f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}). Войдите: login")
            elif command == "login":
                user = self.service.login(args.username, args.password)
                self.current_user_id, self.current_username = user.user_id, user.username
                print(f"Вы вошли как '{user.username}'")
            elif command == "show-portfolio":
                user_id = self._require_login()
                portfolio, rows, total = self.service.portfolio_values(user_id, args.base)
                print(f"Портфель пользователя '{portfolio.user.username}' (база: {args.base.upper()}):")
                if not rows:
                    print("Портфель пока пуст. Для начала: deposit-demo --amount 10000")
                else:
                    for code, quantity, value in rows:
                        print(f"  {code}: {quantity:.4f} → {value:,.2f} {args.base.upper()}")
                    print(f"ИТОГО: {total:,.2f} {args.base.upper()}")
            elif command == "deposit-demo":
                result = self.service.deposit_demo(self._require_login(), args.amount)
                print(f"Добавлено {result.amount:.2f} виртуальных USD. Баланс: {result.after:.2f} USD")
            elif command == "buy":
                result = self.service.buy(self._require_login(), args.currency, args.amount)
                self._display_trade(result)
            elif command == "sell":
                result = self.service.sell(self._require_login(), args.currency, args.amount)
                self._display_trade(result)
            elif command == "get-rate":
                rate = self.rates.get_rate(args.from_code, args.to_code)
                print(f"Курс {rate.from_code}→{rate.to_code}: {rate.rate:.8f}")
                print(f"Обновлено: {rate.updated_at}; источник: {rate.source}")
                print(f"Обратный курс {rate.to_code}→{rate.from_code}: {1 / rate.rate:.8f}")
            elif command == "update-rates":
                self._update_rates(args.source)
            elif command == "show-rates":
                self._show_rates(args)
            elif command == "demo-rates":
                self._demo_rates()
            elif command == "history":
                portfolio = self.service.get_portfolio(self._require_login())
                if not portfolio.transactions:
                    print("История операций пуста")
                for entry in portfolio.transactions:
                    print(f"{entry['timestamp']} {entry['action']} "
                          f"{entry['amount']:.4f} {entry['currency']}")
            elif command == "scheduler":
                print(f"Запущен планировщик, интервал {args.interval} сек (Ctrl+C — стоп)")
                run_scheduler(args.interval)
        except CurrencyNotFoundError as exc:
            print(f"Ошибка: {exc}. Поддерживаемые коды: {', '.join(CURRENCY_REGISTRY)}.")
            print("Справка: help get-rate")
        except ApiRequestError as exc:
            print(f"Ошибка: {exc}. Проверьте сеть, ключ API или выполните update-rates.")
        except (ValutaTradeError, ValueError) as exc:
            print(f"Ошибка: {exc}")
        except SystemExit:
            print("Ошибка: неверные аргументы команды")
        except KeyboardInterrupt:
            print("\nОперация прервана")
        return True

    def run(self) -> None:
        """Интерактивная командная строка до exit или Ctrl+D."""
        print("ValutaTrade Hub — виртуальный валютный кошелёк (help — команды)")
        while True:
            try:
                line = input("valutatrade> ")
            except (EOFError, KeyboardInterrupt):
                print("\nДо свидания!")
                break
            if not self.execute(line):
                break


def main() -> None:
    """Точка входа для uv run valutatrade и python main.py."""
    configure_logging()
    console = Console()
    if len(sys.argv) > 1:
        # Одиночный вызов удобен для команд обновления/просмотра.
        # login не сохраняет авторизацию между разными процессами.
        console.execute(shlex.join(sys.argv[1:]))
    else:
        console.run()


if __name__ == "__main__":
    main()
