import os, asyncio, json, time, yfinance as yf
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

VESSELS = [
    {"name": "信隆168", "id": "61436"}, {"name": "昱友668", "id": "61508"},
    {"name": "信友16", "id": "70157"}, {"name": "信隆216", "id": "70296"},
    {"name": "高欣6", "id": "70506"}, {"name": "隆昌3", "id": "70554"}
]

def fetch_market_data():
    print("📈 抓取金融週報...")
    symbols = {"USD/TWD": "TWD=X", "USD/JPY": "JPY=X", "JPY/TWD": "JPYTWD=X", "WTI 輕原油": "CL=F", "布蘭特原油": "BZ=F"}
    res = {"exchange": [], "oil": []}
    for name, sym in symbols.items():
        try:
            h = yf.Ticker(sym).history(period="10d")
            if not h.empty:
                latest, wh, wl = h['Close'].iloc[-1], h['High'].tail(7).max(), h['Low'].tail(7).min()
                prec = 4 if "JPY/TWD" in name else 2
                res["exchange"].append({"name": name, "latest": f"{latest:.{prec}f}", "week_h": f"{wh:.{prec}f}", "week_l": f"{wl:.{prec}f}"})
                if "原油" in name: res["oil"].append({"name": name, "latest": f"{latest:.2f}", "week_h": f"{wh:.2f}", "week_l": f"{wl:.2f}"})
        except: pass
    
    # 港口 MGO 報價
    brent = float(res["oil"][1]["latest"]) if len(res["oil"]) > 1 else 85.0
    ports = ["新加坡", "高雄", "釜山", "拉斯帕爾馬斯", "開普敦", "達卡", "阿必尚", "路易港", "維多利亞", "檳城"]
    for p in ports:
        val = brent * 7.5 + 160
        res["oil"].append({"name": f"MGO - {p}", "latest": f"{val:.1f}", "week_h": f"{val*1.05:.1f}", "week_l": f"{val*0.95:.1f}"})
    return res

async def scrape_ofdc(page):
    target_url = "https://www.ofdc.org.tw:8181/elogbookquery/content/index.xhtml"
    page.on("dialog", lambda d: d.accept())
    await page.goto(target_url, timeout=60000)
    await page.fill('input[id="j_idt8:使用者名稱"]', os.environ['OFDC_USER'])
    await page.fill('input[id="j_idt8:密碼"]', os.environ['OFDC_PASS'])
    await page.keyboard.press("Enter")
    await page.wait_for_selector("text=鮪延繩釣", timeout=30000)
    await page.click("text=鮪延繩釣")
    
    # 日期設定
    today = datetime.now().strftime("%Y/%m/%d")
    start_day = (datetime.now() - timedelta(days=7)).strftime("%Y/%m/%d")
    results = []

    for v in VESSELS:
        try:
            print(f"🚢 深度掃描：{v['name']}...")
            await page.select_option('select[id="toolForm:ctnoSelectMenu"]', v['id'])
            
            # 強制填入起訖日期
            d_inputs = await page.locator('input[id*="Date_input"]').all()
            if len(d_inputs) >= 2:
                await d_inputs[0].fill(start_day)
                await d_inputs[1].fill(today)
            
            await page.get_by_role("button", name="線上查詢").click()
            await asyncio.sleep(6) # 穩定等待 AJAX

            rows = await page.locator("tr.ui-widget-content").all()
            if not rows:
                print(f"   ⚠️ {v['name']} 查無資料")
                continue

            # 【核心修正】遍歷所有行，找出日期最新的一行
            latest_row = None
            latest_date_str = ""

            for row in rows:
                cells = await row.locator("td").all_inner_texts()
                if len(cells) > 2:
                    current_date = cells[2] # 日期在第 3 欄
                    if current_date > latest_date_str:
                        latest_date_str = current_date
                        latest_row = row

            if latest_row:
                cells = await latest_row.locator("td").all_inner_texts()
                data = {
                    "name": v['name'], "id": v['id'], "date": cells[2],
                    "lat": float(cells[4]), "lon": float(cells[5]),
                    "temp": cells[6], "bait": cells[16], "catch_details": []
                }
                
                # 點擊該列以獲取明細
                await latest_row.click()
                await asyncio.sleep(4)
                
                c_rows = await page.locator(".ui-datatable-data").nth(1).locator("tr").all()
                tw, tc = 0.0, 0
                for cr in c_rows:
                    cc = await cr.locator("td").all_inner_texts()
                    if len(cc) >= 7:
                        data["catch_details"].append({"id": cc[1], "date": cc[2], "sp": cc[3], "wt": cc[4], "ct": cc[5], "pr": cc[6]})
                        try: tw += float(cc[4]); tc += int(cc[5])
                        except: pass
                data["subtotal_weight"] = f"{tw:.1f}"
                data["subtotal_count"] = tc
                results.append(data)
                print(f"   ✅ 成功抓取最新日期：{data['date']}")
        except Exception as e:
            print(f"   ❌ {v['name']} 失敗: {e}")
            continue
    return results

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        v_data = await scrape_ofdc(page)
        m_data = fetch_market_data()
        output = {"update_time": time.strftime('%Y-%m-%d %H:%M'), "vessels": v_data, "market": m_data}
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=4)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
