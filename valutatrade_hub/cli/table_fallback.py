"""Минимальный резервный вывод таблиц, если prettytable ещё не установлен."""


class PrettyTable:
    """Небольшая подмена только для автономного тестирования без PyPI."""

    def __init__(self, field_names: list[str]) -> None:
        self.field_names = list(field_names)
        self.rows: list[list[str]] = []

    def add_row(self, values: list[object]) -> None:
        """Добавить строку."""
        self.rows.append([str(item) for item in values])

    def __str__(self) -> str:
        widths = [
            max(len(row[i]) for row in ([self.field_names] + self.rows))
            for i in range(len(self.field_names))
        ]
        border = "+" + "+".join("-" * (width + 2) for width in widths) + "+"
        def render(row: list[str]) -> str:
            return "| " + " | ".join(f"{item:<{widths[i]}}" for i, item in enumerate(row)) + " |"
        return "\n".join(
            [border, render(self.field_names), border]
            + [render(row) for row in self.rows]
            + [border]
        )
