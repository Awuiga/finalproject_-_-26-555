"""Проверка HTTP-клиентов без интернета: requests.get подменён фиктивным ответом."""

from dataclasses import replace

import pytest

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater


class Response:
    """Синтетический объект, совместимый с requests.Response для теста."""

    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code

    def json(self):
        return self.data


def test_coingecko_client(monkeypatch):
    payload = {"bitcoin": {"usd": 59300.0}, "ethereum": {"usd": 3700},
               "solana": {"usd": 145.0}}
    monkeypatch.setattr("requests.get", lambda *a, **kw: Response(payload))
    result = CoinGeckoClient().fetch_rates()
    assert result["BTC_USD"] == 59300.0
    assert len(result) == 3


def test_exchange_rate_api_inverts_usd_rates(monkeypatch):
    payload = {
        "result": "success",
        "conversion_rates": {"EUR": 0.8, "GBP": 0.7, "RUB": 100},
    }
    monkeypatch.setattr("requests.get", lambda *a, **kw: Response(payload))
    config = replace(ParserConfig(), exchange_api_key="fake_test_key")
    result = ExchangeRateApiClient(config).fetch_rates()
    assert result["EUR_USD"] == pytest.approx(1.25)
    assert result["RUB_USD"] == pytest.approx(0.01)


def test_api_429_is_domain_error(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **kw: Response({}, 429))
    with pytest.raises(ApiRequestError, match="429"):
        CoinGeckoClient().fetch_rates()


def test_updater_partial_success_and_history(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **kw: Response({
        "bitcoin": {"usd": 59300}, "ethereum": {"usd": 3720},
        "solana": {"usd": 145},
    }))
    result = RatesUpdater().run_update()
    assert result.count == 3
    assert len(result.failures) == 1  # Не задан ключ второго источника.
    db = DatabaseManager()
    assert len(db.load_rates()["pairs"]) == 3
    assert len(db.read("exchange_rates.json", [])) == 3
    RatesStorage(db).save(db.load_rates()["pairs"], timestamp=result.refreshed_at)
    assert len(db.read("exchange_rates.json", [])) == 3
