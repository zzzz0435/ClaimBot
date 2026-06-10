from storage.seen_price_lows import SeenPriceLows


def test_is_new_low_when_never_seen(tmp_path):
    s = SeenPriceLows(tmp_path / "lows.json")
    assert s.is_new_low(1, "game_a", 9.99) is True


def test_is_not_new_low_at_same_price(tmp_path):
    s = SeenPriceLows(tmp_path / "lows.json")
    s.mark(1, "game_a", 9.99)
    assert s.is_new_low(1, "game_a", 9.99) is False


def test_is_new_low_when_price_drops(tmp_path):
    s = SeenPriceLows(tmp_path / "lows.json")
    s.mark(1, "game_a", 9.99)
    assert s.is_new_low(1, "game_a", 7.49) is True


def test_is_not_new_low_when_price_rises(tmp_path):
    s = SeenPriceLows(tmp_path / "lows.json")
    s.mark(1, "game_a", 9.99)
    assert s.is_new_low(1, "game_a", 12.99) is False


def test_mark_updates_stored_price(tmp_path):
    s = SeenPriceLows(tmp_path / "lows.json")
    s.mark(1, "game_a", 9.99)
    s.mark(1, "game_a", 7.49)
    assert s.is_new_low(1, "game_a", 7.49) is False
    assert s.is_new_low(1, "game_a", 5.00) is True


def test_guilds_are_independent(tmp_path):
    s = SeenPriceLows(tmp_path / "lows.json")
    s.mark(1, "game_a", 9.99)
    assert s.is_new_low(2, "game_a", 9.99) is True


def test_persists_across_instances(tmp_path):
    path = tmp_path / "lows.json"
    s1 = SeenPriceLows(path)
    s1.mark(1, "game_a", 9.99)
    s2 = SeenPriceLows(path)
    assert s2.is_new_low(1, "game_a", 9.99) is False


def test_resets_on_corrupt_file(tmp_path):
    path = tmp_path / "lows.json"
    path.write_text("{{invalid}}")
    s = SeenPriceLows(path)
    assert s.is_new_low(1, "game_a", 9.99) is True


def test_corrupt_file_backed_up_before_reset(tmp_path):
    path = tmp_path / "lows.json"
    path.write_text("{{invalid}}")
    SeenPriceLows(path)
    bak = tmp_path / "lows.json.corrupt.bak"
    assert bak.read_text() == "{{invalid}}"
