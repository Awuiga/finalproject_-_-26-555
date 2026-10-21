"""Логирование действий с ротацией по размеру файлов."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from valutatrade_hub.infra.settings import SettingsLoader

LOGGER_NAME = "valutatrade_hub"


def configure_logging() -> logging.Logger:
    """Настроить один файловый обработчик с ротацией, без дублирования записей."""
    settings = SettingsLoader()
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(str(settings.get("log_level", "INFO")).upper())
    if logger.handlers:
        return logger
    logs_dir = Path(settings.get("logs_dir"))
    logs_dir.mkdir(parents=True, exist_ok=True)
    fmt = "%(levelname)s %(message)s"  # В записи уже есть ISO-время.
    formatter = logging.Formatter(fmt)
    rotating = RotatingFileHandler(
        logs_dir / "actions.log",
        maxBytes=int(settings.get("log_max_bytes")),
        backupCount=int(settings.get("log_backup_count")),
        encoding="utf-8",
    )
    rotating.setFormatter(formatter)
    logger.addHandler(rotating)
    logger.propagate = False
    return logger
