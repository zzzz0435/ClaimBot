"""JSON 檔案的 atomic 寫入與損毀備份工具。

直接 write_text 覆寫在程序中途被殺時會留下半截檔案；
這裡一律先寫暫存檔再 os.replace()，確保檔案不是舊版就是新版。
"""
import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)


def atomic_write_json(path: Path, data) -> None:
    """將 data 以 JSON 格式 atomic 寫入 path。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def backup_corrupt(path: Path) -> None:
    """將損毀的檔案改名為 <name>.corrupt.bak 保留現場；檔案不存在時不動作。"""
    if not path.exists():
        return
    bak = path.with_name(path.name + ".corrupt.bak")
    os.replace(path, bak)
    log.warning("已將損毀檔案備份至 %s", bak)
