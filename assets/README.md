# assets/

放置平台 Logo，Bot 啟動時會自動上傳為 Application Emoji。

## 需要的檔案

| 檔名 | 用途 | 建議尺寸 |
|------|------|---------|
| `steam.png` | Steam 平台 Logo | 128×128 px，PNG，< 256 KB |
| `epic.png` | Epic Games Logo | 128×128 px，PNG，< 256 KB |

## 取得 Logo

- **Steam**：https://partner.steamgames.com/doc/marketing/branding
- **Epic Games**：https://brand.epicgames.com/

## 備註

- 圖片檔案已加入 `.gitignore`，不會被 commit 進版本控制（避免版權問題）
- 如果 Bot 找不到這些檔案，會自動 fallback 回 Unicode emoji（🎮）
- 上傳成功後，Emoji ID 會存在 `data/app_emojis.json` 不需重複上傳
