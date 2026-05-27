import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import aiohttp

log = logging.getLogger(__name__)

EPIC_PROMOTIONS_URL = (
    "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
)
EPIC_STORE_BASE = "https://store.epicgames.com/zh-Hant/p/"


@dataclass
class UpcomingGame:
    title: str
    url: str
    image_url: str
    start_date: datetime | None
    end_date: datetime | None


class EpicClient:
    async def get_upcoming_games(self) -> list[UpcomingGame]:
        params = {"locale": "zh-Hant", "country": "TW", "allowCountries": "TW"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    EPIC_PROMOTIONS_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        log.warning("Epic API 回傳 HTTP %s", resp.status)
                        return []
                    data = await resp.json(content_type=None)
        except aiohttp.ClientError as exc:
            log.warning("Epic API 請求失敗：%s", exc)
            return []

        try:
            elements = data["data"]["Catalog"]["searchStore"]["elements"]
        except (KeyError, TypeError):
            log.warning("Epic API 回傳非預期格式")
            return []

        return [game for item in elements if (game := self._parse_upcoming(item))]

    def _parse_upcoming(self, item: dict) -> UpcomingGame | None:
        upcoming_groups = (item.get("promotions") or {}).get("upcomingPromotionalOffers", [])
        if not upcoming_groups:
            return None

        # 找出 100% 折扣（discountPercentage == 0）的優惠
        offer = None
        for group in upcoming_groups:
            for o in group.get("promotionalOffers", []):
                if o.get("discountSetting", {}).get("discountPercentage") == 0:
                    offer = o
                    break
            if offer:
                break

        if not offer:
            return None

        return UpcomingGame(
            title=item.get("title", ""),
            url=self._get_url(item),
            image_url=self._get_image(item),
            start_date=self._parse_date(offer.get("startDate")),
            end_date=self._parse_date(offer.get("endDate")),
        )

    def _get_image(self, item: dict) -> str:
        images = item.get("keyImages", [])
        for preferred in ("Thumbnail", "OfferImageWide", "DieselStoreFrontWide"):
            for img in images:
                if img.get("type") == preferred:
                    return img.get("url", "")
        return images[0].get("url", "") if images else ""

    def _get_url(self, item: dict) -> str:
        for mapping in (item.get("catalogNs") or {}).get("mappings", []):
            if mapping.get("pageType") == "productHome":
                return EPIC_STORE_BASE + mapping["pageSlug"]
        for mapping in item.get("offerMappings", []):
            if mapping.get("pageType") == "productHome":
                return EPIC_STORE_BASE + mapping["pageSlug"]
        slug = item.get("productSlug") or item.get("urlSlug")
        if slug and slug != "[]":
            return EPIC_STORE_BASE + slug
        return "https://store.epicgames.com/zh-Hant/free-games"

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return None
