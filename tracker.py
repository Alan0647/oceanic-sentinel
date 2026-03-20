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

async def fetch_fuel_analysis(page):
    print("📰 正在擷取 Integr8 Fuels 市場解析...")
    try:
        await page.goto("https://www.integr8fuels.com/market-reports/", timeout=60000)
        title = await page.locator(".entry-title").first.inner_text()
        content = await page.locator(".entry-content p").first.inner_text()
        return f"【{title.strip()}】 {content.strip()}"
    except:
        return "暫時無法取得專家解析，建議參考 BunkerIndex 價格走勢。"

async def fetch_bunker_data(page):
    print("⛽ 正在更新 BunkerIndex 全球報價...")
    bunker_results = []
    coord_db = {
        "Singapore": [1.29, 103.85], "Gibraltar": [36.14, -5.35], "Rotterdam": [51.92, 4.47],
        "Cape Town": [-33.92, 18.42], "Dakar": [14.69, -17.44], "Houston": [29.76, -95.36],
        "Kaohsiung": [22.61, 120.29], "Busan": [35.17, 129.07], "Las Palmas": [28.12, -15.43]
    }
    try:
        await page.goto("https://www.bunkerindex.com/prices/market_benchmarks.php", timeout=60000)
        await page.wait_for_selector("table", timeout=30000)
        rows = await page.locator("tr").all()
        for row in rows:
            cells = await row.locator("td").all_inner_texts()
            if len(cells) >= 4 and any(x in cells[1] for x in ["MGO", "MDI"]):
                full_name = cells[0].strip()
                port_key = full_name.split("(")[0].strip()
                coords = coord_db.get(port_key, [0, 0])
                bunker_results.append({
                    "name": full_name, "fuel": cells[1].strip(),
                    "latest": cells[2].replace("$", "").strip(),
                    "date": cells[3].strip(), "lat": coords[0], "lon": coords[1]
                })
    except Exception as e:
        print(f"⚠️ BunkerIndex 抓取中斷: {e}")
    return bunker_results

def fetch_fx_data():
    res = []
    symbols = {"USD/TWD": "TWD=X", "USD/JPY": "JPY=X", "JPY/TWD": "JPYTWD=X"}
    for name, sym in symbols.items():
        try:
            ticker = yf.Ticker(sym)
            h = ticker.history(period="10d")
            latest = h['Close'].iloc[-1]
            wh, wl = h['High'].tail(7).max(), h['Low'].tail(7).min()
            prec = 4 if "JPY/TWD" in name else 2
            res.append({"name": name, "latest": f"{latest:.{prec}f}", "week_h": f"{wh:.{prec}f}", "week_l": f"{wl:.{prec}f}"})
        except: pass
    return res

async def scrape_ofdc(page):
    now_tw = datetime.now(TW_TIME)
    end_d, start_d = now_tw.strftime("%Y/%m/%d"), (now_tw - timedelta(days=10)).strftime("%Y/%m/%d")
    await page.goto("https://www.ofdc.org.tw:8181/elogbookquery/content/index.xhtml", timeout=60000)
    await page.fill('input[id*="使用者名稱"]', os.environ['OFDC_USER'])
    await page.fill('input[id*="密碼"]', os.environ['OFDC_PASS'])
    await page.keyboard.press("Enter")
    await page.wait_for_selector("text=鮪延繩釣", timeout=45000)
    await page.click("text=鮪延繩釣")
    final_vessels = []
    for v in VESSELS:
        try:
            print(f"🚢 同步：{v['name']}")
            await page.select_option('select[id*="ctnoSelectMenu"]', v['id'])
            d_ins = await page.locator('input[id*="Date_input"]').all()
            if len(d_ins) >= 2:
                await d_ins[0].fill(start_d)
                await d_ins[1].fill(end_d)
            await page.get_by_role("button", name="線上查詢").click()
            await asyncio.sleep(6)
            rows = await page.locator("tr.ui-widget-content").all()
            if rows:
                best_row, max_date = rows[0], ""
                for r in rows:
                    cc = await r.locator("td").all_inner_texts()
                    if len(cc) > 2 and cc[2] > max_date: max_date, best_row = cc[2], r
                cells = await best_row.locator("td").all_inner_texts()
                data = {"name": v['name'], "id": v['id'], "date": cells[2], "lat": float(cells[4]), "lon": float(cells[5]), "temp": cells[6], "bait": cells[16], "catch_details": []}
                await best_row.click()
                await asyncio.sleep(4)
                c_rows = await page.locator(".ui-datatable-data").nth(1).locator("tr").all()
                tw, tc = 0.0, 0
                for cr in c_rows:
                    cc = await cr.locator("td").all_inner_texts()
                    if len(cc) >= 7:
                        data["catch_details"].append({"id": cc[1], "date": cc[2], "sp": cc[3], "wt": cc[4], "ct": cc[5], "pr": cc[6]})
                        try: tw += float(cc[4]); tc += int(cc[5])
                        except: pass
                data["subtotal_weight"], data["subtotal_count"] = f"{tw:.1f}", tc
                final_vessels.append(data)
        except: continue
    return final_vessels

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        v_data = await scrape_ofdc(page)
        analysis = await fetch_fuel_analysis(page)
        bunker = await fetch_bunker_data(page)
        fx = fetch_fx_data()
        output = {"update_time": datetime.now(TW_TIME).strftime('%Y-%m-%d %H:%M'), "vessels": v_data, "market": {"exchange": fx, "oil": bunker, "analysis": analysis}}
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=4)
        await browser.close()

if __name__ == "__main__": asyncio.run(main())
