import logging
from dataclasses import dataclass

import aiohttp

log = logging.getLogger(__name__)

ITAD_DEALS_URL = "https://api.isthereanydeal.com/deals/v2"


@dataclass
class FreeGame:
    id: str
    title: str
    url: str
    image_url: str
    expires_at: str | None


class ITADClient:
    def __init__(self, api_key: str):
        self._api_key = api_key

    async def get_free_games(self) -> list[FreeGame]:
        params = {
            "shops": 61,
            "country": "US",
            "price_max": 0,
            "limit": 20,
            "key": self._api_key,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    ITAD_DEALS_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        log.warning("ITAD API 回傳 HTTP %s，跳過本次", resp.status)
                        return []
                    data = await resp.json()
        except aiohttp.ClientError as exc:
            log.warning("ITAD API 請求失敗：%s", exc)
            return []

        if isinstance(data, list):
            items = data
        else:
            items = data.get("games") or data.get("list") or data.get("deals") or []
        return [self._parse(item) for item in items]

    def _parse(self, item: dict) -> FreeGame:
        assets = item.get("assets", {})
        deal = item.get("deal", {})
        return FreeGame(
            id=str(item.get("id", "")),
            title=item.get("title", ""),
            url=deal.get("url", ""),
            image_url=assets.get("banner300") or assets.get("banner145") or "",
            expires_at=deal.get("expiry"),
        )
