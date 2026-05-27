import pytest
from storage.guild_platforms import GuildPlatforms, DEFAULT_PLATFORMS


def test_creates_file_if_missing(tmp_path):
    gp = GuildPlatforms(tmp_path / "gp.json")
    assert (tmp_path / "gp.json").exists()


def test_default_platforms_when_not_set(tmp_path):
    gp = GuildPlatforms(tmp_path / "gp.json")
    assert gp.get(111) == DEFAULT_PLATFORMS


def test_set_and_get_platforms(tmp_path):
    gp = GuildPlatforms(tmp_path / "gp.json")
    gp.set(guild_id=111, platforms=["steam"])
    assert gp.get(111) == ["steam"]


def test_set_both_platforms(tmp_path):
    gp = GuildPlatforms(tmp_path / "gp.json")
    gp.set(guild_id=111, platforms=["steam", "epic-games-store"])
    result = gp.get(111)
    assert "steam" in result
    assert "epic-games-store" in result


def test_persists_across_instances(tmp_path):
    path = tmp_path / "gp.json"
    gp = GuildPlatforms(path)
    gp.set(guild_id=111, platforms=["epic-games-store"])
    gp2 = GuildPlatforms(path)
    assert gp2.get(111) == ["epic-games-store"]


def test_resets_on_corrupt_file(tmp_path):
    path = tmp_path / "gp.json"
    path.write_text("{{invalid}}")
    gp = GuildPlatforms(path)
    assert gp.get(111) == DEFAULT_PLATFORMS
