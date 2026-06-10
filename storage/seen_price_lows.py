import json
import logging
from pathlib import Path

from storage.json_io import atomic_write_json, backup_corrupt

log = logging.getLogger(__name__)

SEEN_PRICE_LOWS_PATH = Path("data/seen_price_lows.json")


class SeenPriceLows:
    """
    追蹤每個 guild 曾通知過哪些遊戲的歷史新低價格。
    格式：{ "guild_id": { "game_id": notified_price } }
    只有當前價格 < 通知過的價格時才重新通知（真正的新紀錄低點）。
    """

    def __init__(self, path: Path = SEEN_PRICE_LOWS_PATH):
        self._path = path
        self._guilds: dict[str, dict[str, float]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._guilds = {
                    str(gid): {str(game_id): float(price) for game_id, price in games.items()}
                    for gid, games in data.items()
                    if isinstance(games, dict)
                }
        except (json.JSONDecodeError, ValueError, TypeError):
            log.error("seen_price_lows.json 格式損毀，備份後重置")
            backup_corrupt(self._path)
            self._guilds = {}

    def _write(self) -> None:
        atomic_write_json(self._path, self._guilds)

    def is_new_low(self, guild_id: int, game_id: str, current_price: float) -> bool:
        """若從未通知過，或當前價格比上次通知的更低，則回傳 True。"""
        notified = self._guilds.get(str(guild_id), {}).get(str(game_id))
        if notified is None:
            return True
        return current_price < notified

    def mark(self, guild_id: int, game_id: str, price: float) -> None:
        guild_key = str(guild_id)
        self._guilds.setdefault(guild_key, {})[str(game_id)] = price
        self._write()
