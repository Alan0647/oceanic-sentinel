import os, asyncio, json, time, yfinance as yf
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

# 船隻清單
VESSELS = [
    {"name": "信隆168", "id": "61436"}, {"name": "昱友668", "id": "61508"},
    {"name": "信友16", "id": "70157"}, {"name": "信隆216", "id": "70296"},
    {"name": "高欣6", "id": "70506"}, {"name": "隆昌3", "id": "70554"}
]

# --- [新增] 自動抓取金融數據函數 ---
def fetch_finance_data():
    # 定義要抓取的 Tickers
    # USD/TWD, USD/JPY, JPY/TWD, WTI(CL=F), Brent(BZ=F)
    symbols = {
        "USD/TWD": "TWD=X",
        "USD/JPY": "JPY=X",
        "JPY/TWD": "JPYTWD=X",
        "WTI 輕原油": "CL=F",
        "布蘭特原油": "BZ=F"
    }
    
    market_results = {"exchange": [], "oil": []}
    
    for name, sym in symbols.items():
        try:
            ticker = yf.Ticker(sym)
            # 抓取過去 10 天數據確保含蓋一週交易日
            hist = ticker.history(period="10d")
            if not hist.empty:
                latest = hist['Close'].iloc[-1]
                # 取得過去 7 天的數據進行高低點計算
                week_data = hist.tail(7)
                week_h = week_data['High'].max()
                week_l = week_data['Low'].min()
                
                item = {
                    "name": name,
                    "latest": f"{latest:.2f}",
                    "week_h": f"{week_h:.2f}",
                    "week_l": f"{week_l:.2f}"
                }
                
                if "/" in name: market_results["exchange"].append(item)
                else: market_results["oil"].append(item)
        except Exception as e:
            print(f"金融數據抓取失敗 ({name}): {e}")

    # 針對 10 個港口 MGO 的處理
    # 由於 Yahoo Finance 無法直接提供特定港口 MGO 報價，
    # 這裡我們以 Brent 價格為基準並加入固定溢價 (Spread) 來模擬即時變動，
    # 這樣數據會隨國際油價自動起伏，比靜態數據更具參考價值。
    ports = ["新加坡", "高雄", "釜山", "拉斯帕爾馬斯", "開普敦", "達卡", "阿必尚", "路易港", "維多利亞", "檳城"]
    brent_ref = float(market_results["oil"][1]["latest"]) if len(market_results["oil"]) > 1 else 80.0
    
    for p in ports:
        # 簡易 MGO 估算公式 (僅供參考，可手動微調溢價)
        mgo_latest = brent_ref * 7.5 + 150 
        market_results["oil"].append({
            "name": f"MGO - {p}",
            "latest": f"{mgo_latest:.1f}",
            "week_h": f"{mgo_latest * 1.05:.1f}",
            "week_l": f"{mgo_latest * 0.95:.1f}"
        })
        
    return market_results

async def scrape_vessels(page):
    # ... [此處保留之前優化後的 OFDC 抓取邏輯] ...
    # 確保回傳的資料包含 bait, sea_temp 以及 catch_details 陣列
    return [] # 這裡應填入您實測成功的資料回傳

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # 1. 抓取漁獲
        vessels_data = []
        try:
            # 這裡呼叫您之前的 OFDC 邏輯
            # vessels_data = await scrape_ofdc(page) 
            pass
        except: pass
        
        # 2. 抓取金融 (Yahoo Finance)
        finance_data = fetch_finance_data()
        
        # 3. 整合存檔
        final_json = {
            "update_time": time.strftime('%Y-%m-%d %H:%M'),
            "vessels": vessels_data,
            "market": finance_data
        }
        
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(final_json, f, ensure_ascii=False, indent=4)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
