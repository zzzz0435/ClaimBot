import asyncio
import json
import logging
import re
from dataclasses import dataclass

import aiohttp

log = logging.getLogger(__name__)

ITAD_BASE = "https://api.isthereanydeal.com"
STEAMSPY_BASE = "https://steamspy.com/api.php"
STEAM_SHOP_ID = 61  # ITAD 的 Steam 商店 ID


@dataclass
class PriceDeal:
    id: str              # ITAD game ID
    title: str
    url: str             # Steam 商品頁面 URL
    current_price: float
    original_price: float
    currency: str        # 例如 "USD"
    historical_low: float
    discount_pct: int    # 0-100
    image_url: str       # Steam CDN header 圖


def _extract_steam_appid(url: str) -> str | None:
    m = re.search(r"/app/(\d+)", url)
    return m.group(1) if m else None


class ITADClient:
    def __init__(self, api_key: str):
        self._key = api_key
        self._semaphore: asyncio.Semaphore | None = None

    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(3)
        return self._semaphore

    async def get_steam_historical_lows(
        self,
        min_reviews: int = 500,
        limit: int = 200,
    ) -> list[PriceDeal]:
        raw_deals = await self._fetch_deals(limit)
        if not raw_deals:
            return []

        at_low = [d for d in raw_deals if self._is_at_historical_low(d)]
        if not at_low:
            log.info("ITAD: 目前無 Steam 遊戲達到歷史新低")
            return []

        log.info("ITAD: %d 款遊戲達到歷史新低，開始篩選評論數（>= %d）", len(at_low), min_reviews)

        async def enrich(d: dict) -> PriceDeal | None:
            try:
                game = d["game"]
                deal = d["deal"]
                url = deal.get("url", "")
                appid = _extract_steam_appid(url)
                if not appid:
                    return None
                reviews = await self._fetch_steamspy_reviews(appid)
                if reviews < min_reviews:
                    return None
                store_low = self._parse_store_low(deal)
                return PriceDeal(
                    id=game["id"],
                    title=game.get("title", ""),
                    url=url,
                    current_price=deal["price"]["amount"],
                    original_price=deal["regular"]["amount"],
                    currency=deal["price"]["currency"],
                    historical_low=store_low,
                    discount_pct=deal["cut"],
                    image_url=f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg",
                )
            except (KeyError, TypeError, ValueError) as exc:
                log.warning("ITAD deal 缺少必要欄位，跳過：%s", exc)
                return None

        results = await asyncio.gather(*[enrich(d) for d in at_low])
        filtered = [r for r in results if r is not None]
        log.info("ITAD: 篩選後 %d 款知名遊戲達到歷史新低", len(filtered))
        return filtered

    def _is_at_historical_low(self, d: dict) -> bool:
        try:
            deal = d["deal"]
            price = deal["price"]["amount"]
            store_low = self._parse_store_low(deal)
            return price > 0 and store_low > 0 and price <= store_low
        except (KeyError, TypeError):
            return False

    @staticmethod
    def _parse_store_low(deal: dict) -> float:
        sl = deal.get("storeLow")
        if sl is None:
            return 0.0
        if isinstance(sl, dict):
            return float(sl.get("amount", 0))
        try:
            return float(sl)
        except (ValueError, TypeError):
            return 0.0

    async def _fetch_deals(self, limit: int) -> list[dict]:
        params = {
            "key": self._key,
            "shops": STEAM_SHOP_ID,
            "limit": min(limit, 200),
            "sort": "-cut",
            "country": "US",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{ITAD_BASE}/deals/v2",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        log.warning("ITAD /deals/v2 回傳 HTTP %s", resp.status)
                        return []
                    data = await resp.json()
                    if isinstance(data, dict):
                        return data.get("list", [])
                    if isinstance(data, list):
                        return data
                    return []
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as e:
            log.warning("ITAD /deals/v2 請求失敗：%s", e)
            return []

    async def _fetch_steamspy_reviews(self, appid: str) -> int:
        async with self._get_semaphore():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        STEAMSPY_BASE,
                        params={"request": "appdetails", "appid": appid},
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status != 200:
                            return 0
                        data = await resp.json(content_type=None)
                        if not isinstance(data, dict):
                            return 0
                        return int(data.get("positive", 0)) + int(data.get("negative", 0))
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, TypeError):
                return 0
