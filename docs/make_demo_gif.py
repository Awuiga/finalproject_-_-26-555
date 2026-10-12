"""Создать GIF из реального вывода команд (только виртуальные тестовые данные)."""

import io
import os
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from valutatrade_hub.cli.interface import Console
from valutatrade_hub.infra.settings import SettingsLoader


def main() -> None:
    """Последовательно запустить настоящие команды и отрисовать результат."""
    with tempfile.TemporaryDirectory() as scratch:
        os.environ["VALUTATRADE_DATA_DIR"] = str(Path(scratch) / "data")
        os.environ["VALUTATRADE_LOGS_DIR"] = str(Path(scratch) / "logs")
        SettingsLoader().reload()
        console = Console()
        commands = [
            "help",
            "demo-rates",
            "register --username alice --password 1234",
            "login --username alice --password 1234",
            "deposit-demo --amount 10000",
            "buy --currency BTC --amount 0.05",
            "sell --currency BTC --amount 0.01",
            "show-portfolio",
            "get-rate --from USD --to BTC",
            "show-rates --top 2",
            "update-rates --source exchangerate",
            "sell --currency BTC --amount 100",
            "get-rate --from ABC --to USD",
            "history",
        ]
        frames = []
        history = []
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
        font = ImageFont.truetype(font_path, 19)
        title_font = ImageFont.truetype(font_path, 22)
        for command in commands:
            stream = io.StringIO()
            with redirect_stdout(stream):
                console.execute(command)
            # Не показывать набранный пароль даже в демонстрационной записи.
            safe_command = command.replace("1234", "****")
            history.append(f"valutatrade> {safe_command}")
            history.extend(stream.getvalue().rstrip().splitlines())
            img = Image.new("RGB", (1200, 740), "#101827")
            d = ImageDraw.Draw(img)
            d.rounded_rectangle((20, 20, 1180, 720), radius=18, fill="#172235")
            d.rounded_rectangle((20, 20, 1180, 72), radius=18, fill="#2b374a")
            d.rectangle((20, 53, 1180, 72), fill="#2b374a")
            for i, color in enumerate(("#ff655e", "#ffbf42", "#34c759")):
                d.ellipse((44 + i * 28, 42, 60 + i * 28, 58), fill=color)
            d.text((155, 33), "ValutaTrade Hub • демо-режим • только виртуальные средства", font=title_font, fill="#e7eef9")
            # Панель ограничена 25 строками, т.е. терминал реалистично прокручивается.
            y = 89
            for line in history[-25:]:
                if len(line) > 104:
                    line = line[:101] + "..."
                color = "#a9dbba" if line.startswith("valutatrade>") else "#edf3fc"
                if line.startswith("Ошибка:"):
                    color = "#ffaeae"
                d.text((42, y), line, font=font, fill=color)
                y += 24
            d.text((43, 694), "DEMO-курсы не являются рыночными котировками", font=font, fill="#bac8df")
            frames.append(img)
        frames[0].save(
            Path(__file__).with_name("valutatrade_demo.gif"),
            save_all=True,
            append_images=frames[1:],
            duration=[1600] + [1400] * (len(frames) - 1),
            loop=0,
            optimize=True,
        )


if __name__ == "__main__":
    main()
