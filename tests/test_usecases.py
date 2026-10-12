"""Интеграция сценариев с реальными временными JSON-файлами."""

import pytest

from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    AuthenticationError,
    CurrencyNotFoundError,
    InsufficientFundsError,
    ValidationError,
)
from valutatrade_hub.core.usecases import RateService, TradeService
from valutatrade_hub.core.utils import iso_now
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader


@pytest.fixture
def service():
    db = DatabaseManager()
    rates = RateService(db, auto_refresh=False)
    return TradeService(db, rates)


def load_demo_rates():
    now = iso_now()
    DatabaseManager().save_rates({
        "pairs": {
            "BTC_USD": {"rate": 50000.0, "updated_at": now, "source": "test"},
            "EUR_USD": {"rate": 1.2, "updated_at": now, "source": "test"},
        },
        "last_refresh": now,
    })


def test_registration_and_login(service):
    user = service.register("alice", "1234")
    assert user.user_id == 1
    assert service.login("alice", "1234").user_id == 1
    assert service.get_portfolio(1).wallets == {}
    with pytest.raises(AuthenticationError, match="занято"):
        service.register("ALICE", "9999")
    with pytest.raises(AuthenticationError, match="Неверный пароль"):
        service.login("alice", "wrong")


def test_full_buy_sell_usd_accounting(service):
    load_demo_rates()
    user = service.register("alice", "1234")
    service.deposit_demo(user.user_id, 10000)
    bought = service.buy(user.user_id, "btc", 0.1)
    assert bought.total == pytest.approx(5000)
    assert bought.usd_after == pytest.approx(5000)
    sold = service.sell(user.user_id, "BTC", 0.04)
    assert sold.usd_after == pytest.approx(7000)
    assert sold.after == pytest.approx(0.06)
    portfolio, rows, total = service.portfolio_values(user.user_id)
    assert total == pytest.approx(10000)
    assert len(rows) == 2
    assert len(portfolio.transactions) == 3
    assert len(DatabaseManager().load_portfolios()) == 1


def test_buy_rejects_no_money_without_creating_wallet(service):
    load_demo_rates()
    user = service.register("alice", "1234")
    with pytest.raises(InsufficientFundsError):
        service.buy(user.user_id, "BTC", 0.1)
    assert service.get_portfolio(user.user_id).wallets == {}


def test_sell_rejects_insufficient_funds(service):
    load_demo_rates()
    user = service.register("alice", "1234")
    service.deposit_demo(user.user_id, 10000)
    service.buy(user.user_id, "BTC", 0.1)
    with pytest.raises(InsufficientFundsError):
        service.sell(user.user_id, "BTC", 0.5)
    assert service.get_portfolio(user.user_id).get_wallet("BTC").balance == 0.1


def test_rates_inverse_cross_and_invalid(service):
    load_demo_rates()
    rates = service.rates
    assert rates.get_rate("usd", "BTC").rate == pytest.approx(1 / 50000)
    assert rates.get_rate("EUR", "BTC").rate == pytest.approx(1.2 / 50000)
    assert rates.get_rate("USD", "USD").rate == 1.0
    with pytest.raises(CurrencyNotFoundError):
        rates.get_rate("XYZ", "USD")
    with pytest.raises(ApiRequestError):
        rates.get_rate("ETH", "USD")


def test_old_rates_and_invalid_amount(service):
    load_demo_rates()
    SettingsLoader()._config["rates_ttl_seconds"] = -1
    with pytest.raises(ApiRequestError, match="устарел"):
        service.rates.get_rate("BTC", "USD")
    with pytest.raises(ValidationError):
        service.deposit_demo(1, -1)
