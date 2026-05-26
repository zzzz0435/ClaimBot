import re
import pytest
import aiohttp
from aioresponses import aioresponses
from services.gamerpower_client import GamerPowerClient, FreeGame

GP_URL_PATTERN = re.compile(r"https://www\.gamerpower\.com/api/giveaways.*")

MOCK_RESPONSE = [
    {
        "id": 1001,
        "title": "Warhammer 40,000: Gladius",
        "type": "Game",
        "platforms": "Steam",
        "status": "Active",
        "image": "https://example.com/warhammer.jpg",
        "thumbnail": "https://example.com/warhammer_thumb.jpg",
        "open_giveaway": "https://store.steampowered.com/app/489630/",
        "gamerpower_url": "https://www.gamerpower.com/warhammer",
        "end_date": "2026-06-01 00:00:00",
    },
    {
        "id": 1002,
        "title": "Free DLC Pack",
        "type": "DLC",
        "platforms": "Steam",
        "status": "Active",
        "image": "https://example.com/dlc.jpg",
        "thumbnail": "",
        "open_giveaway": "https://store.steampowered.com/app/99999/",
        "gamerpower_url": "https://www.gamerpower.com/dlc",
        "end_date": "N/A",
    },
    {
        "id": 1003,
        "title": "Epic Only Game",
        "type": "Game",
        "platforms": "Epic Games Store",
        "status": "Active",
        "image": "https://example.com/epic.jpg",
        "thumbnail": "",
        "open_giveaway": "https://epicgames.com/store/...",
        "gamerpower_url": "https://www.gamerpower.com/epic",
        "end_date": "N/A",
    },
    {
        "id": 1004,
        "title": "Expired Game",
        "type": "Game",
        "platforms": "Steam",
        "status": "Expired",
        "image": "https://example.com/expired.jpg",
        "thumbnail": "",
        "open_giveaway": "https://store.steampowered.com/app/55555/",
        "gamerpower_url": "https://www.gamerpower.com/expired",
        "end_date": "2026-01-01 00:00:00",
    },
]


async def test_returns_only_active_steam_games():
    client = GamerPowerClient()
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, payload=MOCK_RESPONSE)
        games = await client.get_free_games()

    assert len(games) == 1
    assert games[0].id == "1001"
    assert games[0].title == "Warhammer 40,000: Gladius"


async def test_parsed_game_fields():
    client = GamerPowerClient()
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, payload=MOCK_RESPONSE)
        games = await client.get_free_games()

    g = games[0]
    assert isinstance(g, FreeGame)
    assert g.url == "https://store.steampowered.com/app/489630/"
    assert g.image_url == "https://example.com/warhammer.jpg"
    assert g.expires_at == "2026-06-01 00:00:00"


async def test_end_date_na_becomes_none():
    client = GamerPowerClient()
    single = [MOCK_RESPONSE[0].copy()]
    single[0] = {**single[0], "end_date": "N/A"}
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, payload=single)
        games = await client.get_free_games()

    assert games[0].expires_at is None


async def test_returns_empty_on_http_error():
    client = GamerPowerClient()
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, status=500)
        games = await client.get_free_games()

    assert games == []


async def test_returns_empty_on_network_error():
    client = GamerPowerClient()
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, exception=aiohttp.ClientConnectionError("timeout"))
        games = await client.get_free_games()

    assert games == []
