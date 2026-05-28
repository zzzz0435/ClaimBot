import json
import pytest
from pathlib import Path
from storage.seen_games import SeenGames


def test_creates_file_if_missing(tmp_path):
    path = tmp_path / "seen.json"
    sg = SeenGames(path)
    assert path.exists()
    assert sg.seen_ids(1) == set()


def test_seen_ids_returns_empty_for_unknown_guild(tmp_path):
    sg = SeenGames(tmp_path / "seen.json")
    assert sg.seen_ids(999) == set()


def test_add_and_retrieve_per_guild(tmp_path):
    sg = SeenGames(tmp_path / "seen.json")
    sg.add(1, {"game-A", "game-B"})
    assert sg.seen_ids(1) == {"game-A", "game-B"}
    assert sg.seen_ids(2) == set()


def test_add_is_cumulative(tmp_path):
    sg = SeenGames(tmp_path / "seen.json")
    sg.add(1, {"game-A"})
    sg.add(1, {"game-B"})
    assert sg.seen_ids(1) == {"game-A", "game-B"}


def test_different_guilds_tracked_independently(tmp_path):
    sg = SeenGames(tmp_path / "seen.json")
    sg.add(1, {"game-A"})
    sg.add(2, {"game-B"})
    assert sg.seen_ids(1) == {"game-A"}
    assert sg.seen_ids(2) == {"game-B"}


def test_persists_across_instances(tmp_path):
    path = tmp_path / "seen.json"
    sg = SeenGames(path)
    sg.add(1, {"game-A"})
    sg2 = SeenGames(path)
    assert "game-A" in sg2.seen_ids(1)


def test_resets_on_corrupt_file(tmp_path):
    path = tmp_path / "seen.json"
    path.write_text("not valid json {{{{")
    sg = SeenGames(path)
    assert sg.seen_ids(1) == set()
    assert path.exists()


def test_new_format_does_not_need_migration(tmp_path):
    sg = SeenGames(tmp_path / "seen.json")
    assert sg.needs_migration() is False


def test_old_format_detected_needs_migration(tmp_path):
    path = tmp_path / "seen.json"
    path.write_text(json.dumps({"seen_ids": ["game-A", "game-B"]}))
    sg = SeenGames(path)
    assert sg.needs_migration() is True
    assert sg.seen_ids(1) == set()  # 未遷移前 per-guild 為空


def test_migrate_applies_legacy_ids_to_all_guilds(tmp_path):
    path = tmp_path / "seen.json"
    path.write_text(json.dumps({"seen_ids": ["game-A", "game-B"]}))
    sg = SeenGames(path)
    sg.migrate([1, 2])
    assert "game-A" in sg.seen_ids(1)
    assert "game-B" in sg.seen_ids(1)
    assert "game-A" in sg.seen_ids(2)
    assert sg.needs_migration() is False


def test_migration_persists_across_instances(tmp_path):
    path = tmp_path / "seen.json"
    path.write_text(json.dumps({"seen_ids": ["game-A"]}))
    sg = SeenGames(path)
    sg.migrate([1])
    sg2 = SeenGames(path)
    assert "game-A" in sg2.seen_ids(1)
    assert not sg2.needs_migration()


def test_migrate_refuses_empty_guild_list(tmp_path):
    path = tmp_path / "seen.json"
    path.write_text(json.dumps({"seen_ids": ["game-A"]}))
    sg = SeenGames(path)
    sg.migrate([])
    assert sg.needs_migration() is True  # legacy_ids 保留，未被清除


def test_contains_per_guild(tmp_path):
    sg = SeenGames(tmp_path / "seen.json")
    sg.add(1, {"game-A"})
    assert sg.contains(1, "game-A") is True
    assert sg.contains(1, "game-B") is False
    assert sg.contains(2, "game-A") is False
