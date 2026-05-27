# ClaimBot 設計規格

**日期：** 2026-05-26  
**狀態：** 已核准

---

## 概述

ClaimBot 是一個 Discord Bot，每 6 小時自動偵測 Steam 平台上的限時免費遊戲，並將遊戲資訊（名稱、封面、領取連結、到期時間）以 Discord Embed 形式推送到指定頻道。資料來源為 IsThereAnyDeal API，本地以 JSON 檔記錄已發送過的遊戲 ID 以防重複通知。

---

## 技術選型

| 項目 | 選擇 |
|------|------|
| 語言 | Python 3.11+ |
| Discord 框架 | discord.py 2.x |
| HTTP 客戶端 | aiohttp（非同步，符合 discord.py 事件循環） |
| 資料來源 | IsThereAnyDeal API v3 |
| 持久化 | JSON 檔案（seen_games.json） |
| 設定管理 | python-dotenv（.env 檔） |

---

## 專案結構

```
ClaimBot/
├── bot.py                        # 入口點：Bot 初始化、載入 Cog
├── cogs/
│   └── free_games.py             # 定時任務 Cog：排程、Embed 組裝、發送
├── services/
│   └── itad_client.py            # IsThereAnyDeal API 封裝
├── data/
│   └── seen_games.json           # 已發送遊戲 ID 記錄（自動建立）
├── .env                          # 機密設定（不提交至 git）
├── .env.example                  # 範例設定檔（提交至 git）
├── requirements.txt              # Python 依賴
└── .gitignore
```

---

## 資料模型

### FreeGame（services/itad_client.py 中定義）

```python
@dataclass
class FreeGame:
    id: str          # ITAD 內部 ID，用於去重（例如：app/12345）
    title: str       # 遊戲名稱
    url: str         # Steam 領取連結
    image_url: str   # 封面圖片 URL
    expires_at: str  # 到期時間（ISO 8601 字串），無期限時為 None
```

### seen_games.json

```json
{
  "seen_ids": ["app/12345", "app/67890"]
}
```

- 只追加，不刪除
- Bot 啟動時若檔案不存在則自動建立

---

## 元件設計

### bot.py

- 讀取 `.env` 中的 `DISCORD_TOKEN`、`DISCORD_CHANNEL_ID`、`ITAD_API_KEY`
- 建立 `discord.ext.commands.Bot` 實例（command_prefix 可設為 `!` 備用）
- 在 `on_ready` 事件中載入 `FreeGamesCog`
- 啟動時驗證 `DISCORD_CHANNEL_ID` 對應的頻道存在，不存在則記錄錯誤並停止

### cogs/free_games.py（FreeGamesCog）

- 使用 `discord.ext.tasks.loop(hours=6)` 定義定時任務
- 流程：
  1. 呼叫 `ITADClient.get_free_games()` 取得目前免費遊戲列表
  2. 讀取 `seen_games.json` 取得已發送 ID 集合
  3. 過濾出尚未發送的遊戲
  4. 若無新遊戲，靜默跳過
  5. 對每款新遊戲發送一則 Embed
  6. 將新遊戲 ID 寫回 `seen_games.json`
- Bot 啟動後立即執行一次（`before_loop` 中等待 `bot.wait_until_ready()`）

### Discord Embed 規格

- **顏色：** `0x2ecc71`（綠色）
- **標題：** 遊戲名稱（超連結，指向 Steam 頁面）
- **縮圖：** 遊戲封面圖（`set_image`）
- **欄位：** 到期時間（若 `expires_at` 不為 None）
- **Footer：** `資料來源：IsThereAnyDeal`

### services/itad_client.py（ITADClient）

- 使用 `aiohttp.ClientSession` 發送非同步 GET 請求
- 端點：`https://api.isthereanydeal.com/v3/deals`
- 查詢參數：
  - `shops=steam`
  - `price_max=0`（限時免費）
  - `limit=20`
  - `key={ITAD_API_KEY}`
- 回傳 `list[FreeGame]`
- API 失敗（非 200 狀態碼、逾時、網路錯誤）時記錄 log 並回傳空列表

---

## 錯誤處理

| 情境 | 處理方式 |
|------|---------|
| ITAD API 回傳非 200 | `log.warning` 記錄狀態碼，回傳 `[]` |
| aiohttp 逾時 / 網路錯誤 | `log.warning` 記錄例外，回傳 `[]` |
| seen_games.json 不存在 | 自動建立 `{"seen_ids": []}` |
| seen_games.json 格式損毀 | `log.error` 記錄，重置為空檔案 |
| Discord 頻道 ID 無效 | `on_ready` 中 `log.error` 並呼叫 `await bot.close()` |
| 本次無新免費遊戲 | 靜默跳過，不發送任何訊息 |

---

## 環境變數

`.env.example` 內容：

```env
DISCORD_TOKEN=your_bot_token_here
DISCORD_CHANNEL_ID=your_channel_id_here
ITAD_API_KEY=your_itad_api_key_here
```

已知的 Discord Application 資訊：
- Application ID：`1508719942579650661`
- Public Key：`f449359229a1362ba910108155191a7695b771d786a61cb64405560ac694b518`

---

## 依賴套件（requirements.txt）

```
discord.py>=2.3
aiohttp>=3.9
python-dotenv>=1.0
```

---

## 部署

- **本地開發：** `python bot.py`
- **長期運行（Windows）：** 工作排程器設定開機啟動
- **雲端部署：** Railway、Fly.io 或任何支援 Python 的 VPS

---

## 不在範疇內（Out of Scope）

- Slash Command 查詢介面
- 多伺服器支援
- 資料庫（SQLite / PostgreSQL）
- Epic Games、GOG、Prime Gaming 等其他平台
