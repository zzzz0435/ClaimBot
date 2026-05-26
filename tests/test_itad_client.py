import re
import pytest
import aiohttp
from aioresponses import aioresponses
from services.itad_client import ITADClient, FreeGame

FAKE_KEY = "test_key"
ITAD_URL_PATTERN = re.compile(r"https://api\.isthereanydeal\.com/deals/v2.*")

MOCK_RESPONSE = {
    "games": [
        {
            "id": 12345,
            "title": "Temporarily Free Game",
            "assets": {"banner300": "https://example.com/banner.jpg"},
            "deal": {
                "regular": {"amount": 9.99},
                "url": "https://store.steampowered.com/app/12345/",
                "expiry": "2026-06-01T17:00:00Z",
            },
        },
        {
            "id": 67890,
            "title": "Temporarily Free No Image",
            "assets": {},
            "deal": {
                "regular": {"amount": 4.99},
                "url": "https://store.steampowered.com/app/67890/",
                "expiry": None,
            },
        },
        {
            "id": 99999,
            "title": "Permanently Free F2P Game",
            "assets": {},
            "deal": {
                "regular": {"amount": 0},
                "url": "https://store.steampowered.com/app/99999/",
                "expiry": None,
            },
        },
    ],
}


async def test_returns_only_temporarily_free_games():
    client = ITADClient(api_key=FAKE_KEY)
    with aioresponses() as m:
        m.get(ITAD_URL_PATTERN, payload=MOCK_RESPONSE)
        games = await client.get_free_games()

    assert len(games) == 2
    ids = [g.id for g in games]
    assert "12345" in ids
    assert "67890" in ids
    assert "99999" not in ids


async def test_returns_parsed_free_games():
    client = ITADClient(api_key=FAKE_KEY)
    with aioresponses() as m:
        m.get(ITAD_URL_PATTERN, payload=MOCK_RESPONSE)
        games = await client.get_free_games()

    g = games[0]
    assert isinstance(g, FreeGame)
    assert g.id == "12345"
    assert g.title == "Temporarily Free Game"
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
