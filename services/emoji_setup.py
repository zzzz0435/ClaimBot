import base64
import json
import logging
from pathlib import Path

import aiohttp

log = logging.getLogger(__name__)

EMOJI_IDS_PATH = Path("data/app_emojis.json")
ASSETS_DIR = Path("assets")

# Discord Application Emoji 的名稱（上傳時使用）
EMOJI_NAMES: dict[str, str] = {
    "steam": "claimbot_steam",
    "epic-games-store": "claimbot_epic",
}

# 對應的圖片檔名（放在 assets/ 目錄下）
EMOJI_ASSETS: dict[str, str] = {
    "steam": "steam.png",
    "epic-games-store": "epic.png",
}


class EmojiSetup:
    """
    管理 Discord Application Emoji 的上傳與快取。

    Bot 啟動時呼叫 ensure_emojis()，若 assets/ 下有對應圖片，
    會自動上傳成 Application Emoji 並將 ID 存入 data/app_emojis.json。
    找不到圖片時安靜跳過，讓呼叫方 fallback 回 Unicode emoji。
    """

    def __init__(self, application_id: str, token: str):
        self._app_id = application_id
        self._token = token
        self._ids: dict[str, int] = self._load()

    async def ensure_emojis(self) -> dict[str, int]:
        """確保所有平台的 Application Emoji 存在，回傳 {platform: emoji_id}。"""
        for platform, asset_file in EMOJI_ASSETS.items():
            asset_path = ASSETS_DIR / asset_file
            if not asset_path.exists():
                log.info("找不到 %s，跳過 Application Emoji 設定", asset_path)
                continue

            cached_id = self._ids.get(platform)
            if cached_id and await self._exists(cached_id):
                log.info("%s Application Emoji 已存在 (ID: %s)", platform, cached_id)
                continue

            # 快取失效或尚未上傳，重新上傳
            new_id = await self._upload(EMOJI_NAMES[platform], asset_path)
            if new_id:
                self._ids[platform] = new_id
                log.info("已上傳 %s Application Emoji (ID: %s)", platform, new_id)

        self._save()
        return dict(self._ids)

    async def _exists(self, emoji_id: int) -> bool:
        url = f"https://discord.com/api/v10/applications/{self._app_id}/emojis/{emoji_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self._headers()) as resp:
                    return resp.status == 200
        except aiohttp.ClientError:
            return False

    async def _upload(self, name: str, path: Path) -> int | None:
        suffix = path.suffix.lstrip(".").lower()
        mime = {
            "png": "image/png", "jpg": "image/jpeg",
            "jpeg": "image/jpeg", "gif": "image/gif",
        }.get(suffix, "image/png")

        image_b64 = base64.b64encode(path.read_bytes()).decode()
        payload = {"name": name, "image": f"data:{mime};base64,{image_b64}"}

        url = f"https://discord.com/api/v10/applications/{self._app_id}/emojis"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self._headers(), json=payload) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        return int(data["id"])
                    error = await resp.text()
                    log.error("上傳 emoji '%s' 失敗 (HTTP %s): %s", name, resp.status, error)
                    return None
        except aiohttp.ClientError as exc:
            log.error("上傳 emoji 請求失敗：%s", exc)
            return None

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bot {self._token}"}

    def _load(self) -> dict[str, int]:
        if not EMOJI_IDS_PATH.exists():
            return {}
        try:
            data = json.loads(EMOJI_IDS_PATH.read_text(encoding="utf-8"))
            return {str(k): int(v) for k, v in data.items()}
        except (json.JSONDecodeError, ValueError):
            log.warning("app_emojis.json 格式損毀，重置")
            return {}

    def _save(self) -> None:
        EMOJI_IDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        EMOJI_IDS_PATH.write_text(
            json.dumps(self._ids, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
