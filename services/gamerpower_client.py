import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import aiohttp

log = logging.getLogger(__name__)

GAMERPOWER_URL = "https://www.gamerpower.com/api/giveaways"

PLATFORM_LABELS: dict[str, str] = {
    "steam": "Steam",
    "epic-games-store": "Epic Games",
}


@dataclass
class FreeGame:
    id: str
    title: str
    url: str
    image_url: str
    expires_at: datetime | None
    platform: str
    worth: str | None          # 原價，例如 "$49.99"；無資料時為 None
    kind: str = "game"         # "game" 或 "dlc"


class GamerPowerClient:
    async def get_free_games(
        self,
        platforms: list[str] | None = None,
        include_dlc: bool = False,
    ) -> list[FreeGame]:
        if platforms is None:
            platforms = ["steam", "epic-games-store"]
        results: list[FreeGame] = []
        for platform in platforms:
            results.extend(await self._fetch_platform(platform, "game"))
            if include_dlc:
                results.extend(await self._fetch_platform(platform, "loot"))
        return results

    async def _fetch_platform(self, platform: str, api_type: str = "game") -> list[FreeGame]:
        params = {"platform": platform, "type": api_type}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    GAMERPOWER_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        log.warning("GamerPower API 回傳 HTTP %s (platform=%s, type=%s)，跳過", resp.status, platform, api_type)
                        return []
                    data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as exc:
            log.warning("GamerPower API 請求失敗 (platform=%s, type=%s)：%s", platform, api_type, exc)
            return []

        if not isinstance(data, list):
            log.warning("GamerPower API 回傳非預期格式 (platform=%s)", platform)
            return []

        kind = "game" if api_type == "game" else "dlc"
        return [self._parse(item, platform, kind) for item in data if self._is_valid(item, api_type)]

    def _is_valid(self, item: dict, api_type: str = "game") -> bool:
        if item.get("id") is None:
            return False
        if item.get("status") != "Active":
            return False
        if api_type == "game":
            return item.get("type") == "Game"
        return item.get("type") != "Game"  # loot：非完整遊戲的項目

    def _parse(self, item: dict, platform: str, kind: str = "game") -> FreeGame:
        return FreeGame(
            id=str(item["id"]),
            title=item.get("title", ""),
            url=item.get("open_giveaway") or item.get("gamerpower_url", ""),
            image_url=item.get("image") or item.get("thumbnail", ""),
            expires_at=self._parse_date(item.get("end_date")),
            platform=platform,
            worth=self._parse_worth(item.get("worth")),
            kind=kind,
        )

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        if not date_str or date_str == "N/A":
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    @staticmethod
    def _parse_worth(worth: str | None) -> str | None:
        if not worth or worth in ("N/A", "$0.00", "0.00", "$0"):
            return None
        return worth
