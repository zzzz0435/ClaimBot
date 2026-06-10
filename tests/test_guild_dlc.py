from storage.guild_dlc import GuildDLC


def test_default_is_false(tmp_path):
    gd = GuildDLC(tmp_path / "dlc.json")
    assert gd.get(111) is False


def test_set_and_get_enabled(tmp_path):
    gd = GuildDLC(tmp_path / "dlc.json")
    gd.set(111, True)
    assert gd.get(111) is True


def test_set_and_get_disabled(tmp_path):
    gd = GuildDLC(tmp_path / "dlc.json")
    gd.set(111, True)
    gd.set(111, False)
    assert gd.get(111) is False


def test_persists_across_instances(tmp_path):
    path = tmp_path / "dlc.json"
    gd = GuildDLC(path)
    gd.set(111, True)
    gd2 = GuildDLC(path)
    assert gd2.get(111) is True


def test_guilds_independent(tmp_path):
    gd = GuildDLC(tmp_path / "dlc.json")
    gd.set(1, True)
    assert gd.get(2) is False


def test_resets_on_corrupt_file(tmp_path):
    path = tmp_path / "dlc.json"
    path.write_text("{{invalid}}")
    gd = GuildDLC(path)
    assert gd.get(111) is False


def test_corrupt_file_backed_up_before_reset(tmp_path):
    path = tmp_path / "dlc.json"
    path.write_text("{{invalid}}")
    GuildDLC(path)
    bak = tmp_path / "dlc.json.corrupt.bak"
    assert bak.read_text() == "{{invalid}}"
