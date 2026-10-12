"""Центральные настройки Parser Service (без ключей в репозитории)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from valutatrade_hub.infra.settings import SettingsLoader

CRYPTO_ID_MAP = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}
FIAT_CURRENCIES = ("EUR", "GBP", "RUB")
CRYPTO_CURRENCIES = tuple(CRYPTO_ID_MAP)


@dataclass(frozen=True)
class ParserConfig:
    """Параметры HTTP-запросов и JSON-кэша."""

    exchange_api_key: str | None = field(
        default_factory=lambda: os.getenv("EXCHANGERATE_API_KEY")
    )
    coingecko_url: str = "https://api.coingecko.com/api/v3/simple/price"
    exchangerate_url: str = "https://v6.exchangerate-api.com/v6"
    base_currency: str = "USD"
    fiat_currencies: tuple[str, ...] = FIAT_CURRENCIES
    crypto_currencies: tuple[str, ...] = CRYPTO_CURRENCIES
    crypto_id_map: dict[str, str] = field(default_factory=lambda: dict(CRYPTO_ID_MAP))
    request_timeout: int = 10
    rates_file_path: Path = Path("data/rates.json")
    history_file_path: Path = Path("data/exchange_rates.json")

    @classmethod
    def from_settings(cls) -> "ParserConfig":
        """Получить параметры из SettingsLoader и окружения."""
        settings = SettingsLoader()
        return cls(
            base_currency=settings.get("base_currency"),
            request_timeout=int(settings.get("request_timeout")),
            rates_file_path=settings.file_path("rates.json"),
            history_file_path=settings.file_path("exchange_rates.json"),
        )
