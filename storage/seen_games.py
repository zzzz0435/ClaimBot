import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


class SeenGames:
    def __init__(self, path: Path):
        self._path = path
        self._guilds: dict[str, set[str]] = {}
        self._legacy_ids: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._write({})
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if "guilds" in data:
                self._guilds = {k: set(v) for k, v in data["guilds"].items()}
            elif "seen_ids" in data:
                self._legacy_ids = set(data["seen_ids"])
                log.warning("seen_games.json 為舊格式，將在啟動時遷移至 per-guild 追蹤")
            else:
                self._write({})
        except (json.JSONDecodeError, KeyError, ValueError):
            log.error("seen_games.json 格式損毀，重置")
            self._write({})

    def _write(self, guilds: dict[str, set[str]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(
                {"guilds": {k: sorted(v) for k, v in guilds.items()}},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def needs_migration(self) -> bool:
        return bool(self._legacy_ids)

    def migrate(self, guild_ids: list[int]) -> None:
        if not guild_ids:
            log.warning("migrate() 傳入空 guild 清單，保留舊資料等待下次重試")
            return
        for guild_id in guild_ids:
            key = str(guild_id)
            self._guilds.setdefault(key, set())
            self._guilds[key] |= self._legacy_ids
        self._legacy_ids = set()
        self._write(self._guilds)
        log.info("seen_games.json 遷移完成，套用至 %d 個伺服器", len(guild_ids))

    def seen_ids(self, guild_id: int) -> set[str]:
        return self._guilds.get(str(guild_id), set()).copy()

    def add(self, guild_id: int, new_ids: set[str]) -> None:
        key = str(guild_id)
        self._guilds.setdefault(key, set())
        self._guilds[key] |= new_ids
        self._write(self._guilds)

    def contains(self, guild_id: int, game_id: str) -> bool:
        return game_id in self._guilds.get(str(guild_id), set())
