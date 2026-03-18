import os
import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

# --- 1. 配置區 ---
OFDC_USER = os.getenv('OFDC_USER')  # 您的登入帳號
OFDC_PASS = os.getenv('OFDC_PASS')  # 您的登入密碼
DATA_FILE = 'data.json'

# 船名與統一編號對照 (根據您的截圖設定)
VESSEL_MAP = {
    "61436": "信隆168",
    "66407": "昱友668",  # 假設編號
    "61431": "YUYO 1",    # 假設編號
    "61432": "YUYO 6"     # 假設編號
}

def run_scraper():
    if not OFDC_USER or not OFDC_PASS:
        print("❌ 錯誤：未設定 OFDC 帳號或密碼於 GitHub Secrets")
        return None

    with sync_playwright() as p:
        # 啟動模擬瀏覽器 (模擬 Windows Chrome)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            print(f"🚀 [{datetime.now().strftime('%H:%M:%S')}] 正在連線至 OFDC 系統...")
            page.goto("https://www.ofdc.org.tw:8181/elogbookquery/login.xhtml", timeout=60000)
            
            # --- A. 登入流程 ---
            # 根據常見 JSF 架構，使用模糊匹配 ID 尋找輸入框
            page.wait_for_selector('input[type="text"]')
            page.get_by_role("textbox").first.fill(OFDC_USER)
            page.get_by_role("textbox").last.fill(OFDC_PASS)
            
            # 尋找登入按鈕並點擊
            login_btn = page.locator('button:has-text("登入"), input[type="submit"]')
            login_btn.first.click()
            
            page.wait_for_timeout(3000) # 等待跳轉
            print("✅ 登入成功，正在切換至鮪延繩釣資料頁...")

            # --- B. 前往資料分頁 ---
            # 模擬點擊頂部的「鮪延繩釣」或直接跳轉 URL
            page.goto("https://www.ofdc.org.tw:8181/elogbookquery/content/tuna/data.xhtml", timeout=60000)
            
            # 等待表格載入
            page.wait_for_selector('table', timeout=30000)
            print("📊 表格載入完成，開始解析數據...")

            # --- C. 解析表格內容 ---
            rows = page.locator('tr').all()
            new_records = []

            # 從第二列開始抓取 (跳過標題)
            for i in range(1, len(rows)):
                cols = rows[i].locator('td').all_texts()
                if len(cols) > 8:
                    ship_id = cols[1].strip()     # 統一編號
                    work_date = cols[2].strip()   # 作業日期 (YYYY/MM/DD)
                    work_time = cols[3].strip()   # 作業時間
                    lat = float(cols[4].strip())  # 緯度
                    lng = float(cols[5].strip())  # 經度
                    temp = cols[6].strip()        # 海面溫度

                    ship_name = VESSEL_MAP.get(ship_id, f"船隻:{ship_id}")
                    
                    new_records.append({
                        "name": ship_name,
                        "lat": lat,
                        "lng": lng,
                        "time": f"{work_date} {work_time}",
                        "temp": temp,
                        "status": "OFDC 官方數據"
                    })

            print(f"✨ 成功解析 {len(new_records)} 筆作業紀錄")
            return new_records

        except Exception as e:
            print(f"❌ 抓取過程發生異常: {str(e)}")
            return None
        finally:
            browser.close()

def update_json(new_data):
    """更新 data.json 並保持數據韌性 (不覆蓋舊有成功數據)"""
    if not new_data:
        print("⚠️ 無新數據可更新，保持舊有資料。")
        return

    # 讀取現有檔案
    all_data = {"vessels": {}, "last_update": "", "finance": {}}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                all_data = json.load(f)
        except: pass

    # 整合新舊數據
    for rec in new_data:
        v_name = rec['name']
        if v_name not in all_data['vessels']:
            all_data['vessels'][v_name] = []
        
        # 檢查是否已存在相同時間的紀錄 (避免重複插入)
        existing_times = [p['time'] for p in all_data['vessels'][v_name]]
        if rec['time'] not in existing_times:
            all_data['vessels'][v_name].append({
                "lat": rec['lat'],
                "lng": rec['lng'],
                "time": rec['time'],
                "temp": rec['temp'],
                "status": rec['status']
            })
            # 每個船隻保留最近 100 筆軌跡
            all_data['vessels'][v_name] = all_data['vessels'][v_name][-100:]

    all_data['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 寫入檔案
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print(f"📂 數據已同步至 {DATA_FILE}")

if __name__ == "__main__":
    latest_vessels = run_scraper()
    if latest_vessels:
        update_json(latest_vessels)
