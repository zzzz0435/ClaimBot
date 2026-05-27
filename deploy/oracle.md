# Oracle Cloud 部署指南（永久免費）

使用 Oracle Cloud Always Free **Ampere A1** VM 部署 ClaimBot。

> 免費額度：最多 4 OCPU + 24 GB RAM，永久免費，不會自動升級付費方案。

---

## 一、註冊 Oracle Cloud 帳號

1. 前往 [cloud.oracle.com](https://cloud.oracle.com) → 「Start for free」
2. 填寫資料，選擇**離台灣近的區域**：
   - 推薦：`Japan East (Tokyo)` 或 `Japan West (Osaka)` 或 `Singapore`
3. 需要信用卡驗證身份（**不會扣款**，只驗證真人）
4. 等待帳號審核（通常幾分鐘到幾小時）

---

## 二、建立 VM 執行個體

1. 登入後進入 **Compute → Instances → Create Instance**

2. 設定如下：

   | 欄位 | 設定值 |
   |------|--------|
   | 名稱 | `claimbot` |
   | Image | Ubuntu 22.04 |
   | Shape | **VM.Standard.A1.Flex**（Ampere，永久免費） |
   | OCPU | 1（最多可給 4，都免費） |
   | RAM | 6 GB（最多可給 24 GB，都免費） |

3. **SSH 金鑰**：選「Generate a key pair for me」→ 下載 **私鑰檔案**（.key）到電腦，妥善保存

4. 按「Create」，等待 VM 狀態變成 **Running**

---

## 三、連線到 VM

### 方法 A：Oracle 網頁 SSH（最簡單，不需要安裝工具）

在 Instance 詳細頁面，點右上角 **Cloud Shell connection** 或使用 **Instance Console**

### 方法 B：Windows Terminal SSH

```powershell
# 下載的私鑰放到 C:\Users\你的帳號\.ssh\
# 取得 VM 的公開 IP（Instance 詳細頁面可以看到）

ssh -i C:\Users\你的帳號\.ssh\私鑰檔名.key ubuntu@你的VM公開IP
```

---

## 四、VM 環境設定（只需做一次）

進入 VM 後依序執行：

```bash
# 更新系統
sudo apt update && sudo apt upgrade -y

# 安裝 Python 3.12 與 git
sudo apt install -y python3.12 python3.12-venv git

# Clone 你的 GitHub repo
git clone https://github.com/zzzz0435/ClaimBot.git
cd ClaimBot

# 建立虛擬環境並安裝套件
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 建立 .env 檔（填入你的 Bot Token）
nano .env
```

在 nano 編輯器中輸入：
```
DISCORD_TOKEN=你的discord_token
```
按 `Ctrl+O` 儲存，`Ctrl+X` 離開

---

## 五、上傳 Logo 圖片（可選）

如果要使用 Application Emoji 功能，需要把 Logo 傳到 VM：

```bash
# 在 VM 上執行，直接從 Google Favicon 下載
cd ~/ClaimBot
curl -o assets/steam.png "https://www.google.com/s2/favicons?domain=steampowered.com&sz=128"
curl -o assets/epic.png "https://www.google.com/s2/favicons?domain=epicgames.com&sz=128"
```

---

## 六、設定 systemd 服務（開機自動啟動）

```bash
# 複製服務設定檔
sudo cp ~/ClaimBot/deploy/claimbot.service /etc/systemd/system/

# 修改服務檔，讓它用虛擬環境的 python
sudo nano /etc/systemd/system/claimbot.service
```

把 `ExecStart` 那行改成：
```
ExecStart=/home/ubuntu/ClaimBot/venv/bin/python bot.py
```

```bash
# 啟動並設為開機自動執行
sudo systemctl daemon-reload
sudo systemctl enable claimbot
sudo systemctl start claimbot

# 確認是否正常運行
sudo systemctl status claimbot
```

看到 `Active: active (running)` 代表成功 ✅

---

## 七、常用指令

```bash
# 查看即時日誌
sudo journalctl -u claimbot -f

# 重啟 Bot
sudo systemctl restart claimbot

# 停止 Bot
sudo systemctl stop claimbot
```

---

## 八、更新 Bot（之後每次 git push 後）

```bash
cd ~/ClaimBot
git pull
source venv/bin/activate
pip install -r requirements.txt   # 只有新增套件時才需要
sudo systemctl restart claimbot
```

---

## 常見問題

**Q：建立 VM 時找不到 VM.Standard.A1.Flex？**
A：免費 Ampere 資源有時在熱門區域會滿，換 `Singapore` 或 `Tokyo` 試試，或稍後再試。

**Q：SSH 連線被拒？**
A：確認 VM 的 Security List 有開放 port 22（TCP Ingress）。

**Q：Bot 啟動後過一段時間停了？**
A：查看日誌 `journalctl -u claimbot -n 50` 找錯誤原因。
