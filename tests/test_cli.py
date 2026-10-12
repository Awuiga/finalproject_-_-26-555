"""Проверки CLI-команд с одной непрерывной сессией."""

from valutatrade_hub.cli.interface import Console
from valutatrade_hub.core.usecases import RateService, TradeService
from valutatrade_hub.infra.database import DatabaseManager


def test_cli_full_scenario(capsys):
    db = DatabaseManager()
    rates = RateService(db, auto_refresh=False)
    console = Console(TradeService(db, rates), db, rates)
    for command in (
        "demo-rates",
        "register --username alice --password 1234",
        "login --username alice --password 1234",
        "deposit-demo --amount 10000",
        "buy --currency BTC --amount 0.05",
        "sell --currency BTC --amount 0.01",
        "show-portfolio",
        "get-rate --from USD --to BTC",
        "show-rates --top 2",
        "history",
    ):
        assert console.execute(command)
    output = capsys.readouterr().out
    assert "зарегистрирован" in output
    assert "Покупка выполнена" in output
    assert "Продажа выполнена" in output
    assert "ИТОГО" in output
    assert "Курс USD→BTC" in output
    assert "BTC" in output
    console.execute("sell --currency BTC --amount 100")
    assert "Недостаточно средств" in capsys.readouterr().out
    console.execute("get-rate --from XYZ --to USD")
    assert "Неизвестная валюта" in capsys.readouterr().out
