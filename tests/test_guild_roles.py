import pytest
from storage.guild_roles import GuildRoles


def test_creates_file_if_missing(tmp_path):
    gr = GuildRoles(tmp_path / "gr.json")
    assert (tmp_path / "gr.json").exists()
    assert gr.get(111) is None


def test_set_and_get_role(tmp_path):
    gr = GuildRoles(tmp_path / "gr.json")
    gr.set(guild_id=111, role_id=888)
    assert gr.get(111) == 888


def test_clear_role(tmp_path):
    gr = GuildRoles(tmp_path / "gr.json")
    gr.set(guild_id=111, role_id=888)
    gr.clear(111)
    assert gr.get(111) is None


def test_clear_nonexistent_is_noop(tmp_path):
    gr = GuildRoles(tmp_path / "gr.json")
    gr.clear(999)
    assert gr.get(999) is None


def test_persists_across_instances(tmp_path):
    path = tmp_path / "gr.json"
    gr = GuildRoles(path)
    gr.set(guild_id=111, role_id=888)
    gr2 = GuildRoles(path)
    assert gr2.get(111) == 888


def test_resets_on_corrupt_file(tmp_path):
    path = tmp_path / "gr.json"
    path.write_text("{{invalid}}")
    gr = GuildRoles(path)
    assert gr.get(111) is None
