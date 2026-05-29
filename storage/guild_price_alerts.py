import json
import logging
from pathlib import Path

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
            log.error("guild_price_alerts.json 格式損毀，重置")
            return {}

    def _write(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def set(self, guild_id: int, enabled: bool) -> None:
        self._settings[str(guild_id)] = enabled
        self._write()

    def get(self, guild_id: int) -> bool:
        return self._settings.get(str(guild_id), False)
