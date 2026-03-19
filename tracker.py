import os, asyncio, json, time, yfinance as yf
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

VESSELS = [
    {"name": "信隆168", "id": "61436"}, {"name": "昱友668", "id": "61508"},
    {"name": "信友16", "id": "70157"}, {"name": "信隆216", "id": "70296"},
    {"name": "高欣6", "id": "70506"}, {"name": "隆昌3", "id": "70554"}
]

# 抓取金融數據 (匯率與油價)
def fetch_finance_data():
    symbols = {
        "USD/TWD": "TWD=X", "USD/JPY": "JPY=X", "JPY/TWD": "JPYTWD=X",
        "WTI 原油": "CL=F", "布蘭特原油": "BZ=F"
    }
    market_results = {"exchange": [], "oil": []}
    
    for name, sym in symbols.items():
        ticker = yf.Ticker(sym)
        hist = ticker.history(period="7d")
        if not hist.empty:
            latest = hist['Close'].iloc[-1]
            week_h = hist['High'].max()
            week_l = hist['Low'].min()
            
            data = {"pair": name, "latest": f"{latest:.2f}", "week_h": f"{week_h:.2f}", "week_l": f"{week_l:.2f}"}
            if "/" in name: market_results["exchange"].append(data)
            else: market_results["oil"].append(data)

    # 補充 10 個港口 MGO (目前以 Brent 溢價模擬，建議每週手動微調或觀察)
    ports = ["新加坡", "高雄", "釜山", "拉斯帕爾馬斯", "開普敦", "達卡", "阿必尚", "路易港", "維多利亞", "檳城"]
    brent_latest = float(market_results["oil"][1]["latest"])
    for p in ports:
        # 簡單邏輯：MGO 約為 Brent 桶價 * 7.5 (噸換算) + 運費溢價
        price = brent_latest * 7.5 + 150 
        market_results["oil"].append({
            "port": f"MGO - {p}", "latest": f"{price:.1f}", 
            "week_h": f"{price*1.05:.1f}", "week_l": f"{price*0.95:.1f}"
        })
    return market_results

async def scrape_ofdc(page):
    # ... (此處保留您先前測試成功的 OFDC 登入與漁獲抓取代碼)
    # 確保抓到 bait (餌料) 與 sea_temp (海溫)
    return vessel_data_list # 假設回傳抓好的船隻陣列

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        vessels_data = []
        try:
            vessels_data = await scrape_ofdc(page)
        except Exception as e: print(f"漁獲抓取失敗: {e}")
        
        finance_data = fetch_finance_data()
        
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
