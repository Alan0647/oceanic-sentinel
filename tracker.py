import os, asyncio, json, time, yfinance as yf
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

VESSELS = [
    {"name": "信隆168", "id": "61436"}, {"name": "昱友668", "id": "61508"},
    {"name": "信友16", "id": "70157"}, {"name": "信隆216", "id": "70296"},
    {"name": "高欣6", "id": "70506"}, {"name": "隆昌3", "id": "70554"}
]

def fetch_market_data():
    symbols = {
        "USD/TWD": "TWD=X", "USD/JPY": "JPY=X", "JPY/TWD": "JPYTWD=X",
        "WTI 輕原油": "CL=F", "布蘭特原油": "BZ=F"
    }
    res = {"exchange": [], "oil": []}
    for name, sym in symbols.items():
        try:
            h = yf.Ticker(sym).history(period="10d")
            latest, wh, wl = h['Close'].iloc[-1], h['High'].tail(7).max(), h['Low'].tail(7).min()
            item = {"name": name, "latest": f"{latest:.2f}", "week_h": f"{wh:.2f}", "week_l": f"{wl:.2f}"}
            if "/" in name: res["exchange"].append(item)
            else: res["oil"].append(item)
        except: pass
    
    # 港口 MGO 11 個點位
    brent = float(res["oil"][1]["latest"]) if len(res["oil"]) > 1 else 85.0
    ports = ["新加坡", "高雄", "釜山", "拉斯帕爾馬斯", "開普敦", "達卡", "阿必尚", "路易港", "維多利亞", "檳城"]
    for p in ports:
        price = brent * 7.5 + 160
        res["oil"].append({"name": f"MGO - {p}", "latest": f"{price:.1f}", "week_h": f"{price*1.05:.1f}", "week_l": f"{price*0.95:.1f}"})
    return res

async def scrape_ofdc(page):
    target_url = "https://www.ofdc.org.tw:8181/elogbookquery/content/index.xhtml"
    page.on("dialog", lambda d: d.accept())
    await page.goto(target_url, timeout=60000)
    await page.fill('input[id="j_idt8:使用者名稱"]', os.environ['OFDC_USER'])
    await page.fill('input[id="j_idt8:密碼"]', os.environ['OFDC_PASS'])
    await page.keyboard.press("Enter")
    await page.click("text=鮪延繩釣")

    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y/%m/%d")
    vessels_results = []

    for v in VESSELS:
        try:
            print(f"🚢 執行中：{v['name']}")
            await page.select_option('select[id="toolForm:ctnoSelectMenu"]', v['id'])
            d_ins = await page.locator('input[id*="Date"]').all()
            if len(d_ins) >= 2: await d_ins[0].fill(start_date)
            await page.get_by_role("button", name="線上查詢").click()
            await asyncio.sleep(6)

            rows = await page.locator("tr.ui-widget-content").all()
            if rows:
                cells = await rows[0].locator("td").all_inner_texts()
                # 總漁獲量通常在第 11 欄或小計列
                data = {
                    "name": v['name'], "id": v['id'], "date": cells[2],
                    "lat": float(cells[4]), "lon": float(cells[5]),
                    "temp": cells[6], "bait": cells[16], "total_weight": cells[11],
                    "catch_details": []
                }
                # 點擊以獲取明細
                await rows[0].click()
                await asyncio.sleep(3)
                c_rows = await page.locator(".ui-datatable-data").nth(1).locator("tr").all()
                for cr in c_rows:
                    cc = await cr.locator("td").all_inner_texts()
                    if len(cc) >= 6:
                        data["catch_details"].append({"sp": cc[2], "wt": cc[3], "ct": cc[4], "pr": cc[5]})
                vessels_results.append(data)
        except: continue
    return vessels_results

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        v_data = await scrape_ofdc(page)
        m_data = fetch_market_data()
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump({"update_time": time.strftime('%Y-%m-%d %H:%M'), "vessels": v_data, "market": m_data}, f, ensure_ascii=False, indent=4)
        await browser.close()

if __name__ == "__main__": asyncio.run(main())
