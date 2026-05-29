import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from services.gamerpower_client import FreeGame
from services.itad_client import PriceDeal
from cogs.free_games import FreeGamesCog, filter_new_games, build_embed, build_view, build_price_embed
from storage.guild_channels import GuildChannels
from storage.guild_dlc import GuildDLC
from storage.guild_price_alerts import GuildPriceAlerts
from storage.guild_roles import GuildRoles
from storage.guild_platforms import GuildPlatforms
from storage.seen_games import SeenGames
from storage.seen_price_lows import SeenPriceLows

EXPIRY = datetime(2026, 6, 1, 17, 0, 0, tzinfo=timezone.utc)


def make_game(
    game_id: str,
    expires_at: datetime | None = None,
    platform: str = "steam",
    worth: str | None = None,
) -> FreeGame:
    return FreeGame(
        id=game_id,
        title=f"Game {game_id}",
        url=f"https://store.steampowered.com/app/{game_id}/",
        image_url="https://example.com/img.jpg",
        expires_at=expires_at,
        platform=platform,
        worth=worth,
    )


# --- filter_new_games ---

def test_filters_out_seen_games():
    games = [make_game("1"), make_game("2"), make_game("3")]
    result = filter_new_games(games, seen_ids={"1"})
    assert [g.id for g in result] == ["2", "3"]


def test_returns_empty_when_all_seen():
    games = [make_game("1"), make_game("2")]
    assert filter_new_games(games, seen_ids={"1", "2"}) == []


def test_returns_all_when_nothing_seen():
    games = [make_game("1"), make_game("2")]
    assert len(filter_new_games(games, seen_ids=set())) == 2


# --- build_embed ---

def test_embed_has_title_and_url():
    embed = build_embed(make_game("1"))
    assert embed.title == "Game 1"
    assert embed.url == "https://store.steampowered.com/app/1/"


def test_embed_steam_color():
    embed = build_embed(make_game("1", platform="steam"))
    assert embed.color == discord.Color(0x2ECC71)


def test_embed_epic_color():
    embed = build_embed(make_game("1", platform="epic-games-store"))
    assert embed.color == discord.Color(0x0074E4)


def test_embed_author_steam_fallback():
    # 無 emoji_ids 時使用 Unicode fallback
    embed = build_embed(make_game("1", platform="steam"))
    assert embed.author.name == "🎮 Steam 限時免費"
    assert embed.author.icon_url is None


def test_embed_author_epic_fallback():
    embed = build_embed(make_game("1", platform="epic-games-store"))
    assert embed.author.name == "⚡ Epic Games 限時免費"


def test_embed_author_with_emoji_ids():
    # 有 emoji_ids 時使用 icon_url 顯示品牌 Logo
    emoji_ids = {"steam": 123456789}
    embed = build_embed(make_game("1", platform="steam"), emoji_ids=emoji_ids)
    assert embed.author.name == "Steam 限時免費"
    assert embed.author.icon_url == "https://cdn.discordapp.com/emojis/123456789.png"


def test_embed_author_icon_url_not_set_without_emoji_ids():
    embed = build_embed(make_game("1", platform="steam"), emoji_ids=None)
    assert embed.author.icon_url is None


def test_embed_has_image():
    embed = build_embed(make_game("1"))
    assert embed.image.url == "https://example.com/img.jpg"


def test_embed_no_image_when_empty():
    game = FreeGame(id="1", title="T", url="https://x.com", image_url="",
                    expires_at=None, platform="steam", worth=None)
    embed = build_embed(game)
    assert embed.image.url is None


def test_embed_shows_worth():
    embed = build_embed(make_game("1", worth="$49.99"))
    assert any(f.name == "💰 原價" and f.value == "$49.99" for f in embed.fields)


def test_embed_no_worth_field_when_none():
    embed = build_embed(make_game("1", worth=None))
    assert not any(f.name == "💰 原價" for f in embed.fields)


def test_embed_shows_expiry_when_present():
    embed = build_embed(make_game("1", expires_at=EXPIRY))
    assert any(f.name == "⏰ 限免截止" for f in embed.fields)


def test_embed_no_expiry_when_none():
    embed = build_embed(make_game("1", expires_at=None))
    assert not any(f.name == "⏰ 限免截止" for f in embed.fields)


