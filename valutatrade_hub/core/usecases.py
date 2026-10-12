"""Сценарии приложения; CLI здесь не занимается бизнес-логикой."""

import logging
from dataclasses import dataclass
from typing import Any

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    AuthenticationError,
    InsufficientFundsError,
    ValidationError,
)
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.core.utils import iso_now, parse_datetime, utc_now, validate_amount
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader

logger = logging.getLogger("valutatrade_hub")


@dataclass(frozen=True)
class RateResult:
    """Один курс, время исходных данных и источники."""

    from_code: str
    to_code: str
    rate: float
    updated_at: str
    source: str


@dataclass(frozen=True)
class TradeResult:
    """Итог покупки или продажи виртуальной валюты."""

    action: str
    currency_code: str
    amount: float
    rate: float
    base: str
    total: float
    before: float
    after: float
    usd_before: float
    usd_after: float


class RateService:
    """Курсы к USD с обратными и кросс-курсами через USD."""

    def __init__(
        self,
        database: DatabaseManager | None = None,
        settings: SettingsLoader | None = None,
        *,
        auto_refresh: bool = True,
    ) -> None:
        self.database = database or DatabaseManager()
        self.settings = settings or SettingsLoader()
        self.auto_refresh = auto_refresh

    def _fresh_pair(self, pair: str, pairs: dict) -> dict:
        """Найти запись и проверить срок годности именно этой пары."""
        if pair not in pairs:
            raise ApiRequestError(f"курс {pair.replace('_', '→')} отсутствует в кеше")
        entry = pairs[pair]
        age = (utc_now() - parse_datetime(entry["updated_at"])).total_seconds()
        ttl = int(self.settings.get("rates_ttl_seconds", 300))
        if age > ttl or age < -60:
            raise ApiRequestError(f"курс {pair.replace('_', '→')} устарел")
        rate = entry.get("rate")
        if isinstance(rate, bool) or not isinstance(rate, (int, float)):
            raise ApiRequestError(f"некорректный курс для {pair}")
        if not 0 < rate < float("inf"):
            raise ApiRequestError(f"некорректный курс для {pair}")
        return entry

    def _calculate(self, from_code: str, to_code: str) -> RateResult:
        pairs = self.database.load_rates().get("pairs", {})
        direct = f"{from_code}_{to_code}"
        inverse = f"{to_code}_{from_code}"
        if direct in pairs:
            entry = self._fresh_pair(direct, pairs)
            return RateResult(
                from_code, to_code, float(entry["rate"]),
                entry["updated_at"], entry.get("source", "cache"),
            )
        if inverse in pairs:
            entry = self._fresh_pair(inverse, pairs)
            return RateResult(
                from_code, to_code, 1 / float(entry["rate"]),
                entry["updated_at"], entry.get("source", "cache (inverse)"),
            )

        # Для EUR→BTC используем EUR→USD / BTC→USD.
        def usd_value(code: str) -> tuple[float, str, str]:
            if code == "USD":
                return 1.0, iso_now(), "USD"
            entry = self._fresh_pair(f"{code}_USD", pairs)
            return float(entry["rate"]), entry["updated_at"], entry["source"]

        left, left_date, left_source = usd_value(from_code)
        right, right_date, right_source = usd_value(to_code)
        updated = min(parse_datetime(left_date), parse_datetime(right_date)).isoformat()
        return RateResult(
            from_code, to_code, left / right, updated,
            "+".join(sorted({left_source, right_source} - {"USD"})),
        )

    def get_rate(self, from_code: str, to_code: str) -> RateResult:
        """Получить курс; при отсутствии/старении попытаться обновить кеш."""
        origin = get_currency(from_code).code
        target = get_currency(to_code).code
        if origin == target:
            return RateResult(origin, target, 1.0, iso_now(), "identity")
        try:
            return self._calculate(origin, target)
        except ApiRequestError as first_error:
            if not self.auto_refresh:
                raise
            # Импорт внутри метода предотвращает цикл зависимостей.
            from valutatrade_hub.parser_service.updater import RatesUpdater

            try:
                RatesUpdater().run_update()
                return self._calculate(origin, target)
            except ApiRequestError as refresh_error:
                raise ApiRequestError(
                    f"{first_error.reason}; обновление не удалось: {refresh_error.reason}"
                ) from refresh_error


