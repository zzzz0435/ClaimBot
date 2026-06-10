import json
import logging
from pathlib import Path

from storage.json_io import atomic_write_json, backup_corrupt

log = logging.getLogger(__name__)

GUILD_ROLES_PATH = Path("data/guild_roles.json")


class GuildRoles:
    def __init__(self, path: Path = GUILD_ROLES_PATH):
        self._path = path
        self._roles: dict[str, int] = self._load()

    def _load(self) -> dict[str, int]:
        if not self._path.exists():
            self._write({})
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return {str(k): int(v) for k, v in data.items()}
        except (json.JSONDecodeError, ValueError):
            log.error("guild_roles.json 格式損毀，備份後重置")
            backup_corrupt(self._path)
            self._write({})
            return {}

    def _write(self, roles: dict[str, int]) -> None:
        atomic_write_json(self._path, roles)

    def set(self, guild_id: int, role_id: int) -> None:
        self._roles[str(guild_id)] = role_id
        self._write(self._roles)

    def get(self, guild_id: int) -> int | None:
        return self._roles.get(str(guild_id))

    def clear(self, guild_id: int) -> None:
        self._roles.pop(str(guild_id), None)
        self._write(self._roles)
