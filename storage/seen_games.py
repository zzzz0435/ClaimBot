import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


class SeenGames:
    def __init__(self, path: Path):
        self._path = path
        self.seen_ids: set[str] = self._load()

    def _load(self) -> set[str]:
        if not self._path.exists():
            self._write(set())
            return set()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return set(data.get("seen_ids", []))
        except (json.JSONDecodeError, KeyError, ValueError):
            log.error("seen_games.json 格式損毀，重置為空檔案")
            self._write(set())
            return set()

    def _write(self, ids: set[str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"seen_ids": sorted(ids)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, new_ids: set[str]) -> None:
        self.seen_ids |= new_ids
        self._write(self.seen_ids)

    def contains(self, game_id: str) -> bool:
        return game_id in self.seen_ids
