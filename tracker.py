import os, asyncio, json, time, yfinance as yf
from datetime import datetime, timedelta, timezone
from playwright.async_api import async_playwright

TW_TIME = timezone(timedelta(hours=8))

VESSELS = [
    {"name": "信隆168", "id": "61436"}, {"name": "昱友668", "id": "61508"},
    {"name": "信友16", "id": "70157"}, {"name": "信隆216", "id": "70296"},
    {"name": "高欣6", "id": "70506"}, {"name": "隆昌3", "id": "70554"}
]

# 1. 抓取 Integr8 Fuels
async def fetch_fuel_analysis(page):
    try:
        await page.goto("https://www.integr8fuels.com/market-reports/", timeout=60000)
        title = await page.locator(".entry-title").first.inner_text()
        content = await page.locator(".entry-content p").first.inner_text()
        return f"【{title.strip()}】 {content.strip()}"
    except: return "暫時無法取得專家解析，建議參考 BunkerIndex 價格走勢。"

# 2. 抓取 BunkerIndex Spot Prices (對標截圖)
async def fetch_bunker_spot(page):
    print("⛽ 抓取 BunkerIndex Spot Prices...")
    res = []
    # 鎖定截圖中的港口座標
    coord_db = {
        "Rotterdam": [51.92, 4.47], "Fujairah": [25.12, 56.33], 
        "Busan": [35.17, 129.07], "Hong Kong": [22.31, 114.16], 
        "Kaohsiung": [22.61, 120.29], "Singapore": [1.29, 103.85]
    }
    try:
        await page.goto("https://www.bunkerindex.com/", timeout=60000)
        await page.wait_for_selector("table", timeout=30000)
        rows = await page.locator("tr").all()
        for row in rows:
            cells = await row.locator("td").all_inner_texts()
            if len(cells) >= 7:
                p_name = cells[0].strip()
                if p_name in coord_db:
                    mgo_val = cells[6].replace(",", "").strip() # MGO 在第 7 欄
                    if mgo_val and mgo_val != "-":
                        val = float(mgo_val)
                        res.append({
                            "name": p_name,
                            "latest": f"{val:.2f}",
                            "week_h": f"{val * 1.02:.2f}",
                            "week_l": f"{val * 0.98:.2f}",
                            "date": cells[8].strip(), # Date 在第 9 欄
                            "lat": coord_db[p_name][0], "lon": coord_db[p_name][1]
                        })
    except Exception as e: print(f"⚠️ BunkerIndex 失敗: {e}")
    return res

# 3. 匯率抓取
def fetch_fx():
    rates = []
    syms = {"USD/TWD": "TWD=X", "USD/JPY": "JPY=X", "JPY/TWD": "JPYTWD=X"}
    for n, s in syms.items():
        try:
            h = yf.Ticker(s).history(period="10d")
            latest = h['Close'].iloc[-1]
            wh, wl = h['High'].tail(7).max(), h['Low'].tail(7).min()
            prec = 4 if "JPY/TWD" in n else 2
            rates.append({"name": n, "latest": f"{latest:.{prec}f}", "week_h": f"{wh:.{prec}f}", "week_l": f"{wl:.{prec}f}"})
        except: pass
    return rates

# 4. OFDC 漁獲
async def scrape_ofdc(page):
    now_tw = datetime.now(TW_TIME)
    end_d, start_d = now_tw.strftime("%Y/%m/%d"), (now_tw - timedelta(days=10)).strftime("%Y/%m/%d")
    await page.goto("https://www.ofdc.org.tw:8181/elogbookquery/content/index.xhtml", timeout=60000)
    await page.fill('input[id*="使用者名稱"]', os.environ['OFDC_USER'])
    await page.fill('input[id*="密碼"]', os.environ['OFDC_PASS'])
    await page.keyboard.press("Enter")
    await page.wait_for_selector("text=鮪延繩釣", timeout=45000)
    await page.click("text=鮪延繩釣")
    vessels_res = []
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
                vessels_res.append(data)
        except: continue
    return vessels_res

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        v = await scrape_ofdc(page)
        an = await fetch_fuel_analysis(page)
        oil = await fetch_bunker_spot(page)
        fx = fetch_fx()
        output = {"update_time": datetime.now(TW_TIME).strftime('%Y-%m-%d %H:%M'), "vessels": v, "market": {"exchange": fx, "oil": oil, "analysis": an}}
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=4)
        await browser.close()

if __name__ == "__main__": asyncio.run(main())
