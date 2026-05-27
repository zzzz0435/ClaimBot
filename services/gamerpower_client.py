import logging
from dataclasses import dataclass

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
    expires_at: str | None
    platform: str


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
        end_date = item.get("end_date")
        expires_at = None if end_date in (None, "N/A") else end_date
        return FreeGame(
            id=str(item["id"]),
            title=item.get("title", ""),
            url=item.get("open_giveaway") or item.get("gamerpower_url", ""),
            image_url=item.get("image") or item.get("thumbnail", ""),
            expires_at=expires_at,
            platform=platform,
        )
