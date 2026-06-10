import json
import logging
from pathlib import Path

from storage.json_io import atomic_write_json, backup_corrupt

log = logging.getLogger(__name__)

GUILD_PRICE_ALERTS_PATH = Path("data/guild_price_alerts.json")


class GuildPriceAlerts:
    def __init__(self, path: Path = GUILD_PRICE_ALERTS_PATH):
        self._path = path
        self._settings: dict[str, bool] = self._load()

    def _load(self) -> dict[str, bool]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return {str(k): bool(v) for k, v in data.items()}
        except (json.JSONDecodeError, ValueError):
            log.error("guild_price_alerts.json 格式損毀，備份後重置")
            backup_corrupt(self._path)
            return {}

    def _write(self) -> None:
        atomic_write_json(self._path, self._settings)

    def set(self, guild_id: int, enabled: bool) -> None:
        self._settings[str(guild_id)] = enabled
        self._write()

    def get(self, guild_id: int) -> bool:
        return self._settings.get(str(guild_id), False)
