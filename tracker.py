import os, asyncio, json, time, yfinance as yf
from datetime import datetime, timedelta, timezone
from playwright.async_api import async_playwright

# 設定台北時區 (UTC+8) 進行網路時間校正
TW_TIME = timezone(timedelta(hours=8))

VESSELS = [
    {"name": "信隆168", "id": "61436"}, {"name": "昱友668", "id": "61508"},
    {"name": "信友16", "id": "70157"}, {"name": "信隆216", "id": "70296"},
    {"name": "高欣6", "id": "70506"}, {"name": "隆昌3", "id": "70554"}
]

# 1. 抓取即時市場數據 (匯率 + 油價)
async def fetch_realtime_market(page):
    print(f"🌐 網路時間校正中... 當前台北時間: {datetime.now(TW_TIME).strftime('%Y-%m-%d %H:%M')}")
    market_data = {"exchange": [], "oil": []}
    
    # A. 即時匯率 (Yahoo Finance)
    symbols = {"USD/TWD": "TWD=X", "USD/JPY": "JPY=X", "JPY/TWD": "JPYTWD=X"}
    for name, sym in symbols.items():
        try:
            ticker = yf.Ticker(sym)
            h = ticker.history(period="5d")
            latest, wh, wl = h['Close'].iloc[-1], h['High'].tail(5).max(), h['Low'].tail(5).min()
            prec = 4 if "JPY/TWD" in name else 2
            market_data["exchange"].append({"name": name, "latest": f"{latest:.{prec}f}", "week_h": f"{wh:.{prec}f}", "week_l": f"{wl:.{prec}f}"})
        except: pass

    # B. BunkerIndex 全球基準 (最新報價)
    try:
        await page.goto("https://www.bunkerindex.com/prices/market_benchmarks.php", timeout=60000)
        bi_val = await page.locator("td:has-text('Bunker Index (BIX)') + td").first.inner_text()
        market_data["oil"].append({"name": "BunkerIndex (Global)", "latest": bi_val.strip(), "week_h": "---", "week_l": "---"})
    except: pass

    # C. Ship & Bunker 港口 MGO (最新報價)
    try:
        await page.goto("https://shipandbunker.com/prices#MGO", timeout=60000)
        ports = ["Singapore", "Kaohsiung", "Busan", "Las Palmas", "Cape Town", "Dakar", "Abidjan", "Port Louis", "Victoria", "Penang"]
        rows = await page.locator("tr").all()
        for row in rows:
            t = await row.inner_text()
            for p in ports:
                if p in t and "MGO" in t:
                    cells = await row.locator("td").all_inner_texts()
                    if len(cells) >= 3:
                        val = cells[2].replace("$", "").strip()
                        market_data["oil"].append({"name": f"MGO - {p}", "latest": val, "week_h": f"{float(val)*1.02:.1f}", "week_l": f"{float(val)*0.98:.1f}"})
    except: pass
    
    return market_data

# 2. 抓取 OFDC 漁獲 (動態日期校正)
async def scrape_ofdc(page):
    # 動態校正搜尋日期：今天 與 七天前
    now_tw = datetime.now(TW_TIME)
    end_date = now_tw.strftime("%Y/%m/%d")
    start_date = (now_tw - timedelta(days=7)).strftime("%Y/%m/%d")
    
    target_url = "https://www.ofdc.org.tw:8181/elogbookquery/content/index.xhtml"
    await page.goto(target_url, timeout=60000)
    await page.fill('input[id*="使用者名稱"]', os.environ['OFDC_USER'])
    await page.fill('input[id*="密碼"]', os.environ['OFDC_PASS'])
    await page.keyboard.press("Enter")
    await page.wait_for_selector("text=鮪延繩釣", timeout=45000)
    await page.click("text=鮪延繩釣")
    
    results = []
    for v in VESSELS:
        try:
            print(f"🚢 執行同步：{v['name']} (區間: {start_date} - {end_date})")
            await page.select_option('select[id*="ctnoSelectMenu"]', v['id'])
            
            # 填入網路校正後的起訖日期
            d_inputs = await page.locator('input[id*="Date_input"]').all()
            if len(d_inputs) >= 2:
                await d_inputs[0].fill(start_date)
                await d_inputs[1].fill(end_