class TradeService:
    """Регистрация, вход, портфель, торговля и demo-пополнение."""

    def __init__(
        self,
        database: DatabaseManager | None = None,
        rate_service: RateService | None = None,
    ) -> None:
        self.database = database or DatabaseManager()
        self.rates = rate_service or RateService(database=self.database)

    @log_action("REGISTER")
    def register(self, username: str, password: str) -> User:
        """Зарегистрировать нового пользователя и создать пустой портфель."""
        if not isinstance(username, str) or not username.strip():
            raise ValidationError("Имя пользователя не может быть пустым")
        username = username.strip()

        def add_user(users: list[dict]) -> User:
            if any(item["username"].casefold() == username.casefold() for item in users):
                raise AuthenticationError(f"Имя пользователя '{username}' уже занято")
            new_id = max((item["user_id"] for item in users), default=0) + 1
            new_user = User(new_id, username, password=password)
            users.append(new_user.to_dict())
            return new_user

        user = self.database.transaction("users.json", [], add_user)

        def add_portfolio(portfolios: list[dict]) -> None:
            if not any(row["user_id"] == user.user_id for row in portfolios):
                portfolios.append(Portfolio(user).to_dict())

        self.database.transaction("portfolios.json", [], add_portfolio)
        return user

    @log_action("LOGIN")
    def login(self, username: str, password: str) -> User:
        """Проверить существование пользователя и его пароль."""
        users = self.database.load_users()
        record = next((r for r in users if r["username"] == username), None)
        if record is None:
            raise AuthenticationError(f"Пользователь '{username}' не найден")
        user = User.from_dict(record)
        if not user.verify_password(password):
            raise AuthenticationError("Неверный пароль")
        return user

    def _load_user(self, user_id: int) -> User:
        user_record = next(
            (r for r in self.database.load_users() if r["user_id"] == user_id), None
        )
        if user_record is None:
            raise AuthenticationError("Пользователь не найден. Сначала выполните login")
        return User.from_dict(user_record)

    def get_portfolio(self, user_id: int) -> Portfolio:
        """Загрузить портфель для известного пользователя."""
        user = self._load_user(user_id)
        record = next(
            (r for r in self.database.load_portfolios() if r["user_id"] == user_id),
            None,
        )
        return Portfolio.from_dict(user, record) if record else Portfolio(user)

    def portfolio_values(
        self, user_id: int, base: str = "USD"
    ) -> tuple[Portfolio, list[tuple[str, float, float]], float]:
        """Вернуть портфель, стоимость его кошельков и общую сумму."""
        base = get_currency(base).code
        portfolio = self.get_portfolio(user_id)
        rows = []
        for code, wallet in sorted(portfolio.wallets.items()):
            rate = self.rates.get_rate(code, base).rate if wallet.balance else 0.0
            rows.append((code, wallet.balance, wallet.balance * rate))
        return portfolio, rows, sum(row[2] for row in rows)

    def _modify_portfolio(self, user_id: int, fn: Any) -> Any:
        """Одна атомарная операция над записью портфеля в portfolios.json."""
        user = self._load_user(user_id)

        def modify(portfolios: list[dict]) -> Any:
            index = next(
                (i for i, record in enumerate(portfolios)
                 if record["user_id"] == user_id),
                None,
            )
            record = portfolios[index] if index is not None else {"wallets": {}}
            portfolio = Portfolio.from_dict(user, record)
            result = fn(portfolio)
            if index is None:
                portfolios.append(portfolio.to_dict())
            else:
                portfolios[index] = portfolio.to_dict()
            return result

        return self.database.transaction("portfolios.json", [], modify)

    @log_action("DEMO_DEPOSIT", verbose=True)
    def deposit_demo(self, user_id: int, amount: float) -> TradeResult:
        """Пополнить USD фиктивными деньгами (реальные деньги не используются)."""
        amount = validate_amount(amount)

        def apply(portfolio: Portfolio) -> TradeResult:
            usd = portfolio.add_currency("USD")
            before = usd.balance
            usd.deposit(amount)
            portfolio.record_transaction(
                {"action": "DEMO_DEPOSIT", "currency": "USD", "amount": amount,
                 "timestamp": iso_now()}
            )
            return TradeResult(
                "DEMO_DEPOSIT", "USD", amount, 1.0, "USD", amount,
                before, usd.balance, before, usd.balance,
            )

        return self._modify_portfolio(user_id, apply)

    @log_action("BUY", verbose=True)
    def buy(self, user_id: int, currency_code: str, amount: float) -> TradeResult:
        """Купить валюту за USD: списать USD и добавить единицы валюты."""
        currency_code = get_currency(currency_code).code
        amount = validate_amount(amount)
        if currency_code == "USD":
            raise ValidationError("Покупка USD за USD не поддерживается")
        rate = self.rates.get_rate(currency_code, "USD").rate
        cost = amount * rate

        def apply(portfolio: Portfolio) -> TradeResult:
            usd = portfolio.get_wallet("USD")
            usd_balance = usd.balance if usd else 0.0
            if usd_balance + 1e-10 < cost:
                raise InsufficientFundsError(usd_balance, cost, "USD")
            target = portfolio.add_currency(currency_code)
            before, usd_before = target.balance, usd.balance
            usd.withdraw(cost)
            target.deposit(amount)
            portfolio.record_transaction(
                {"action": "BUY", "currency": currency_code, "amount": amount,
                 "rate": rate, "usd_total": cost, "timestamp": iso_now()}
            )
            return TradeResult(
                "BUY", currency_code, amount, rate, "USD", cost,
                before, target.balance, usd_before, usd.balance,
            )

        return self._modify_portfolio(user_id, apply)

    @log_action("SELL", verbose=True)
    def sell(self, user_id: int, currency_code: str, amount: float) -> TradeResult:
        """Продать валюту за USD; проверить доступный остаток."""
        currency_code = get_currency(currency_code).code
        amount = validate_amount(amount)
        if currency_code == "USD":
            raise ValidationError("Продажа USD за USD не поддерживается")
        rate = self.rates.get_rate(currency_code, "USD").rate
        revenue = amount * rate

        def apply(portfolio: Portfolio) -> TradeResult:
            wallet = portfolio.get_wallet(currency_code)
            if wallet is None:
                raise ValidationError(
                    f"У вас нет кошелька '{currency_code}'. "
                    "Он создаётся при первой покупке."
                )
            before = wallet.balance
            wallet.withdraw(amount)
            usd = portfolio.add_currency("USD")
            usd_before = usd.balance
            usd.deposit(revenue)
            portfolio.record_transaction(
                {"action": "SELL", "currency": currency_code, "amount": amount,
                 "rate": rate, "usd_total": revenue, "timestamp": iso_now()}
            )
            return TradeResult(
                "SELL", currency_code, amount, rate, "USD", revenue,
                before, wallet.balance, usd_before, usd.balance,
            )

        return self._modify_portfolio(user_id, apply)
