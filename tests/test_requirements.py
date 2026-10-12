"""Дополнительные проверки требований итогового задания."""

from datetime import timedelta

import pytest

from valutatrade_hub.cli.interface import Console
from valutatrade_hub.core.currencies import Currency, CryptoCurrency, FiatCurrency, get_currency
from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError, ValidationError
from valutatrade_hub.core.models import User, Wallet
from valutatrade_hub.core.usecases import RateService, TradeService
from valutatrade_hub.core.utils import utc_now
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.parser_service.storage import RatesStorage


def test_singletons_share_identity():
    assert SettingsLoader() is SettingsLoader()
    assert DatabaseManager() is DatabaseManager()


def test_currency_abstract_and_display():
    with pytest.raises(TypeError):
        Currency('Example', 'EX')
    assert isinstance(get_currency('usd'), FiatCurrency)
    assert isinstance(get_currency('btc'), CryptoCurrency)
    assert 'Issuing:' in get_currency('USD').get_display_info()
    assert 'MCAP:' in get_currency('BTC').get_display_info()
    with pytest.raises(CurrencyNotFoundError):
        get_currency('ABC')
    with pytest.raises(ValidationError):
        FiatCurrency('', 'ZZ', 'Nowhere')


def test_password_not_public_and_salted():
    first = User(1, 'alice', password='1234')
    second = User(2, 'bob', password='1234')
    assert first.hashed_password != second.hashed_password
    assert first.verify_password('1234')
    assert not first.verify_password('wrong')
    assert not {'hashed_password', 'salt', 'password'} & first.get_user_info().keys()
    assert User.from_dict(first.to_dict()).verify_password('1234')


def test_wallet_validation():
    wallet = Wallet('USD')
    for amount in (-1, float('nan'), float('inf'), True):
        with pytest.raises(ValidationError):
            wallet.deposit(amount)
    with pytest.raises(ValidationError):
        wallet.balance = -1
    wallet.deposit(200)
    wallet.withdraw(50)
    assert wallet.balance == 150


def test_rate_reverse_cross_and_ttl():
    now = utc_now().isoformat()
    db = DatabaseManager()
    db.save_rates({'pairs': {
        'EUR_USD': {'rate': 1.25, 'updated_at': now, 'source': 'mock'},
        'BTC_USD': {'rate': 50000.0, 'updated_at': now, 'source': 'mock'},
    }, 'last_refresh': now})
    rates = RateService(db, auto_refresh=False)
    assert rates.get_rate('USD', 'BTC').rate == pytest.approx(1 / 50000)
    assert rates.get_rate('EUR', 'BTC').rate == pytest.approx(1.25 / 50000)
    assert rates.get_rate('USD', 'USD').rate == 1
    old = (utc_now() - timedelta(hours=1)).isoformat()
    db.save_rates({'pairs': {'EUR_USD': {'rate': 1.25, 'updated_at': old,
                                        'source': 'mock'}}, 'last_refresh': old})
    with pytest.raises(ApiRequestError, match='устарел'):
        rates.get_rate('EUR', 'USD')


def test_portfolio_persistence_and_buy_sell():
    db = DatabaseManager()
    now = utc_now().isoformat()
    db.save_rates({'pairs': {'BTC_USD': {'rate': 50000, 'updated_at': now,
                                        'source': 'mock'}}, 'last_refresh': now})
    trade = TradeService(db, RateService(db, auto_refresh=False))
    person = trade.register('alice', '1234')
    trade.deposit_demo(person.user_id, 10000)
    trade.buy(person.user_id, 'BTC', 0.1)
    result = trade.sell(person.user_id, 'BTC', 0.02)
    assert result.total == pytest.approx(1000)
    reloaded = trade.get_portfolio(person.user_id)
    assert reloaded.get_wallet('BTC').balance == pytest.approx(0.08)
    assert reloaded.get_wallet('USD').balance == pytest.approx(6000)
    assert len(reloaded.transactions) == 3


def test_storage_does_not_replace_newer_rate():
    db = DatabaseManager()
    now = utc_now()
    later = (now + timedelta(seconds=10)).isoformat()
    earlier = (now - timedelta(seconds=10)).isoformat()
    storage = RatesStorage(db)
    assert storage.save({'BTC_USD': {'rate': 50000, 'updated_at': later,
                                    'source': 'mock'}}) == 1
    assert storage.save({'BTC_USD': {'rate': 40000, 'updated_at': earlier,
                                    'source': 'mock'}}) == 0
    assert db.load_rates()['pairs']['BTC_USD']['rate'] == 50000
    assert len(db.read('exchange_rates.json', [])) == 1


def test_cli_help_and_auth(capsys):
    console = Console()
    for command in ('show-portfolio', 'buy --currency BTC --amount 1',
                    'sell --currency BTC --amount 1'):
        console.execute(command)
    assert capsys.readouterr().out.count('Сначала выполните login') == 3
    console.execute('help')
    out = capsys.readouterr().out
    for command in ('register', 'login', 'buy', 'sell', 'get-rate',
                    'update-rates', 'show-rates'):
        assert command in out
