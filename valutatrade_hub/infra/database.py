"""JSON-хранилище c атомарной записью и сериализованными изменениями."""

import json
import os
import tempfile
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from threading import Lock, RLock
from typing import Any, TypeVar

from valutatrade_hub.core.exceptions import DataStorageError
from valutatrade_hub.infra.settings import SettingsLoader

T = TypeVar("T")


class DatabaseManager:
    """Singleton для единого доступа к локальным JSON-файлам."""

    _instance: "DatabaseManager | None" = None
    _instance_lock = Lock()

    def __new__(cls) -> "DatabaseManager":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._lock = RLock()
            return cls._instance

    def _path(self, name: str) -> Path:
        return SettingsLoader().file_path(name)

    @staticmethod
    def _read(path: Path, default: T) -> T:
        if not path.exists():
            return deepcopy(default)
        try:
            with path.open(encoding="utf-8") as file:
                return json.load(file)
        except (OSError, json.JSONDecodeError, UnicodeError) as exc:
            raise DataStorageError(f"Не удалось прочитать {path.name}: {exc}") from exc

    @staticmethod
    def _write(path: Path, data: Any) -> None:
        """Сначала создать tmp в той же папке, затем заменить конечный файл."""
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent,
                prefix=f".{path.name}.", suffix=".tmp", delete=False,
            ) as stream:
                temp_name = stream.name
                json.dump(data, stream, indent=2, ensure_ascii=False, allow_nan=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, path)
        except (OSError, TypeError, ValueError) as exc:
            raise DataStorageError(f"Не удалось сохранить {path.name}: {exc}") from exc
        finally:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)

    def read(self, filename: str, default: T) -> T:
        """Прочитать JSON в пределах блокировки процесса."""
        with self._lock:
            return self._read(self._path(filename), default)

    def write(self, filename: str, data: Any) -> None:
        """Атомарно заменить содержимое файла."""
        with self._lock:
            self._write(self._path(filename), data)

    def transaction(
        self, filename: str, default: T, modify: Callable[[T], Any]
    ) -> Any:
        """Выполнить чтение→изменение→запись под одной блокировкой."""
        with self._lock:
            path = self._path(filename)
            records = self._read(path, default)
            result = modify(records)
            self._write(path, records)
            return result

    def load_users(self) -> list[dict]:
        """Прочитать список зарегистрированных пользователей."""
        return self.read("users.json", [])

    def load_portfolios(self) -> list[dict]:
        """Прочитать кошельки пользователей."""
        return self.read("portfolios.json", [])

    def load_rates(self) -> dict:
        """Прочитать последний снимок курсов."""
        return self.read("rates.json", {"pairs": {}, "last_refresh": None})

    def save_rates(self, data: dict) -> None:
        """Атомарно обновить файл курсов."""
        self.write("rates.json", data)
