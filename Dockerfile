FROM python:3.12-slim

WORKDIR /app

# 先複製 requirements 以利用 Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製程式碼
COPY . .

# 建立資料與 assets 目錄
RUN mkdir -p data assets

CMD ["python", "bot.py"]
