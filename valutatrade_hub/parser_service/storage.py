"""Обновление кэша и сохранение истории курсов по уникальному ID."""

from collections.abc import Mapping

from valutatrade_hub.core.utils import iso_now, parse_datetime
from valutatrade_hub.infra.database import DatabaseManager


class RatesStorage:
    """Хранилище со снимком последних курсов и историей измерений."""

    def __init__(self, database: DatabaseManager | None = None) -> None:
        self.database = database or DatabaseManager()

    def save(self, new_pairs: Mapping[str, dict], *, timestamp: str | None = None) -> int:
        """Обновить только более свежие пары и не дублировать историю."""
        now = timestamp or iso_now()
        updated: dict[str, dict] = {}

        def merge_rates(data: dict) -> None:
            pairs = data.setdefault("pairs", {})
            for code, new in new_pairs.items():
                previous = pairs.get(code)
                if previous and parse_datetime(previous["updated_at"]) > parse_datetime(
                    new["updated_at"]
                ):
                    continue
                pairs[code] = dict(new)
                updated[code] = dict(new)
            if updated:
                data["last_refresh"] = now

        self.database.transaction(
            "rates.json", {"pairs": {}, "last_refresh": None}, merge_rates
        )
        if not updated:
            return 0

        def merge_history(entries: list[dict]) -> None:
            seen = {entry["id"] for entry in entries}
            for code, info in updated.items():
                # Разделить только на одну пару; коды валют не содержат '_'.
                from_code, to_code = code.split("_", 1)
                timestamp_iso = info["updated_at"]
                record_id = f"{from_code}_{to_code}_{timestamp_iso}"
                if record_id not in seen:
                    entries.append(
                        {
                            "id": record_id,
                            "from_currency": from_code,
                            "to_currency": to_code,
                            "rate": info["rate"],
                            "timestamp": timestamp_iso,
                            "source": info["source"],
                            "meta": info.get("meta", {}),
                        }
                    )
                    seen.add(record_id)

        self.database.transaction("exchange_rates.json", [], merge_history)
        return len(updated)
