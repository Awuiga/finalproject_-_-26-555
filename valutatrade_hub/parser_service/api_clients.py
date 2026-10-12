"""Клиенты для двух реальных источников фиатных и криптовалютных курсов."""

import logging
import math
from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig

logger = logging.getLogger("valutatrade_hub")


def _check_response(response: requests.Response) -> dict:
    """Проверить HTTP-ответ и декодировать JSON без выдачи секретного URL."""
    if response.status_code == 429:
        raise ApiRequestError("превышен лимит запросов (HTTP 429)")
    if response.status_code in (401, 403):
        raise ApiRequestError("неверный API-ключ или нет доступа (HTTP 401/403)")
    if not 200 <= response.status_code < 300:
        raise ApiRequestError(f"сервер ответил HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise ApiRequestError("API вернул некорректный JSON") from exc
    if not isinstance(payload, dict):
        raise ApiRequestError("API вернул неожиданный формат")
    return payload


def _valid_rate(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ApiRequestError("курс не является числом")
    rate = float(value)
    if not math.isfinite(rate) or rate <= 0:
        raise ApiRequestError("курс должен быть положительным конечным числом")
    return rate


class BaseApiClient(ABC):
    """Единый интерфейс: пары вида BTC_USD → значение курса."""

    source_name: str

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Получить нормализованные обменные курсы."""


class CoinGeckoClient(BaseApiClient):
    """Курсы криптовалют в USD из CoinGecko Simple Price API."""

    source_name = "CoinGecko"

    def __init__(self, config: ParserConfig | None = None) -> None:
        self.config = config or ParserConfig.from_settings()

    def fetch_rates(self) -> dict[str, float]:
        """Получить BTC/ETH/SOL → USD и проверить значения."""
        ids = [self.config.crypto_id_map[c] for c in self.config.crypto_currencies]
        params = {"ids": ",".join(ids), "vs_currencies": self.config.base_currency.lower()}
        try:
            response = requests.get(
                self.config.coingecko_url, params=params,
                timeout=self.config.request_timeout,
            )
            data = _check_response(response)
        except requests.RequestException as exc:
            raise ApiRequestError(f"CoinGecko: ошибка сети ({type(exc).__name__})") from exc
        result = {}
        for ticker in self.config.crypto_currencies:
            coin_id = self.config.crypto_id_map[ticker]
            try:
                raw_rate = data[coin_id][self.config.base_currency.lower()]
            except (KeyError, TypeError) as exc:
                raise ApiRequestError(f"CoinGecko: нет курса для {ticker}") from exc
            result[f"{ticker}_{self.config.base_currency}"] = _valid_rate(raw_rate)
        logger.debug("CoinGecko: получено %s курсов", len(result))
        return result


class ExchangeRateApiClient(BaseApiClient):
    """Курсы фиатных валют из ExchangeRate-API."""

    source_name = "ExchangeRate-API"

    def __init__(self, config: ParserConfig | None = None) -> None:
        self.config = config or ParserConfig.from_settings()

    def fetch_rates(self) -> dict[str, float]:
        """Инвертировать USD→EUR в EUR→USD для единого представления."""
        key = self.config.exchange_api_key
        if not key or key == "replace_me":
            raise ApiRequestError("ExchangeRate-API: задайте EXCHANGERATE_API_KEY")
        url = f"{self.config.exchangerate_url}/{key}/latest/{self.config.base_currency}"
        try:
            response = requests.get(url, timeout=self.config.request_timeout)
            data = _check_response(response)
        except requests.RequestException as exc:
            raise ApiRequestError(
                f"ExchangeRate-API: ошибка сети ({type(exc).__name__})"
            ) from exc
        if data.get("result") != "success":
            raise ApiRequestError("ExchangeRate-API вернул ошибку результата")
        # Реальное API использует conversion_rates; rates — вариант из учебного ТЗ.
        rates = data.get("conversion_rates", data.get("rates"))
        if not isinstance(rates, dict):
            raise ApiRequestError("ExchangeRate-API: нет словаря conversion_rates")
        result = {}
        for ticker in self.config.fiat_currencies:
            if ticker not in rates:
                raise ApiRequestError(f"ExchangeRate-API: нет курса для {ticker}")
            # Ответ с базой USD: 1 USD = N EUR; нам нужно 1 EUR = (1/N) USD.
            result[f"{ticker}_{self.config.base_currency}"] = (
                1.0 / _valid_rate(rates[ticker])
            )
        logger.debug("ExchangeRate-API: получено %s курсов", len(result))
        return result
