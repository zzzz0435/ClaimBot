from storage.guild_price_alerts import GuildPriceAlerts


def test_default_is_false(tmp_path):
    g = GuildPriceAlerts(tmp_path / "pa.json")
    assert g.get(111) is False


def test_set_and_get_enabled(tmp_path):
    g = GuildPriceAlerts(tmp_path / "pa.json")
    g.set(111, True)
    assert g.get(111) is True


def test_set_and_get_disabled(tmp_path):
    g = GuildPriceAlerts(tmp_path / "pa.json")
    g.set(111, True)
    g.set(111, False)
    assert g.get(111) is False


def test_guilds_independent(tmp_path):
    g = GuildPriceAlerts(tmp_path / "pa.json")
    g.set(1, True)
    assert g.get(2) is False


def test_persists_across_instances(tmp_path):
    path = tmp_path / "pa.json"
    g = GuildPriceAlerts(path)
    g.set(42, True)
    g2 = GuildPriceAlerts(path)
    assert g2.get(42) is True


def test_resets_on_corrupt_file(tmp_path):
    path = tmp_path / "pa.json"
    path.write_text("{{invalid}}")
    g = GuildPriceAlerts(path)
    assert g.get(111) is False
