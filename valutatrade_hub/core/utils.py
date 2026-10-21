"""Проверки входных значений и вспомогательные функции."""

import math
from datetime import UTC, datetime

from .exceptions import ValidationError


def validate_amount(value: object) -> float:
    """Вернуть положительное конечное число или выбросить ValidationError."""
    if isinstance(value, bool):
        raise ValidationError("'amount' должен быть положительным числом")
    try:
        amount = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'amount' должен быть положительным числом") from exc
    if not math.isfinite(amount) or amount <= 0:
        raise ValidationError("'amount' должен быть положительным числом")
    return amount


def normalize_code(value: object) -> str:
    """Проверить код (2–5 букв A-Z) и перевести в верхний регистр."""
    if not isinstance(value, str):
        raise ValidationError("Код валюты должен быть строкой из 2–5 латинских букв")
    code = value.strip().upper()
    if not 2 <= len(code) <= 5 or not code.isascii() or not code.isalpha():
        raise ValidationError("Код валюты должен состоять из 2–5 латинских букв")
    return code


def utc_now() -> datetime:
    """Текущее время в UTC."""
    return datetime.now(UTC)


def iso_now() -> str:
    """Текущая дата/время в формате ISO 8601 с UTC."""
    return utc_now().isoformat(timespec="seconds")


def parse_datetime(value: str) -> datetime:
    """Прочитать ISO-дату; старые даты без зоны считать временем UTC."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
