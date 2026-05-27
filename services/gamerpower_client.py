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


class GamerPowerClient:
    async def get_free_games(self, platforms: list[str] | None = None) -> list[FreeGame]:
        if platforms is None:
            platforms = ["steam", "epic-games-store"]
        results: list[FreeGame] = []
        for platform in platforms:
            results.extend(await self._fetch_platform(platform))
        return results

    async def _fetch_platform(self, platform: str) -> list[FreeGame]:
        params = {"platform": platform, "type": "game"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    GAMERPOWER_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        log.warning("GamerPower API 回傳 HTTP %s (platform=%s)，跳過", resp.status, platform)
                        return []
                    data = await resp.json()
        except aiohttp.ClientError as exc:
            log.warning("GamerPower API 請求失敗 (platform=%s)：%s", platform, exc)
            return []

        if not isinstance(data, list):
            log.warning("GamerPower API 回傳非預期格式 (platform=%s)", platform)
            return []

        return [self._parse(item, platform) for item in data if self._is_valid(item)]

    def _is_valid(self, item: dict) -> bool:
        return (
            item.get("status") == "Active"
            and item.get("type") == "Game"
        )

    def _parse(self, item: dict, platform: str) -> FreeGame:
        return FreeGame(
            id=str(item["id"]),
            title=item.get("title", ""),
            url=item.get("open_giveaway") or item.get("gamerpower_url", ""),
            image_url=item.get("image") or item.get("thumbnail", ""),
            expires_at=self._parse_date(item.get("end_date")),
            platform=platform,
            worth=self._parse_worth(item.get("worth")),
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
