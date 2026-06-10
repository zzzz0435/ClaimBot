import json

import pytest
import storage.json_io as json_io
from storage.json_io import atomic_write_json, backup_corrupt


# --- atomic_write_json ---

def test_writes_json_data(tmp_path):
    path = tmp_path / "x.json"
    atomic_write_json(path, {"a": 1, "中文": "值"})
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1, "中文": "值"}


def test_overwrites_existing_content(tmp_path):
    path = tmp_path / "x.json"
    atomic_write_json(path, {"v": 1})
    atomic_write_json(path, {"v": 2})
    assert json.loads(path.read_text(encoding="utf-8")) == {"v": 2}


def test_leaves_no_tmp_file(tmp_path):
    path = tmp_path / "x.json"
    atomic_write_json(path, {"a": 1})
    assert [p.name for p in tmp_path.iterdir()] == ["x.json"]


def test_creates_parent_dirs(tmp_path):
    path = tmp_path / "sub" / "dir" / "x.json"
    atomic_write_json(path, {})
    assert path.exists()


def test_preserves_original_when_replace_fails(tmp_path, monkeypatch):
    path = tmp_path / "x.json"
    atomic_write_json(path, {"v": 1})

    def boom(src, dst):
        raise OSError("simulated crash")

    monkeypatch.setattr(json_io.os, "replace", boom)
    with pytest.raises(OSError):
        atomic_write_json(path, {"v": 2})

    # 寫入中斷時原檔必須完整保留
    assert json.loads(path.read_text(encoding="utf-8")) == {"v": 1}


# --- backup_corrupt ---

def test_backup_corrupt_renames_file(tmp_path):
    path = tmp_path / "x.json"
    path.write_text("{{bad json", encoding="utf-8")
    backup_corrupt(path)
    assert not path.exists()
    bak = tmp_path / "x.json.corrupt.bak"
    assert bak.read_text(encoding="utf-8") == "{{bad json"


def test_backup_corrupt_overwrites_previous_backup(tmp_path):
    path = tmp_path / "x.json"
    path.write_text("first", encoding="utf-8")
    backup_corrupt(path)
    path.write_text("second", encoding="utf-8")
    backup_corrupt(path)
    bak = tmp_path / "x.json.corrupt.bak"
    assert bak.read_text(encoding="utf-8") == "second"


def test_backup_corrupt_noop_when_missing(tmp_path):
    backup_corrupt(tmp_path / "nope.json")  # 不應拋出例外
