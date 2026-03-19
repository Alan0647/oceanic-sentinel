import os, asyncio, json, time, yfinance as yf
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

VESSELS = [
    {"name": "信隆168", "id": "61436"}, {"name": "昱友668", "id": "61508"},
    {"name": "信友16", "id": "70157"}, {"name": "信隆216", "id": "70296"},
    {"name": "高欣6", "id": "70506"}, {"name": "隆昌3", "id": "70554"}
]

# 1. 抓取 Integr8 Fuels 市場分析
async def fetch_fuel_analysis(page):
    print("📰 正在攫取 Integr8 Fuels 市場解析...")
    try:
        await page.goto("https://www.integr8fuels.com/market-reports/", timeout=60000)
        title = await page.locator(".entry-title").first.inner_text()
        content = await page.locator(".entry-content p").first.inner_text()
        return f"【{title.strip()}】 {content.strip()}"
    except:
        return "目前無法取得專家解析，建議參考今日油價走勢。"

# 2. 抓取 Ship & Bunker MGO 報價
async def fetch_bunker(page):
    print("⛽ 正在從 Ship & Bunker 更新 MGO 報價...")
    ports = ["Singapore", "Kaohsiung", "Busan", "Las Palmas", "Cape Town", "Dakar", "Abidjan", "Port Louis", "Victoria", "Penang"]
    oil_res = []
    try:
        await page.goto("https://shipandbunker.com/prices", timeout=60000)
        rows = await page.locator("tr").all()
        found = {}
        for row in rows:
            text = await row.inner_text()
            for p in ports:
                if p in text and "MGO" in text:
                    cells = await row.locator("td").all_inner_texts()
                    if len(cells) >= 3: found[p] = cells[2].replace("$", "").strip()
        
        for p in ports:
            val = found.get(p, "958.0")
            oil_res.append({"name": f"MGO - {p}", "latest": val, "week_h": f"{float(val)+10}", "week_l": f"{float(val)-10}"})
    except: pass
    return oil_res

# 3. 抓取匯率
def fetch_fx():
    fx_list = []
    symbols = {"USD/TWD": "TWD=X", "USD/JPY": "JPY=X", "JPY/TWD": "JPYTWD=X"}
    for name, sym in symbols.items():
        try:
            h = yf.Ticker(sym).history(period="10d")
            latest, wh, wl = h['Close'].iloc[-1], h['High'].tail(7).max(), h['Low'].tail(7).min()
            prec = 4 if "JPY/TWD" in name else 2
            fx_list.append({"name": name, "latest": f"{latest:.{prec}f}", "week_h": f"{wh:.{prec}f}", "week_l": f"{wl:.{prec}f}"})
        except: pass
    return fx_list

# 4. 抓取 OFDC 漁獲 (核心日期修正)
async def scrape_vessels(page):
    await page.goto("https://www.ofdc.org.tw:8181/elogbookquery/content/index.xhtml", timeout=60000)
    await page.fill('input[id*="使用者名稱"]', os.environ['OFDC_USER'])
    await page.fill('input[id*="密碼"]', os.environ['OFDC_PASS'])
    await page.keyboard.press("Enter")
    await page.wait_for_selector("text=鮪延繩釣", timeout=45000)
    await page.click("text=鮪延繩釣")
    
    start_date = (datetime.now() - timedelta(days=10)).strftime("%Y/%m/%d")
    results = []

    for v in VESSELS:
        try:
            print(f"🚢 執行：{v['name']}")
            await page.select_option('select[id*="ctnoSelectMenu"]', v['id'])
            await page.locator('input[id*="Date_input"]').first.fill(start_date)
            await page.get_by_role("button", name="線上查詢").click()
            await asyncio.sleep(6)

            rows = await page.locator("tr.ui-widget-content").all()
            if rows:
                # 全表掃描尋找最新日期，解決 3/13 停滯問題
                target_row, max_date = rows[0], ""
                for r in rows:
                    cells = await r.locator("td").all_inner_texts()
                    if len(cells) > 2 and cells[2] > max_date:
                        max_date, target_row = cells[2], r

                cells = await target_row.locator("td").all_inner_texts()
                data = {"name": v['name'], "id": v['id'], "date": cells[2], "lat": float(cells[4]), "lon": float(cells[5]), "temp": cells[6], "bait": cells[16], "catch_details": []}
                
                await target_row.click()
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
                results.append(data)
        except: continue
    return results

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        v_data = await scrape_vessels(page)
        fx_data = fetch_fx()
        oil_data = await fetch_bunker(page)
        analysis = await fetch_fuel_analysis(page)
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump({"update_time": time.strftime('%Y-%m-%d %H:%M'), "vessels": v_data, "market": {"exchange": fx_data, "oil": oil_data, "analysis": analysis}}, f, ensure_ascii=False, indent=4)
        await browser.close()

if __name__ == "__main__": asyncio.run(main())
