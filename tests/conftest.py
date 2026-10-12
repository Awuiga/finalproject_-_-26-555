"""Независимые тестовые директории вместо пользовательских файлов данных."""

import pytest

from valutatrade_hub.infra.settings import SettingsLoader


@pytest.fixture(autouse=True)
def isolated_data(monkeypatch, tmp_path):
    """Подставить для каждого теста новый каталог JSON-хранилища."""
    monkeypatch.setenv("VALUTATRADE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("VALUTATRADE_LOGS_DIR", str(tmp_path / "logs"))
    SettingsLoader().reload()
    yield
    SettingsLoader().reload()