def test_embed_footer():
    embed = build_embed(make_game("1"))
    assert embed.footer.text == "資料來源：GamerPower"


# --- build_view ---

def test_view_has_steam_button_fallback():
    # 無 emoji_ids 時按鈕 emoji 為 🎮
    view = build_view(make_game("1", platform="steam"))
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    assert len(buttons) == 1
    assert "Steam" in buttons[0].label
    assert buttons[0].url.endswith("/1/")


def test_view_has_epic_button_fallback():
    view = build_view(make_game("1", platform="epic-games-store"))
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    assert "Epic" in buttons[0].label


def test_view_button_uses_partial_emoji_when_emoji_ids_provided():
    # 有 emoji_ids 時按鈕 emoji 為 PartialEmoji
    emoji_ids = {"steam": 987654321}
    view = build_view(make_game("1", platform="steam"), emoji_ids=emoji_ids)
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    assert len(buttons) == 1
    assert isinstance(buttons[0].emoji, discord.PartialEmoji)
    assert buttons[0].emoji.id == 987654321


def test_view_no_button_when_no_url():
    game = FreeGame(id="1", title="T", url="", image_url="",
                    expires_at=None, platform="steam", worth=None)
    view = build_view(game)
    assert len(view.children) == 0


# --- _do_check() ---

def _make_cog(tmp_path) -> FreeGamesCog:
    bot = MagicMock()
    bot.wait_until_ready = AsyncMock()
    cog = object.__new__(FreeGamesCog)
    cog._bot = bot
    cog._emoji_ids = {}
    cog._client = AsyncMock()
    cog._epic_client = AsyncMock()
    cog._itad_client = None  # 預設停用，避免真實 API 呼叫
    cog._seen = SeenGames(tmp_path / "seen.json")
    cog._guild_channels = GuildChannels(tmp_path / "channels.json")
    cog._guild_roles = GuildRoles(tmp_path / "roles.json")
    cog._guild_platforms = GuildPlatforms(tmp_path / "platforms.json")
    cog._guild_dlc = GuildDLC(tmp_path / "dlc.json")
    cog._guild_price_alerts = GuildPriceAlerts(tmp_path / "price_alerts.json")
    cog._seen_price_lows = SeenPriceLows(tmp_path / "price_lows.json")
    cog._last_check = None
    cog._check_lock = asyncio.Lock()
    return cog


def _make_price_deal(deal_id: str, price: float = 9.99, store_low: float = 9.99) -> PriceDeal:
    return PriceDeal(
        id=deal_id,
        title=f"Game {deal_id}",
        url=f"https://store.steampowered.com/app/{deal_id}/",
        current_price=price,
        original_price=19.99,
        currency="USD",
        historical_low=store_low,
        discount_pct=50,
        image_url="https://cdn.akamai.steamstatic.com/steam/apps/12345/header.jpg",
    )


def _http_error() -> discord.HTTPException:
    resp = MagicMock()
    resp.status = 403
    return discord.HTTPException(resp, "Missing Permissions")


async def test_do_check_marks_all_sent_games_as_seen(tmp_path):
    cog = _make_cog(tmp_path)
    cog._guild_channels.set(1, 100)
    cog._client.get_free_games.return_value = [make_game("A"), make_game("B")]
    cog._bot.get_channel.return_value = AsyncMock()

    await cog._do_check()

    assert "A" in cog._seen.seen_ids(1)
    assert "B" in cog._seen.seen_ids(1)


async def test_do_check_only_marks_successful_sends_as_seen(tmp_path):
    cog = _make_cog(tmp_path)
    cog._guild_channels.set(1, 100)
    cog._client.get_free_games.return_value = [make_game("A"), make_game("B")]

    channel = AsyncMock()
    channel.send.side_effect = [None, _http_error()]
    cog._bot.get_channel.return_value = channel

    await cog._do_check()

    assert "A" in cog._seen.seen_ids(1)
    assert "B" not in cog._seen.seen_ids(1)


async def test_do_check_skips_missing_channel_without_crash(tmp_path):
    cog = _make_cog(tmp_path)
    cog._guild_channels.set(1, 100)
    cog._client.get_free_games.return_value = [make_game("A")]
    cog._bot.get_channel.return_value = None

    await cog._do_check()

    assert "A" not in cog._seen.seen_ids(1)


