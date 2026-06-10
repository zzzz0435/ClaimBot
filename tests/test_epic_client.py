import asyncio
import re
import pytest
import aiohttp
from datetime import datetime, timezone
from aioresponses import aioresponses
from services.epic_client import EpicClient, UpcomingGame

EPIC_URL_PATTERN = re.compile(
    r"https://store-site-backend-static\.ak\.epicgames\.com/freeGamesPromotions.*"
)

MOCK_UPCOMING_ITEM = {
    "title": "Horizon Zero Dawn",
    "keyImages": [
        {"type": "Thumbnail", "url": "https://example.com/horizon.jpg"},
    ],
    "productSlug": "horizon-zero-dawn",
    "catalogNs": {
        "mappings": [
            {"pageSlug": "horizon-zero-dawn-complete-edition", "pageType": "productHome"}
        ]
    },
    "offerMappings": [],
    "promotions": {
        "promotionalOffers": [],
        "upcomingPromotionalOffers": [
            {
                "promotionalOffers": [
                    {
                        "startDate": "2026-06-06T16:00:00.000Z",
                        "endDate": "2026-06-13T16:00:00.000Z",
                        "discountSetting": {
                            "discountType": "PERCENTAGE",
                            "discountPercentage": 0,
                        },
                    }
                ]
            }
        ],
    },
}

MOCK_ACTIVE_ITEM = {
    "title": "Already Free Game",
    "keyImages": [],
    "productSlug": "already-free",
    "catalogNs": {"mappings": []},
    "offerMappings": [],
    "promotions": {
        "promotionalOffers": [
            {
                "promotionalOffers": [
                    {
                        "startDate": "2026-05-30T16:00:00.000Z",
                        "endDate": "2026-06-06T16:00:00.000Z",
                        "discountSetting": {"discountType": "PERCENTAGE", "discountPercentage": 0},
                    }
                ]
            }
        ],
        "upcomingPromotionalOffers": [],
    },
}

MOCK_NO_PROMO_ITEM = {
    "title": "Paid Game",
    "keyImages": [],
    "productSlug": "paid-game",
    "catalogNs": {"mappings": []},
    "offerMappings": [],
    "promotions": {
        "promotionalOffers": [],
        "upcomingPromotionalOffers": [],
    },
}

def make_response(*elements):
    return {
        "data": {
            "Catalog": {
                "searchStore": {
                    "elements": list(elements)
                }
            }
        }
    }


async def test_returns_upcoming_game():
    client = EpicClient()
    with aioresponses() as m:
        m.get(EPIC_URL_PATTERN, payload=make_response(MOCK_UPCOMING_ITEM))
        games = await client.get_upcoming_games()

    assert len(games) == 1
    assert games[0].title == "Horizon Zero Dawn"


async def test_excludes_already_active_game():
    client = EpicClient()
    with aioresponses() as m:
        m.get(EPIC_URL_PATTERN, payload=make_response(MOCK_ACTIVE_ITEM, MOCK_UPCOMING_ITEM))
        games = await client.get_upcoming_games()

    # 只有 upcoming，active 的不包含
    assert len(games) == 1
    assert games[0].title == "Horizon Zero Dawn"


async def test_excludes_paid_game():
    client = EpicClient()
    with aioresponses() as m:
        m.get(EPIC_URL_PATTERN, payload=make_response(MOCK_NO_PROMO_ITEM))
        games = await client.get_upcoming_games()

    assert games == []


async def test_parsed_fields():
    client = EpicClient()
    with aioresponses() as m:
        m.get(EPIC_URL_PATTERN, payload=make_response(MOCK_UPCOMING_ITEM))
        games = await client.get_upcoming_games()

    g = games[0]
    assert isinstance(g, UpcomingGame)
    assert "horizon-zero-dawn-complete-edition" in g.url
    assert g.image_url == "https://example.com/horizon.jpg"
    assert isinstance(g.start_date, datetime)
    assert g.start_date.tzinfo is not None


async def test_start_and_end_dates_parsed():
    client = EpicClient()
    with aioresponses() as m:
        m.get(EPIC_URL_PATTERN, payload=make_response(MOCK_UPCOMING_ITEM))
        games = await client.get_upcoming_games()

    g = games[0]
    assert g.start_date == datetime(2026, 6, 6, 16, 0, 0, tzinfo=timezone.utc)
    assert g.end_date == datetime(2026, 6, 13, 16, 0, 0, tzinfo=timezone.utc)


async def test_returns_empty_on_http_error():
    client = EpicClient()
    with aioresponses() as m:
        m.get(EPIC_URL_PATTERN, status=503)
        games = await client.get_upcoming_games()

    assert games == []


async def test_returns_empty_on_network_error():
    client = EpicClient()
    with aioresponses() as m:
        m.get(EPIC_URL_PATTERN, exception=aiohttp.ClientConnectionError("timeout"))
        games = await client.get_upcoming_games()

    assert games == []


async def test_returns_empty_on_malformed_response():
    client = EpicClient()
    with aioresponses() as m:
        m.get(EPIC_URL_PATTERN, payload={"unexpected": "format"})
        games = await client.get_upcoming_games()

    assert games == []


async def test_returns_empty_on_timeout():
    client = EpicClient()
    with aioresponses() as m:
        m.get(EPIC_URL_PATTERN, exception=asyncio.TimeoutError())
        games = await client.get_upcoming_games()

    assert games == []


async def test_returns_empty_on_invalid_json():
    client = EpicClient()
    with aioresponses() as m:
        m.get(EPIC_URL_PATTERN, body="not json", content_type="application/json")
        games = await client.get_upcoming_games()

    assert games == []


async def test_url_falls_back_when_mapping_missing_page_slug():
    client = EpicClient()
    item = {
        **MOCK_UPCOMING_ITEM,
        "catalogNs": {"mappings": [{"pageType": "productHome"}]},  # 缺 pageSlug
        "offerMappings": [{"pageType": "productHome"}],            # 缺 pageSlug
    }
    with aioresponses() as m:
        m.get(EPIC_URL_PATTERN, payload=make_response(item))
        games = await client.get_upcoming_games()

    assert len(games) == 1
    assert games[0].url.endswith("horizon-zero-dawn")  # fallback 至 productSlug
