import re
import pytest
import aiohttp
from aioresponses import aioresponses
from services.itad_client import ITADClient, FreeGame

FAKE_KEY = "test_key"
ITAD_URL_PATTERN = re.compile(r"https://api\.isthereanydeal\.com/deals/v2.*")

MOCK_RESPONSE = {
    "hasMore": False,
    "nextCursor": None,
    "list": [
        {
            "game": {
                "id": 12345,
                "title": "Free Game One",
                "assets": {"banner300": "https://example.com/banner.jpg"},
            },
            "deal": {
                "url": "https://store.steampowered.com/app/12345/",
                "expiry": "2026-06-01T17:00:00Z",
            },
        },
        {
            "game": {
                "id": 67890,
                "title": "Free Game Two (No Image)",
                "assets": {},
            },
            "deal": {
                "url": "https://store.steampowered.com/app/67890/",
                "expiry": None,
            },
        },
    ],
}


async def test_returns_parsed_free_games():
    client = ITADClient(api_key=FAKE_KEY)
    with aioresponses() as m:
        m.get(ITAD_URL_PATTERN, payload=MOCK_RESPONSE)
        games = await client.get_free_games()

    assert len(games) == 2
    g = games[0]
    assert isinstance(g, FreeGame)
    assert g.id == "12345"
    assert g.title == "Free Game One"
    assert g.url == "https://store.steampowered.com/app/12345/"
    assert g.image_url == "https://example.com/banner.jpg"
    assert g.expires_at == "2026-06-01T17:00:00Z"


async def test_missing_image_returns_empty_string():
    client = ITADClient(api_key=FAKE_KEY)
    with aioresponses() as m:
        m.get(ITAD_URL_PATTERN, payload=MOCK_RESPONSE)
        games = await client.get_free_games()

    assert games[1].image_url == ""
    assert games[1].expires_at is None


async def test_returns_empty_list_on_http_error():
    client = ITADClient(api_key=FAKE_KEY)
    with aioresponses() as m:
        m.get(ITAD_URL_PATTERN, status=500)
        games = await client.get_free_games()

    assert games == []


async def test_returns_empty_list_on_network_error():
    client = ITADClient(api_key=FAKE_KEY)
    with aioresponses() as m:
        m.get(ITAD_URL_PATTERN, exception=aiohttp.ClientConnectionError("連線失敗"))
        games = await client.get_free_games()

    assert games == []