async def test_do_check_skips_when_no_guilds(tmp_path):
    cog = _make_cog(tmp_path)
    cog._client.get_free_games.return_value = [make_game("A")]

    await cog._do_check()

    cog._client.get_free_games.assert_not_called()
    assert "A" not in cog._seen.seen_ids(1)


async def test_do_check_tracks_seen_per_guild_independently(tmp_path):
    cog = _make_cog(tmp_path)
    cog._guild_channels.set(1, 100)
    cog._guild_channels.set(2, 200)
    cog._client.get_free_games.return_value = [make_game("A")]

    bad_channel = AsyncMock()
    bad_channel.send.side_effect = _http_error()
    good_channel = AsyncMock()

    def get_channel(cid):
        return bad_channel if cid == 100 else good_channel

    cog._bot.get_channel.side_effect = get_channel

    await cog._do_check()

    good_channel.send.assert_called_once()
    assert "A" not in cog._seen.seen_ids(1)  # 失敗的 guild 不標 seen
    assert "A" in cog._seen.seen_ids(2)       # 成功的 guild 標 seen


async def test_do_check_excludes_dlc_by_default(tmp_path):
    cog = _make_cog(tmp_path)
    cog._guild_channels.set(1, 100)
    dlc_game = make_game("DLC1", platform="steam")
    dlc_game = FreeGame(
        id="DLC1", title="DLC Pack", url="https://store.steampowered.com/app/DLC1/",
        image_url="", expires_at=None, platform="steam", worth=None, kind="dlc"
    )
    full_game = make_game("G1", platform="steam")
    cog._client.get_free_games.return_value = [full_game, dlc_game]
    channel = AsyncMock()
    cog._bot.get_channel.return_value = channel

    await cog._do_check()

    assert channel.send.call_count == 1
    assert "G1" in cog._seen.seen_ids(1)
    assert "DLC1" not in cog._seen.seen_ids(1)


async def test_do_check_includes_dlc_when_enabled(tmp_path):
    cog = _make_cog(tmp_path)
    cog._guild_channels.set(1, 100)
    cog._guild_dlc.set(1, True)
    dlc_game = FreeGame(
        id="DLC1", title="DLC Pack", url="https://store.steampowered.com/app/DLC1/",
        image_url="", expires_at=None, platform="steam", worth=None, kind="dlc"
    )
    full_game = make_game("G1", platform="steam")
    cog._client.get_free_games.return_value = [full_game, dlc_game]
    channel = AsyncMock()
    cog._bot.get_channel.return_value = channel

    await cog._do_check()

    assert channel.send.call_count == 2
    assert "G1" in cog._seen.seen_ids(1)
    assert "DLC1" in cog._seen.seen_ids(1)


async def test_do_check_skips_when_lock_held(tmp_path):
    cog = _make_cog(tmp_path)
    cog._guild_channels.set(1, 100)
    cog._client.get_free_games.return_value = [make_game("A")]

    async with cog._check_lock:
        await cog._do_check()

    cog._client.get_free_games.assert_not_called()


async def test_do_check_migrates_using_bot_guilds_not_channels(tmp_path):
    import json
    cog = _make_cog(tmp_path)
    # 沒有設定任何頻道，但 bot.guilds 有 guild 42
    mock_guild = MagicMock()
    mock_guild.id = 42
    cog._bot.guilds = [mock_guild]

    seen_path = tmp_path / "seen.json"
    seen_path.write_text(json.dumps({"seen_ids": ["A"]}))
    from storage.seen_games import SeenGames
    cog._seen = SeenGames(seen_path)

    await cog._do_check()

    # channel 未設定所以早退，但 migration 應已完成
    assert "A" in cog._seen.seen_ids(42)
    assert not cog._seen.needs_migration()


async def test_do_check_migrates_legacy_before_filtering(tmp_path):
    import json
    cog = _make_cog(tmp_path)
    cog._guild_channels.set(1, 100)

    # 設定 bot.guilds，讓 migration 能套用到 guild 1
    mock_guild = MagicMock()
    mock_guild.id = 1
    cog._bot.guilds = [mock_guild]

    # game-A 已在舊格式 seen_ids 中
    seen_path = tmp_path / "seen.json"
    seen_path.write_text(json.dumps({"seen_ids": ["A"]}))
    from storage.seen_games import SeenGames
    cog._seen = SeenGames(seen_path)

    cog._client.get_free_games.return_value = [make_game("A"), make_game("B")]
    channel = AsyncMock()
    cog._bot.get_channel.return_value = channel

    await cog._do_check()

    # A 因舊格式遷移視為已見過，不應重發；B 應發送
    assert channel.send.call_count == 1
    assert "A" in cog._seen.seen_ids(1)  # 已遷移
    assert "B" in cog._seen.seen_ids(1)  # 新發送


