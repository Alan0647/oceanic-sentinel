name: OFDC Data Auto Scraper

on:
  schedule:
    - cron: '45 0 * * *' # 台灣時間 08:45 執行
  workflow_dispatch:      # 支援手動執行

permissions:
  contents: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: 1. 檢出代碼
        uses: actions/checkout@v4

      - name: 2. 設定 Python 3.9
        uses: actions/setup-python@v5
        with:
          python-version: '3.9'

      - name: 3. 安裝組件
        run: |
          pip install playwright yfinance
          playwright install chromium

      - name: 4. 執行數據抓取 (漁獲 + 金融)
        env:
          OFDC_USER: ${{ secrets.OFDC_USER }}
          OFDC_PASS: ${{ secrets.OFDC_PASS }}
        run: python tracker.py

      - name: 5. 同步並推送數據 (防衝突模式)
        if: success()
        run: |
          git config --global user.name "Vessel-Bot"
          git config --global user.email "bot@example.com"
          
          # 關鍵修復：處理未提交的變動並拉取遠端更新
          git add data.json
          git stash
          git pull --rebase origin main
          git stash pop || echo "No stash to pop"
          
          git add data.json
          git diff --quiet && git diff --staged --quiet || (git commit -m "自動更新報表: $(date)" && git push origin main)
