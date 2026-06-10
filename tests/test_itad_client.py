import asyncio
import re

import pytest
from aioresponses import aioresponses
from services.itad_client import ITADClient, PriceDeal, _extract_steam_appid

ITAD_DEALS_PATTERN = re.compile(r"https://api\.isthereanydeal\.com/deals/v2.*")
STEAMSPY_PATTERN = re.compile(r"https://steamspy\.com/api\.php.*")


# --- _extract_steam_appid ---

def test_extracts_appid_from_store_url():
    url = "https://store.steampowered.com/app/1091500/Cyberpunk_2077/"
    assert _extract_steam_appid(url) == "1091500"


def test_returns_none_for_non_steam_url():
    assert _extract_steam_appid("https://example.com/game") is None


def test_returns_none_for_empty_url():
    assert _extract_steam_appid("") is None


# --- _parse_store_low ---

def test_parse_store_low_plain_number():
    client = ITADClient("fake_key")
    deal = {"storeLow": 9.99}
    assert client._parse_store_low(deal) == pytest.approx(9.99)


def test_parse_store_low_dict_format():
    client = ITADClient("fake_key")
    deal = {"storeLow": {"amount": 7.49, "currency": "USD"}}
    assert client._parse_store_low(deal) == pytest.approx(7.49)


def test_parse_store_low_none():
    client = ITADClient("fake_key")
    assert client._parse_store_low({"storeLow": None}) == 0.0


def test_parse_store_low_missing_key():
    client = ITADClient("fake_key")
    assert client._parse_store_low({}) == 0.0


# --- _is_at_historical_low ---

def _make_deal(price: float, store_low: float) -> dict:
    return {
        "game": {"id": "abc", "title": "Game"},
        "deal": {
            "price": {"amount": price, "currency": "USD"},
            "regular": {"amount": 19.99, "currency": "USD"},
            "cut": 50,
            "storeLow": store_low,
            "url": "https://store.steampowered.com/app/12345/",
        },
    }


def test_at_historical_low_when_price_equals_store_low():
    client = ITADClient("fake_key")
    assert client._is_at_historical_low(_make_deal(9.99, 9.99)) is True


def test_at_historical_low_when_price_below_store_low():
    client = ITADClient("fake_key")
    assert client._is_at_historical_low(_make_deal(7.99, 9.99)) is True


def test_not_at_historical_low_when_price_above():
    client = ITADClient("fake_key")
    assert client._is_at_historical_low(_make_deal(14.99, 9.99)) is False


def test_not_at_historical_low_when_free():
    client = ITADClient("fake_key")
    assert client._is_at_historical_low(_make_deal(0.0, 0.0)) is False


def test_not_at_historical_low_when_store_low_zero():
    client = ITADClient("fake_key")
    assert client._is_at_historical_low(_make_deal(9.99, 0.0)) is False


# --- get_steam_historical_lows 整合測試 ---

def _make_api_deal(game_id: str, appid: str) -> dict:
    return {
        "game": {"id": game_id, "title": f"Game {game_id}"},
        "deal": {
            "price": {"amount": 9.99, "currency": "USD"},
            "regular": {"amount": 19.99, "currency": "USD"},
            "cut": 50,
            "storeLow": 9.99,
            "url": f"https://store.steampowered.com/app/{appid}/",
        },
    }


async def test_returns_empty_on_deals_timeout():
    client = ITADClient("fake_key")
    with aioresponses() as m:
        m.get(ITAD_DEALS_PATTERN, exception=asyncio.TimeoutError())
        deals = await client.get_steam_historical_lows()

    assert deals == []


async def test_returns_empty_on_deals_invalid_json():
    client = ITADClient("fake_key")
    with aioresponses() as m:
        m.get(ITAD_DEALS_PATTERN, body="not json", content_type="application/json")
        deals = await client.get_steam_historical_lows()

    assert deals == []


async def test_steamspy_timeout_treated_as_zero_reviews():
    client = ITADClient("fake_key")
    with aioresponses() as m:
        m.get(ITAD_DEALS_PATTERN, payload={"list": [_make_api_deal("A", "111")]})
        m.get(STEAMSPY_PATTERN, exception=asyncio.TimeoutError())
        deals = await client.get_steam_historical_lows()

    assert deals == []  # 評論數視為 0 被過濾，但不應拋出例外


async def test_skips_deal_missing_fields_keeps_valid_ones():
    client = ITADClient("fake_key")
    good = _make_api_deal("good", "111")
    bad = _make_api_deal("bad", "222")
    del bad["deal"]["regular"]
    del bad["deal"]["cut"]
    with aioresponses() as m:
        m.get(ITAD_DEALS_PATTERN, payload={"list": [bad, good]})
        m.get(STEAMSPY_PATTERN, payload={"positive": 600, "negative": 100}, repeat=True)
        deals = await client.get_steam_historical_lows()

    assert [d.id for d in deals] == ["good"]
