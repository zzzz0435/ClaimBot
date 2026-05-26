import json
import pytest
from pathlib import Path
from storage.seen_games import SeenGames


def test_creates_file_if_missing(tmp_path):
    path = tmp_path / "seen.json"
    sg = SeenGames(path)
    assert path.exists()
    assert sg.seen_ids == set()


def test_reads_existing_ids(tmp_path):
    path = tmp_path / "seen.json"
    path.write_text(json.dumps({"seen_ids": ["app/111", "app/222"]}))
    sg = SeenGames(path)
    assert sg.seen_ids == {"app/111", "app/222"}


def test_resets_on_corrupt_file(tmp_path):
    path = tmp_path / "seen.json"
    path.write_text("not valid json {{{{")
    sg = SeenGames(path)
    assert sg.seen_ids == set()
    assert path.exists()


def test_add_persists_new_ids(tmp_path):
    path = tmp_path / "seen.json"
    sg = SeenGames(path)
    sg.add({"app/123", "app/456"})
    sg2 = SeenGames(path)
    assert {"app/123", "app/456"} <= sg2.seen_ids


def test_add_is_cumulative(tmp_path):
    path = tmp_path / "seen.json"
    sg = SeenGames(path)
    sg.add({"app/1"})
    sg.add({"app/2"})
    assert sg.seen_ids == {"app/1", "app/2"}


def test_contains_known_id(tmp_path):
    path = tmp_path / "seen.json"
    sg = SeenGames(path)
    sg.add({"app/123"})
    assert sg.contains("app/123") is True
    assert sg.contains("app/999") is False
