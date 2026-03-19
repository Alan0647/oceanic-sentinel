import os, asyncio, json, time, yfinance as yf
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

VESSELS = [
    {"name": "信隆168", "id": "61436"}, {"name": "昱友668", "id": "61508"},
    {"name": "信友16", "id": "70157"}, {"name": "信隆216", "id": "70296"},
    {"name": "高欣6", "id": "70506"}, {"name": "隆昌3", "id": "70554"}
]

def fetch_market_info():
    print("📈 抓取金融數據中...")
    symbols = {
        "USD/TWD": "TWD=X", "USD/JPY": "JPY=X", "JPY/TWD": "JPYTWD=X",
        "WTI 輕原油": "CL=F", "布蘭特原油": "BZ=F"
    }
    market = {"exchange": [], "oil": []}
    for name, sym in symbols.items():
        try:
            t = yf.Ticker(sym)
            h = t.history(period="10d")
            if not h.empty:
                latest = h['Close'].iloc[-1]
                week_h = h['High'].tail(7).max()
                week_l = h['Low'].tail(7).min()
                item = {"name": name, "latest": f"{latest:.2f}", "week_h": f"{week_h:.2f}", "week_l": f"{week_l:.2f}"}
                if "/" in name: market["exchange"].append(item)
                else: market["oil"].append(item)
        except: print(f"⚠️ {name} 抓取失敗")
    
    # 港口 MGO 報價 (以 Brent 為基準模擬，確保數據連動)
    brent = float(market["oil"][1]["latest"]) if len(market["oil"]) > 1 else 82.0
    ports = ["新加坡", "高雄", "釜山", "拉斯帕爾馬斯", "開普敦", "達卡", "阿必尚", "路易港", "維多利亞", "檳城"]
    for p in ports:
        price = brent * 7.5 + 160 # 模擬換算
        market["oil"].append({"name": f"MGO - {p}", "latest": f"{price:.1f}", "week_h": f"{price*1.05:.1f}", "week_l": f"{price*0.95:.1f}"})
    return market

async def scrape_vessels(page):
    target_url = "https://www.ofdc.org.tw:8181/elogbookquery/content/index.xhtml"
    page.on("dialog", lambda d: d.accept())
    await page.goto(target_url, timeout=60000)
    await page.fill('input[id="j_idt8:使用者名稱"]', os.environ['OFDC_USER'])
    await page.fill('input[id="j_idt8:密碼"]', os.environ['OFDC_PASS'])
    await page.keyboard.press("Enter")
    
    # 耐心等待「鮪延繩釣」標籤
    tuna_tab = page.locator("text=鮪延繩釣").first
    await tuna_tab.wait_for(state="visible", timeout=30000)
    await tuna_tab.click()

    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y/%m/%d")
    results = []

    for vessel in VESSELS:
        try:
            print(f"🚢 執行：{vessel['name']}")
            await page.select_option('select[id="toolForm:ctnoSelectMenu"]', vessel['id'])
            
            # 填寫回推日期
            date_in = await page.locator('input[id*="Date"]').all()
            if len(date_in) >= 2: await date_in[0].fill(start_date)
            
            await page.get_by_role("button", name="線上查詢").click()
            await asyncio.sleep(5)

            rows = await page.locator("tr.ui-widget-content").all()
            if rows:
                target_row = rows[0]
                cells = await target_row.locator("td").all_inner_texts()
                data = {
                    "name": vessel['name'], "id": vessel['id'], "date": cells[2],
                    "lat": float(cells[4]), "lon": float(cells[5]),
                    "temp": cells[6], "bait": cells[16], "catch_details": []
                }
                # 點擊行觸發綠框
                await target_row.click()
                await asyncio.sleep(3)
                # 抓取綠框漁獲
                c_rows = await page.locator(".ui-datatable-data").nth(1).locator("tr").all()
                for cr in c_rows:
                    cc = await cr.locator("td").all_inner_texts()
                    if len(cc) >= 6:
                        data["catch_details"].append({"sp": cc[2], "wt": cc[3], "ct": cc[4], "pr": cc[5]})
                results.append(data)
        except: continue
    return results

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        v_data = await scrape_vessels(page)
        m_data = fetch_market_info()
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump({"update_time": time.strftime('%Y-%m-%d %H:%M'), "vessels": v_data, "market": m_data}, f, ensure_ascii=False, indent=4)
        await browser.close()

if __name__ == "__main__": asyncio.run(main())
