from datetime import datetime, timezone

import discord
import pytest
from services.gamerpower_client import FreeGame
from cogs.free_games import filter_new_games, build_embed, build_view

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


def test_embed_author_steam():
    embed = build_embed(make_game("1", platform="steam"))
    assert embed.author.name == "🎮 Steam 限時免費"


def test_embed_author_epic():
    embed = build_embed(make_game("1", platform="epic-games-store"))
    assert embed.author.name == "⚡ Epic Games 限時免費"


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

def test_view_has_steam_button():
    view = build_view(make_game("1", platform="steam"))
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    assert len(buttons) == 1
    assert "Steam" in buttons[0].label
    assert buttons[0].url.endswith("/1/")


def test_view_has_epic_button():
    view = build_view(make_game("1", platform="epic-games-store"))
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    assert "Epic" in buttons[0].label


def test_view_no_button_when_no_url():
    game = FreeGame(id="1", title="T", url="", image_url="",
                    expires_at=None, platform="steam", worth=None)
    view = build_view(game)
    assert len(view.children) == 0
