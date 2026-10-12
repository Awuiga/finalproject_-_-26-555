"""Тесты валют, пользователей и кошельков."""

import pytest

from valutatrade_hub.core.currencies import CryptoCurrency, FiatCurrency, get_currency
from valutatrade_hub.core.exceptions import (
    CurrencyNotFoundError,
    InsufficientFundsError,
    ValidationError,
)
from valutatrade_hub.core.models import Portfolio, User, Wallet


def test_user_password_salt_and_serialization():
    user = User(1, "alice", password="secret!")
    assert user.verify_password("secret!")
    assert not user.verify_password("wrong")
    assert "secret!" not in str(user.to_dict())
    assert "hashed_password" not in user.get_user_info()
    clone = User.from_dict(user.to_dict())
    assert clone.verify_password("secret!")
    assert clone.registration_date == user.registration_date
    user.change_password("another-secret")
    assert not user.verify_password("secret!")
    assert user.verify_password("another-secret")


def test_user_validation():
    with pytest.raises(ValidationError, match="короче 4"):
        User(1, "john", password="123")
    with pytest.raises(ValidationError, match="Имя"):
        User(1, " ", password="long")


def test_wallet_balance_and_withdraw():
    wallet = Wallet("btc")
    wallet.deposit(0.5)
    wallet.withdraw(0.2)
    assert wallet.balance == pytest.approx(0.3)
    with pytest.raises(InsufficientFundsError):
        wallet.withdraw(0.4)
    with pytest.raises(ValidationError):
        wallet.balance = -5
    with pytest.raises(ValidationError):
        wallet.deposit(float("nan"))
    with pytest.raises(ValidationError):
        wallet.deposit(True)


def test_portfolio_unique_wallets_copy_and_total():
    user = User(1, "alice", password="1234")
    portfolio = Portfolio(user)
    btc = portfolio.add_currency("btc")
    assert portfolio.add_currency("BTC") is btc
    btc.deposit(2)
    copy = portfolio.wallets
    copy.pop("BTC")
    assert portfolio.get_wallet("BTC") is btc
    assert portfolio.get_total_value(rate_provider=lambda c, base: 5) == 10
    restored = Portfolio.from_dict(user, portfolio.to_dict())
    assert restored.get_wallet("BTC").balance == 2


def test_currency_polymorphism_and_not_found():
    assert isinstance(get_currency("usd"), FiatCurrency)
    assert isinstance(get_currency("btc"), CryptoCurrency)
    assert "Issuing:" in get_currency("USD").get_display_info()
    assert "Algo:" in get_currency("BTC").get_display_info()
    with pytest.raises(CurrencyNotFoundError, match="ABC"):
        get_currency("abc")
