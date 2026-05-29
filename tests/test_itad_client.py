import pytest
from services.itad_client import ITADClient, PriceDeal, _extract_steam_appid


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
