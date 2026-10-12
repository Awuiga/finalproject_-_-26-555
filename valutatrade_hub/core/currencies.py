"""Абстракция валют, наследники и простой реестр (фабрика)."""

from abc import ABC, abstractmethod

from .exceptions import CurrencyNotFoundError, ValidationError
from .utils import normalize_code


class Currency(ABC):
    """Контракт валюты с названием, кодом и строкой для интерфейса."""

    def __init__(self, name: str, code: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValidationError("Название валюты не может быть пустым")
        self.name = name.strip()
        self.code = normalize_code(code)

    @abstractmethod
    def get_display_info(self) -> str:
        """Вывести описание валюты, зависящее от её типа."""


class FiatCurrency(Currency):
    """Обычная валюта, выпущенная государством или валютной зоной."""

    def __init__(self, name: str, code: str, issuing_country: str) -> None:
        super().__init__(name, code)
        if not issuing_country.strip():
            raise ValidationError("Нужно указать страну/зону эмиссии")
        self.issuing_country = issuing_country

    def get_display_info(self) -> str:
        """Вернуть код, название и страну выпуска."""
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта с алгоритмом и оценкой капитализации."""

    def __init__(
        self, name: str, code: str, algorithm: str, market_cap: float
    ) -> None:
        super().__init__(name, code)
        if not algorithm.strip():
            raise ValidationError("Нужно указать алгоритм криптовалюты")
        if isinstance(market_cap, bool) or not isinstance(market_cap, (int, float)):
            raise ValidationError("Капитализация должна быть неотрицательным числом")
        if not 0 <= market_cap < float("inf"):
            raise ValidationError("Капитализация должна быть неотрицательным числом")
        self.algorithm = algorithm
        self.market_cap = float(market_cap)

    def get_display_info(self) -> str:
        """Вернуть код, название, алгоритм и компактную капитализацию."""
        mcap = f"{self.market_cap:.2e}".replace("e+", "e")
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {mcap})"
        )


CURRENCY_REGISTRY: dict[str, Currency] = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "GBP": FiatCurrency("Pound Sterling", "GBP", "United Kingdom"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    # Демо-значения капитализации не являются актуальными котировками.
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Proof of Stake", 4.20e11),
    "SOL": CryptoCurrency("Solana", "SOL", "Proof of History / PoS", 8.00e10),
}


def get_currency(code: str) -> Currency:
    """Вернуть объект валюты или CurrencyNotFoundError."""
    normalized = normalize_code(code)
    if normalized not in CURRENCY_REGISTRY:
        raise CurrencyNotFoundError(normalized)
    return CURRENCY_REGISTRY[normalized]
