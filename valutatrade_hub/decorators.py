"""Декоратор журналирования пользовательских операций."""

import functools
import inspect
import logging
from collections.abc import Callable
from typing import Any

from valutatrade_hub.core.utils import iso_now

logger = logging.getLogger("valutatrade_hub")


def log_action(action: str, *, verbose: bool = False) -> Callable:
    """Зафиксировать OK/ERROR, но оставить исключения вызывающей стороне."""

    def decorator(function: Callable) -> Callable:
        signature = inspect.signature(function)

        @functools.wraps(function)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = bound.arguments
            fields: dict[str, Any] = {
                "timestamp": iso_now(),
                "action": action.upper(),
                "user_id": arguments.get("user_id", "-"),
                "username": arguments.get("username", "-"),
                "currency_code": arguments.get("currency_code", "-"),
                "amount": arguments.get("amount", "-"),
                "base": "USD",
            }
            try:
                result = function(*args, **kwargs)
            except Exception as exc:
                fields["result"] = "ERROR"
                fields["error_type"] = type(exc).__name__
                fields["error_message"] = str(exc)
                logger.info(" ".join(f"{k}={v!r}" for k, v in fields.items()))
                raise
            fields["result"] = "OK"
            if hasattr(result, "rate"):
                fields["rate"] = result.rate
            if verbose and hasattr(result, "before"):
                fields["wallet_before"] = result.before
                fields["wallet_after"] = result.after
                if hasattr(result, "usd_before"):
                    fields["usd_before"] = result.usd_before
                    fields["usd_after"] = result.usd_after
            logger.info(" ".join(f"{k}={v!r}" for k, v in fields.items()))
            return result

        return wrapper

    return decorator
