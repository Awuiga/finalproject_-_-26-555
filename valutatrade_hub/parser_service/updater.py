"""Сбор курсов: отказ одного источника не блокирует остальные."""

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.utils import iso_now
from valutatrade_hub.parser_service.api_clients import (
    BaseApiClient,
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.storage import RatesStorage

logger = logging.getLogger("valutatrade_hub")


@dataclass
class UpdateResult:
    """Количество загруженных курсов и сообщения об ошибках источников."""

    count: int
    refreshed_at: str
    failures: list[str] = field(default_factory=list)


class RatesUpdater:
    """Оркестратор опроса API и сохранения пары снапшот + история."""

    def __init__(
        self,
        clients: Iterable[BaseApiClient] | None = None,
        storage: RatesStorage | None = None,
    ) -> None:
        self.clients = (
            list(clients)
            if clients is not None
            else [CoinGeckoClient(), ExchangeRateApiClient()]
        )
        self.storage = storage or RatesStorage()

    def run_update(self, source: str | None = None) -> UpdateResult:
        """Обновить из всех источников или выбранного; вернуть отчёт."""
        timestamp = iso_now()
        pairs: dict[str, dict] = {}
        failures = []
        logger.info("%s PARSER_START source=%s", timestamp, source or "all")
        for client in self.clients:
            normalized_name = client.source_name.lower().replace("-api", "")
            if source and source.lower() not in (
                normalized_name,
                client.source_name.lower(),
            ):
                continue
            try:
                fetched = client.fetch_rates()
                pairs.update(
                    {
                        code: {
                            "rate": rate,
                            "updated_at": timestamp,
                            "source": client.source_name,
                        }
                        for code, rate in fetched.items()
                    }
                )
                logger.info(
                    "%s PARSER_FETCH source=%r result=OK count=%s",
                    timestamp,
                    client.source_name,
                    len(fetched),
                )
            except ApiRequestError as exc:
                failures.append(f"{client.source_name}: {exc}")
                logger.error(
                    "%s PARSER_FETCH source=%r result=ERROR error=%r",
                    timestamp,
                    client.source_name,
                    str(exc),
                )
        if not pairs:
            reason = "; ".join(failures) if failures else "нет данных от источников"
            raise ApiRequestError(reason)
        count = self.storage.save(pairs, timestamp=timestamp)
        logger.info(
            "%s PARSER_FINISH count=%s failures=%s", timestamp, count, len(failures)
        )
        return UpdateResult(count=count, refreshed_at=timestamp, failures=failures)
