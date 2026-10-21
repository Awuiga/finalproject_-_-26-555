"""Конфигурация приложения: единственный экземпляр SettingsLoader."""

import os
import tomllib
from pathlib import Path
from threading import Lock
from typing import Any

from valutatrade_hub.core.exceptions import DataStorageError


class SettingsLoader:
    """Singleton через __new__: короче и понятнее собственного метакласса."""

    _instance: "SettingsLoader | None" = None
    _instance_lock = Lock()

    def __new__(cls) -> "SettingsLoader":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if not self._initialized:
            self._config: dict[str, Any] = {}
            self.reload()
            self._initialized = True

    def reload(self) -> None:
        """Повторно прочитать настройки из pyproject.toml и окружения."""
        root = Path(__file__).resolve().parents[2]
        project_config = root / "pyproject.toml"
        config: dict[str, Any] = {
            "data_dir": "data",
            "logs_dir": "logs",
            "rates_ttl_seconds": 300,
            "base_currency": "USD",
            "log_format": "text",
            "log_level": "INFO",
            "log_max_bytes": 1_048_576,
            "log_backup_count": 3,
            "request_timeout": 10,
        }
        if project_config.is_file():
            try:
                with project_config.open("rb") as stream:
                    config.update(
                        tomllib.load(stream).get("tool", {}).get("valutatrade", {})
                    )
            except (OSError, ValueError) as exc:
                raise DataStorageError(f"Ошибка чтения pyproject.toml: {exc}") from exc
        # При установке пакета вне исходников используются папки в cwd.
        workdir = root if project_config.is_file() else Path.cwd()
        data_override = os.getenv("VALUTATRADE_DATA_DIR")
        logs_override = os.getenv("VALUTATRADE_LOGS_DIR")
        data_dir = Path(data_override or config["data_dir"])
        logs_dir = Path(logs_override or config["logs_dir"])
        config["data_dir"] = data_dir if data_dir.is_absolute() else workdir / data_dir
        config["logs_dir"] = logs_dir if logs_dir.is_absolute() else workdir / logs_dir
        self._config = config

    def get(self, key: str, default: Any = None) -> Any:
        """Вернуть конфигурационное значение, иначе default."""
        return self._config.get(key, default)

    def file_path(self, filename: str) -> Path:
        """Путь к файлу внутри data_dir."""
        if Path(filename).name != filename:
            raise DataStorageError("Имя файла данных не должно содержать пути")
        return Path(self.get("data_dir")) / filename
