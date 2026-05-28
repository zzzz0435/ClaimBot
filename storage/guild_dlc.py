import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

GUILD_DLC_PATH = Path("data/guild_dlc.json")


class GuildDLC:
    def __init__(self, path: Path = GUILD_DLC_PATH):
        self._path = path
        self._settings: dict[str, bool] = self._load()

    def _load(self) -> dict[str, bool]:
        if not self._path.exists():
            self._write({})
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return {str(k): bool(v) for k, v in data.items()}
        except (json.JSONDecodeError, ValueError):
            log.error("guild_dlc.json 格式損毀，重置")
            self._write({})
            return {}

    def _write(self, settings: dict[str, bool]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def set(self, guild_id: int, enabled: bool) -> None:
        self._settings[str(guild_id)] = enabled
        self._write(self._settings)

    def get(self, guild_id: int) -> bool:
        return self._settings.get(str(guild_id), False)
