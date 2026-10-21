"""Простой последовательный планировщик обновления курсов (Ctrl+C — стоп)."""

import logging
import time

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.updater import RatesUpdater

logger = logging.getLogger("valutatrade_hub")


def run_scheduler(interval_seconds: int = 300) -> None:
    """Опрашивать API не чаще выбранного интервала."""
    if interval_seconds < 60:
        raise ValueError("Интервал обновления должен быть не меньше 60 секунд")
    updater = RatesUpdater()
    logger.info("Запуск автообновления курсов: интервал %s сек", interval_seconds)
    while True:
        try:
            updater.run_update()
        except ApiRequestError as exc:
            logger.error("Ошибка планового обновления курсов: %s", exc)
        time.sleep(interval_seconds)
