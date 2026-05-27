# Google Cloud 部署指南

使用 Google Cloud **Always Free** e2-micro VM 部署 ClaimBot。

---

## 一、建立 GCP 帳號與 VM

1. 前往 [console.cloud.google.com](https://console.cloud.google.com)，用 Google 帳號登入
2. 建立新專案（任意名稱，如 `claimbot`）
3. 左側選單 → **Compute Engine** → **VM instances** → **建立執行個體**

   | 欄位 | 設定值 |
   |------|--------|
   | 名稱 | `claimbot` |
   | 區域 | `us-central1`（或 `us-west1`、`us-east1`，才是免費） |
   | 機器類型 | `e2-micro`（免費層） |
   | 作業系統 | Ubuntu 22.04 LTS |
   | 開機磁碟 | 標準永久磁碟，30 GB |

4. 按「建立」，等待 VM 啟動

---

## 二、SSH 進入 VM

在 VM 列表頁，點擊右側的 **SSH** 按鈕（瀏覽器內建終端，不需安裝任何工具）

---

## 三、環境設定（只需做一次）

在 SSH 終端中依序執行：

```bash
# 更新系統
sudo apt update && sudo apt upgrade -y

# 安裝 Python 3.12 與 git
sudo apt install -y python3.12 python3.12-venv git

# Clone 你的 repo（換成你的 GitHub 網址）
git clone https://github.com/zzzz0435/ClaimBot.git
cd ClaimBot

# 建立虛擬環境並安裝套件
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 建立 .env 檔（填入你的 Token）
echo "DISCORD_TOKEN=你的token" > .env

# 複製 assets（如果有 Logo 圖片）
# 可用 scp 或 GCP Cloud Storage 上傳
```

---

## 四、設定 systemd 服務（開機自動啟動）

```bash
# 複製服務設定檔
sudo cp ~/ClaimBot/deploy/claimbot.service /etc/systemd/system/

# 修改 ExecStart 指向虛擬環境的 python
sudo nano /etc/systemd/system/claimbot.service
# 把 ExecStart 改為：
# ExecStart=/home/ubuntu/ClaimBot/venv/bin/python bot.py

# 啟用並啟動服務
sudo systemctl daemon-reload
sudo systemctl enable claimbot
sudo systemctl start claimbot

# 確認運行狀態
sudo systemctl status claimbot
```

---

## 五、查看日誌

```bash
# 即時日誌
sudo journalctl -u claimbot -f

# 最近 100 行
sudo journalctl -u claimbot -n 100
```

---

## 六、更新 Bot（之後每次推送新功能）

```bash
cd ~/ClaimBot
git pull
source venv/bin/activate
pip install -r requirements.txt   # 有新套件時
sudo systemctl restart claimbot
```

---

## 注意事項

- **免費資格**：VM 必須在 `us-central1`、`us-west1` 或 `us-east1` 區域，機型為 `e2-micro`
- **資料持久性**：`data/` 資料夾存在 VM 磁碟上，重啟服務不會遺失
- **assets Logo**：需要手動上傳 `steam.png` 和 `epic.png` 到 VM 的 `assets/` 目錄
