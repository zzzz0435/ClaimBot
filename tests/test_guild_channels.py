import json
import pytest
from pathlib import Path
from storage.guild_channels import GuildChannels


def test_creates_file_if_missing(tmp_path):
    gc = GuildChannels(tmp_path / "gc.json")
    assert (tmp_path / "gc.json").exists()
    assert gc.all_channels() == []


def test_set_and_retrieve_channel(tmp_path):
    gc = GuildChannels(tmp_path / "gc.json")
    gc.set(guild_id=111, channel_id=999)
    assert 999 in gc.all_channels()


def test_set_overwrites_existing_guild(tmp_path):
    gc = GuildChannels(tmp_path / "gc.json")
    gc.set(guild_id=111, channel_id=100)
    gc.set(guild_id=111, channel_id=200)
    assert gc.all_channels() == [200]


def test_persists_across_instances(tmp_path):
    path = tmp_path / "gc.json"
    gc = GuildChannels(path)
    gc.set(guild_id=111, channel_id=999)
    gc2 = GuildChannels(path)
    assert 999 in gc2.all_channels()


def test_resets_on_corrupt_file(tmp_path):
    path = tmp_path / "gc.json"
    path.write_text("{{invalid}}")
    gc = GuildChannels(path)
    assert gc.all_channels() == []


def test_get_returns_channel_id(tmp_path):
    gc = GuildChannels(tmp_path / "gc.json")
    gc.set(guild_id=111, channel_id=999)
    assert gc.get(111) == 999


def test_get_returns_none_when_not_set(tmp_path):
    gc = GuildChannels(tmp_path / "gc.json")
    assert gc.get(111) is None


def test_has_returns_true_when_set(tmp_path):
    gc = GuildChannels(tmp_path / "gc.json")
    gc.set(guild_id=111, channel_id=999)
    assert gc.has(111) is True


def test_has_returns_false_when_not_set(tmp_path):
    gc = GuildChannels(tmp_path / "gc.json")
    assert gc.has(111) is False
