"""Объекты пользователя, валютного кошелька и портфеля."""

import hashlib
import secrets
from collections.abc import Callable
from datetime import datetime

from .currencies import get_currency
from .exceptions import InsufficientFundsError, ValidationError
from .utils import iso_now, normalize_code, parse_datetime, validate_amount


class User:
    """Пользователь с закрытыми учетными полями и хешем пароля с солью."""

    def __init__(
        self,
        user_id: int,
        username: str,
        *,
        password: str | None = None,
        hashed_password: str | None = None,
        salt: str | None = None,
        registration_date: datetime | str | None = None,
    ) -> None:
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
            raise ValidationError(
                "Идентификатор пользователя должен быть положительным"
            )
        self._user_id = user_id
        self._username = ""
        self.username = username
        self._hashed_password = ""
        self._salt = ""
        if password is not None:
            self.change_password(password)
        elif hashed_password and salt:
            self._hashed_password = hashed_password
            self._salt = salt
        else:
            raise ValidationError("Нужен пароль или сохранённые хеш и соль")
        self._registration_date = (
            parse_datetime(registration_date)
            if isinstance(registration_date, str)
            else registration_date
        ) or parse_datetime(iso_now())

    @property
    def user_id(self) -> int:
        """Неизменяемый идентификатор пользователя."""
        return self._user_id

    @property
    def username(self) -> str:
        """Имя пользователя."""
        return self._username

    @username.setter
    def username(self, name: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValidationError("Имя пользователя не может быть пустым")
        self._username = name.strip()

    @property
    def hashed_password(self) -> str:
        """Хеш для сериализации, никогда не показывать в CLI."""
        return self._hashed_password

    @property
    def salt(self) -> str:
        """Соль для сохранения в JSON."""
        return self._salt

    @property
    def registration_date(self) -> datetime:
        """Дата регистрации (UTC)."""
        return self._registration_date

    def change_password(self, new_password: str) -> None:
        """Создать соль и хеш SHA-256 (учебный пример, не для реальных паролей)."""
        if not isinstance(new_password, str) or len(new_password) < 4:
            raise ValidationError("Пароль должен быть не короче 4 символов")
        salt = secrets.token_hex(16)
        hashed = hashlib.sha256((salt + new_password).encode("utf-8")).hexdigest()
        self._salt = salt
        self._hashed_password = hashed

    def verify_password(self, password: str) -> bool:
        """Сравнить хеши без уязвимого простого сравнения строк."""
        if not isinstance(password, str):
            return False
        expected = hashlib.sha256((self._salt + password).encode("utf-8")).hexdigest()
        return secrets.compare_digest(expected, self._hashed_password)

    def get_user_info(self) -> dict[str, object]:
        """Вернуть публичные данные без хеша, соли и пароля."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def to_dict(self) -> dict[str, object]:
        """Сериализовать пользователя для локального JSON-хранилища."""
        return {
            **self.get_user_info(),
            "hashed_password": self._hashed_password,
            "salt": self._salt,
        }

    @classmethod
    def from_dict(cls, record: dict) -> "User":
        """Восстановить пользователя из JSON без смены соли."""
        return cls(**record)


class Wallet:
    """Кошелёк одной валюты; баланс никогда не может быть отрицательным."""

    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        self.currency_code = get_currency(normalize_code(currency_code)).code
        self._balance = 0.0
        self.balance = balance

    @property
    def balance(self) -> float:
        """Текущий остаток валюты."""
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError("Баланс должен быть числом, не меньше нуля")
        if not 0 <= value < float("inf"):
            raise ValidationError("Баланс должен быть числом, не меньше нуля")
        self._balance = float(value)

    def deposit(self, amount: float) -> None:
        """Зачислить положительное количество валюты."""
        self.balance = self.balance + validate_amount(amount)

    def withdraw(self, amount: float) -> None:
        """Списать сумму или выбросить InsufficientFundsError."""
        quantity = validate_amount(amount)
        if self._balance + 1e-10 < quantity:
            raise InsufficientFundsError(self._balance, quantity, self.currency_code)
        self.balance = max(0.0, self._balance - quantity)

    def get_balance_info(self) -> str:
        """Человекочитаемый баланс с 4 знаками после запятой."""
        return f"{self.currency_code}: {self._balance:.4f}"

    def to_dict(self) -> dict:
        """Вернуть данные для JSON."""
        return {"currency_code": self.currency_code, "balance": self._balance}


class Portfolio:
    """Набор кошельков, принадлежащих одному пользователю."""

    def __init__(
        self,
        user: User,
        wallets: dict[str, Wallet] | None = None,
        transactions: list[dict] | None = None,
    ) -> None:
        self._user = user
        self._wallets = dict(wallets or {})
        self._transactions = list(transactions or [])

    @property
    def user(self) -> User:
        """Владелец портфеля (без сеттера)."""
        return self._user

    @property
    def wallets(self) -> dict[str, Wallet]:
        """Копия словаря: нельзя напрямую менять набор кошельков извне."""
        return dict(self._wallets)

    @property
    def transactions(self) -> list[dict]:
        """Копия истории виртуальных операций."""
        return [dict(item) for item in self._transactions]

    def add_currency(self, currency_code: str) -> Wallet:
        """Добавить пустой кошелёк или вернуть уже существующий."""
        code = get_currency(currency_code).code
        if code not in self._wallets:
            self._wallets[code] = Wallet(code)
        return self._wallets[code]

    def get_wallet(self, currency_code: str) -> Wallet | None:
        """Найти кошелёк пользователя по коду."""
        code = get_currency(currency_code).code
        return self._wallets.get(code)

    def record_transaction(self, data: dict) -> None:
        """Добавить запись в историю операций."""
        self._transactions.append(dict(data))

    def get_total_value(
        self,
        base_currency: str = "USD",
        rate_provider: Callable[[str, str], float] | None = None,
    ) -> float:
        """Посчитать стоимость всех кошельков через предоставленный источник курсов."""
        base = get_currency(base_currency).code
        total = 0.0
        for code, wallet in self._wallets.items():
            if wallet.balance == 0:
                continue
            if code == base:
                total += wallet.balance
            elif rate_provider is not None:
                total += wallet.balance * rate_provider(code, base)
            else:
                raise ValidationError("Нужен источник курсов для конвертации")
        return total

    def to_dict(self) -> dict:
        """Сериализовать портфель со всеми кошельками и историей."""
        return {
            "user_id": self._user.user_id,
            "wallets": {
                code: wallet.to_dict() for code, wallet in self._wallets.items()
            },
            "transactions": self.transactions,
        }

    @classmethod
    def from_dict(cls, user: User, record: dict) -> "Portfolio":
        """Восстановить портфель из записи хранилища."""
        wallets = {
            code: Wallet(code, entry["balance"])
            for code, entry in record.get("wallets", {}).items()
        }
        return cls(user, wallets, record.get("transactions", []))
