import asyncio
import re
import pytest
import aiohttp
from datetime import datetime, timezone
from aioresponses import aioresponses
from services.gamerpower_client import GamerPowerClient, FreeGame

GP_URL_PATTERN = re.compile(r"https://www\.gamerpower\.com/api/giveaways.*")

STEAM_RESPONSE = [
    {
        "id": 1001,
        "title": "Warhammer 40,000: Gladius",
        "type": "Game",
        "platforms": "PC, Steam",
        "status": "Active",
        "image": "https://example.com/warhammer.jpg",
        "thumbnail": "https://example.com/warhammer_thumb.jpg",
        "open_giveaway": "https://store.steampowered.com/app/489630/",
        "gamerpower_url": "https://www.gamerpower.com/warhammer",
        "end_date": "2026-06-01 00:00:00",
        "worth": "$39.99",
    },
    {
        "id": 1002,
        "title": "Free DLC Pack",
        "type": "DLC",
        "platforms": "PC, Steam",
        "status": "Active",
        "image": "https://example.com/dlc.jpg",
        "thumbnail": "",
        "open_giveaway": "https://store.steampowered.com/app/99999/",
        "gamerpower_url": "https://www.gamerpower.com/dlc",
        "end_date": "N/A",
        "worth": "N/A",
    },
    {
        "id": 1004,
        "title": "Expired Game",
        "type": "Game",
        "platforms": "PC, Steam",
        "status": "Expired",
        "image": "https://example.com/expired.jpg",
        "thumbnail": "",
        "open_giveaway": "https://store.steampowered.com/app/55555/",
        "gamerpower_url": "https://www.gamerpower.com/expired",
        "end_date": "2026-01-01 00:00:00",
        "worth": "$9.99",
    },
]

EPIC_RESPONSE = [
    {
        "id": 2001,
        "title": "Epic Exclusive Game",
        "type": "Game",
        "platforms": "PC, Epic Games Store",
        "status": "Active",
        "image": "https://example.com/epic.jpg",
        "thumbnail": "",
        "open_giveaway": "https://store.epicgames.com/en-US/p/game",
        "gamerpower_url": "https://www.gamerpower.com/epic-game",
        "end_date": "2026-06-15 00:00:00",
        "worth": "$59.99",
    },
]


async def test_returns_only_active_games_from_steam():
    client = GamerPowerClient()
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, payload=STEAM_RESPONSE)
        m.get(GP_URL_PATTERN, payload=[])
        games = await client.get_free_games()

    steam_games = [g for g in games if g.platform == "steam"]
    assert len(steam_games) == 1
    assert steam_games[0].id == "1001"
    assert steam_games[0].title == "Warhammer 40,000: Gladius"


async def test_returns_games_from_both_platforms_by_default():
    client = GamerPowerClient()
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, payload=STEAM_RESPONSE)
        m.get(GP_URL_PATTERN, payload=EPIC_RESPONSE)
        games = await client.get_free_games()

    platforms = {g.platform for g in games}
    assert "steam" in platforms
    assert "epic-games-store" in platforms


async def test_platform_field_is_set_correctly():
    client = GamerPowerClient()
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, payload=STEAM_RESPONSE)
        m.get(GP_URL_PATTERN, payload=EPIC_RESPONSE)
        games = await client.get_free_games()

    steam_game = next(g for g in games if g.platform == "steam")
    epic_game = next(g for g in games if g.platform == "epic-games-store")
    assert steam_game.id == "1001"
    assert epic_game.id == "2001"


async def test_parsed_game_fields():
    client = GamerPowerClient()
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, payload=STEAM_RESPONSE)
        m.get(GP_URL_PATTERN, payload=[])
        games = await client.get_free_games()

    g = games[0]
    assert isinstance(g, FreeGame)
    assert g.url == "https://store.steampowered.com/app/489630/"
    assert g.image_url == "https://example.com/warhammer.jpg"
    assert g.expires_at == datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)


async def test_end_date_na_becomes_none():
    client = GamerPowerClient()
    single = [{**STEAM_RESPONSE[0], "end_date": "N/A"}]
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, payload=single)
        m.get(GP_URL_PATTERN, payload=[])
        games = await client.get_free_games()

    assert games[0].expires_at is None


async def test_returns_empty_on_http_error():
    client = GamerPowerClient()
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, status=500)
        m.get(GP_URL_PATTERN, status=500)
        games = await client.get_free_games()

    assert games == []


async def test_returns_empty_on_network_error():
    client = GamerPowerClient()
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, exception=aiohttp.ClientConnectionError("timeout"))
        m.get(GP_URL_PATTERN, exception=aiohttp.ClientConnectionError("timeout"))
        games = await client.get_free_games()

    assert games == []


async def test_returns_empty_on_timeout():
    client = GamerPowerClient()
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, exception=asyncio.TimeoutError())
        m.get(GP_URL_PATTERN, exception=asyncio.TimeoutError())
        games = await client.get_free_games()

    assert games == []


async def test_returns_empty_on_invalid_json():
    client = GamerPowerClient()
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, body="not json", content_type="application/json")
        m.get(GP_URL_PATTERN, body="not json", content_type="application/json")
        games = await client.get_free_games()

    assert games == []


async def test_skips_items_missing_id():
    client = GamerPowerClient()
    item_without_id = {k: v for k, v in STEAM_RESPONSE[0].items() if k != "id"}
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, payload=[item_without_id, STEAM_RESPONSE[0]])
        m.get(GP_URL_PATTERN, payload=[])
        games = await client.get_free_games()

    assert [g.id for g in games] == ["1001"]


async def test_single_platform_fetch():
    client = GamerPowerClient()
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, payload=STEAM_RESPONSE)
        games = await client.get_free_games(platforms=["steam"])

    assert all(g.platform == "steam" for g in games)


async def test_worth_parsed_correctly():
    client = GamerPowerClient()
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, payload=STEAM_RESPONSE)
        m.get(GP_URL_PATTERN, payload=[])
        games = await client.get_free_games()

    assert games[0].worth == "$39.99"


async def test_worth_na_becomes_none():
    client = GamerPowerClient()
    single = [{**STEAM_RESPONSE[0], "worth": "N/A"}]
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, payload=single)
        m.get(GP_URL_PATTERN, payload=[])
        games = await client.get_free_games()

    assert games[0].worth is None


async def test_worth_zero_becomes_none():
    client = GamerPowerClient()
    single = [{**STEAM_RESPONSE[0], "worth": "$0.00"}]
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, payload=single)
        m.get(GP_URL_PATTERN, payload=[])
        games = await client.get_free_games()

    assert games[0].worth is None


async def test_expires_at_parsed_as_datetime():
    client = GamerPowerClient()
    with aioresponses() as m:
        m.get(GP_URL_PATTERN, payload=STEAM_RESPONSE)
        m.get(GP_URL_PATTERN, payload=[])
        games = await client.get_free_games()

    assert isinstance(games[0].expires_at, datetime)
    assert games[0].expires_at.tzinfo is not None
