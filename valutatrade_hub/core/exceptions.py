"""Ошибки, понятные бизнес-логике и консольному интерфейсу."""


class ValutaTradeError(Exception):
    """Базовый класс ожидаемых ошибок приложения."""


class InsufficientFundsError(ValutaTradeError):
    """Операция потребовала больше средств, чем доступно."""

    def __init__(self, available: float, required: float, code: str) -> None:
        self.available = available
        self.required = required
        self.code = code
        super().__init__(
            f"Недостаточно средств: доступно {available:.4f} {code}, "
            f"требуется {required:.4f} {code}"
        )


class CurrencyNotFoundError(ValutaTradeError):
    """Код валюты отсутствует в реестре."""

    def __init__(self, code: str) -> None:
        self.code = str(code)
        super().__init__(f"Неизвестная валюта '{self.code}'")


class ApiRequestError(ValutaTradeError):
    """Внешний источник данных недоступен или вернул ошибку."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")


class ValidationError(ValutaTradeError):
    """Значение не проходит доменную проверку."""


class AuthenticationError(ValutaTradeError):
    """Регистрация или вход завершились неуспешно."""


class DataStorageError(ValutaTradeError):
    """Ошибка чтения или записи JSON-хранилища."""