# --- build_price_embed ---

def test_price_embed_has_title_and_url():
    deal = _make_price_deal("1234")
    embed = build_price_embed(deal)
    assert embed.title == "Game 1234"
    assert "1234" in embed.url


def test_price_embed_has_price_fields():
    deal = _make_price_deal("1", price=9.99, store_low=9.99)
    embed = build_price_embed(deal)
    field_names = [f.name for f in embed.fields]
    assert "💰 目前售價" in field_names
    assert "📉 歷史最低" in field_names
    assert "🔖 原價" in field_names


def test_price_embed_footer():
    embed = build_price_embed(_make_price_deal("1"))
    assert "IsThereAnyDeal" in embed.footer.text


# --- _check_price_lows (via _do_check) ---

async def test_price_lows_skipped_when_itad_client_none(tmp_path):
    cog = _make_cog(tmp_path)
    cog._guild_channels.set(1, 100)
    cog._guild_price_alerts.set(1, True)
    cog._itad_client = None  # 無 ITAD client
    cog._client.get_free_games.return_value = []
    channel = AsyncMock()
    cog._bot.get_channel.return_value = channel

    await cog._do_check()

    # 無 ITAD client 時不應送出任何歷史新低通知
    channel.send.assert_not_called()


async def test_price_lows_sends_new_low(tmp_path):
    cog = _make_cog(tmp_path)
    cog._guild_channels.set(1, 100)
    cog._guild_price_alerts.set(1, True)

    itad = AsyncMock()
    itad.get_steam_historical_lows.return_value = [_make_price_deal("P1")]
    cog._itad_client = itad

    cog._client.get_free_games.return_value = []
    channel = AsyncMock()
    cog._bot.get_channel.return_value = channel

    await cog._do_check()

    channel.send.assert_called_once()
    assert cog._seen_price_lows.is_new_low(1, "P1", 9.99) is False  # 已標記


async def test_price_lows_skips_already_notified(tmp_path):
    cog = _make_cog(tmp_path)
    cog._guild_channels.set(1, 100)
    cog._guild_price_alerts.set(1, True)
    cog._seen_price_lows.mark(1, "P1", 9.99)  # 已通知過

    itad = AsyncMock()
    itad.get_steam_historical_lows.return_value = [_make_price_deal("P1", price=9.99)]
    cog._itad_client = itad

    cog._client.get_free_games.return_value = []
    channel = AsyncMock()
    cog._bot.get_channel.return_value = channel

    await cog._do_check()

    channel.send.assert_not_called()


async def test_price_lows_notifies_new_record_low(tmp_path):
    cog = _make_cog(tmp_path)
    cog._guild_channels.set(1, 100)
    cog._guild_price_alerts.set(1, True)
    cog._seen_price_lows.mark(1, "P1", 9.99)  # 上次通知 9.99

    itad = AsyncMock()
    itad.get_steam_historical_lows.return_value = [_make_price_deal("P1", price=7.49, store_low=7.49)]
    cog._itad_client = itad

    cog._client.get_free_games.return_value = []
    channel = AsyncMock()
    cog._bot.get_channel.return_value = channel

    await cog._do_check()

    channel.send.assert_called_once()
    assert cog._seen_price_lows.is_new_low(1, "P1", 7.49) is False  # 更新到 7.49


async def test_price_lows_skipped_when_guild_disabled(tmp_path):
    cog = _make_cog(tmp_path)
    cog._guild_channels.set(1, 100)
    # guild_price_alerts 預設 False，不啟用

    itad = AsyncMock()
    itad.get_steam_historical_lows.return_value = [_make_price_deal("P1")]
    cog._itad_client = itad

    cog._client.get_free_games.return_value = []
    channel = AsyncMock()
    cog._bot.get_channel.return_value = channel

    await cog._do_check()

    itad.get_steam_historical_lows.assert_not_called()
    channel.send.assert_not_called()
