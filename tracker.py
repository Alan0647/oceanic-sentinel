import os, asyncio, json, time, yfinance as yf
from datetime import datetime, timedelta, timezone
from playwright.async_api import async_playwright

# 設定台北時區 (UTC+8)
TW_TIME = timezone(timedelta(hours=8))

VESSELS = [
    {"name": "信隆168", "id": "61436"}, {"name": "昱友668", "id": "61508"},
    {"name": "信友16", "id": "70157"}, {"name": "信隆216", "id": "70296"},
    {"name": "高欣6", "id": "70506"}, {"name": "隆昌3", "id": "70554"}
]

# 1. 抓取 Integr8 Fuels 市場解析
async def fetch_integr8_analysis(page):
    print("📰 正在攫取 Integr8 Fuels 市場解析...")
    try:
        await page.goto("https://www.integr8fuels.com/market-reports/", timeout=60000)
        title = await page.locator(".entry-title").first.inner_text()
        summary = await page.locator(".entry-content p").first.inner_text()
        return f"【{title.strip()}】 {summary.strip()}"
    except:
        return "暫時無法取得專家解析，建議參考 BunkerIndex 價格走勢。"

# 2. 抓取 BunkerIndex 全球報價
async def fetch_bunker_index(page):
    print("⛽ 正在從 BunkerIndex 攫取全球報價網絡...")
    ports_res = []
    coord_db = {
        "Singapore": [1.29, 103.85], "Gibraltar": [36.14, -5.35], "Rotterdam": [51.92, 4.47],
        "Cape Town": [-33.92, 18.42], "Dakar": [14.69, -17.44], "Houston": [29.76, -95.36],
        "Abidjan": [5.31, -4.00], "Port Louis": [-20.16, 57.50], "Kaohsiung": [22.61, 120.29],
        "Busan": [35.17, 129.07], "Las Palmas": [28.12, -15.43]
    }
    try:
        await page.goto("https://www.bunkerindex.com/prices/market_benchmarks.php", timeout=60000)
        rows = await page.locator("tr").all()
        for row in rows:
            cells = await row.locator("td").all_inner_texts()
            if len(cells) >= 4 and any(x in cells[1] for x in ["MGO", "MDI"]):
                port_country = cells[0].strip()
                port_name = port_country.split("(")[0].strip()
                coords = coord_db.get(port_name, [0, 0])
                ports_res.append({
                    "name": port_country, "fuel": cells[1].strip(),
                    "latest": cells[2].replace("$", "").strip(),
                    "date": cells[3].strip(), "lat": coords[0], "lon": coords[1]
                })
    except Exception as e: print(f"⚠️ BunkerIndex 失敗: {e}")
    return ports_res

# 3. 抓取匯率
def fetch_fx():
    rates = []
    symbols = {"USD/TWD": "TWD=X", "USD/JPY": "JPY=X", "JPY/TWD": "JPYTWD=X"}
    for name, sym in symbols.items():
        try:
            h = yf.Ticker(sym).history(period="10d")
            latest, wh, wl = h['Close'].iloc[-1], h['High'].tail(7).max(), h['Low'].tail(7).min()
            prec = 4 if "JPY/TWD" in name else 2
            rates.append({"name": name, "latest": f"{latest:.{prec}f}", "week_h": f"{wh:.{prec}f}", "week_l": f"{wl:.{prec}f}"})
        except: pass
    return rates

# 4. 抓取 OFDC 漁獲 (強力日期校正)
async def scrape_ofdc(page):
    now_tw = datetime.now(TW_TIME)
    end_date = now_tw.strftime("%Y/%m/%d")
    start_date = (now_tw - timedelta(days=10)).strftime("%Y/%m/%d")
    
    await page.goto("https://www.ofdc.org.tw:8181/elogbookquery/content/index.xhtml", timeout=60000)
    await page.fill('input[id*="使用者名稱"]', os.environ['OFDC_USER'])
    await page.fill('input[id*="密碼"]', os.environ['OFDC_PASS'])
    await page.keyboard.press("Enter")
    await page.wait_for_selector("text=鮪延繩釣", timeout=45000)
    await page.click("text=鮪延繩釣")
    
    results = []
    for v in VESSELS:
        try:
            print(f"🚢 同步：{v['name']}")
            await page.select_option('select[id*="ctnoSelectMenu"]', v['id'])
            d_ins = await page.locator('input[id*="Date_input"]').all()
            if len(d_
