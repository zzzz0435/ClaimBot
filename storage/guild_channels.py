import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

GUILD_CHANNELS_PATH = Path("data/guild_channels.json")


class GuildChannels:
    def __init__(self, path: Path = GUILD_CHANNELS_PATH):
        self._path = path
        self._channels: dict[str, int] = self._load()

    def _load(self) -> dict[str, int]:
        if not self._path.exists():
            self._write({})
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return {str(k): int(v) for k, v in data.items()}
        except (json.JSONDecodeError, ValueError):
            log.error("guild_channels.json 格式損毀，重置")
            self._write({})
            return {}

    def _write(self, channels: dict[str, int]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(channels, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def set(self, guild_id: int, channel_id: int) -> None:
        self._channels[str(guild_id)] = channel_id
        self._write(self._channels)

    def all_channels(self) -> list[int]:
        return list(self._channels.values())

    def all_items(self) -> list[tuple[int, int]]:
        return [(int(gid), cid) for gid, cid in self._channels.items()]
