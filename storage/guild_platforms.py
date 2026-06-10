import json
import logging
from pathlib import Path

from storage.json_io import atomic_write_json, backup_corrupt

log = logging.getLogger(__name__)

GUILD_PLATFORMS_PATH = Path("data/guild_platforms.json")
DEFAULT_PLATFORMS = ["steam", "epic-games-store"]


class GuildPlatforms:
    def __init__(self, path: Path = GUILD_PLATFORMS_PATH):
        self._path = path
        self._platforms: dict[str, list[str]] = self._load()

    def _load(self) -> dict[str, list[str]]:
        if not self._path.exists():
            self._write({})
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return {str(k): list(v) for k, v in data.items()}
        except (json.JSONDecodeError, ValueError):
            log.error("guild_platforms.json 格式損毀，備份後重置")
            backup_corrupt(self._path)
            self._write({})
            return {}

    def _write(self, platforms: dict[str, list[str]]) -> None:
        atomic_write_json(self._path, platforms)

    def set(self, guild_id: int, platforms: list[str]) -> None:
        self._platforms[str(guild_id)] = platforms
        self._write(self._platforms)

    def get(self, guild_id: int) -> list[str]:
        return self._platforms.get(str(guild_id), list(DEFAULT_PLATFORMS))
