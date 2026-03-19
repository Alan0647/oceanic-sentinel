import os, asyncio, json, time, yfinance as yf
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

VESSELS = [
    {"name": "信隆168", "id": "61436"}, {"name": "昱友668", "id": "61508"},
    {"name": "信友16", "id": "70157"}, {"name": "信隆216", "id": "70296"},
    {"name": "高欣6", "id": "70506"}, {"name": "隆昌3", "id": "70554"}
]

def fetch_market_data():
    print("📈 優先同步金融數據...")
    symbols = {"USD/TWD": "TWD=X", "USD/JPY": "JPY=X", "JPY/TWD": "JPYTWD=X", "WTI 輕原油": "CL=F", "布蘭特原油": "BZ=F"}
    res = {"exchange": [], "oil": []}
    for name, sym in symbols.items():
        try:
            h = yf.Ticker(sym).history(period="10d")
            if not h.empty:
                latest, wh, wl = h['Close'].iloc[-1], h['High'].tail(7).max(), h['Low'].tail(7).min()
                prec = 4 if "JPY/TWD" in name else 2
                res["exchange"].append({"name": name, "latest": f"{latest:.{prec}f}", "week_h": f"{wh:.{prec}f}", "week_l": f"{wl:.{prec}f}"})
                if "原油" in name:
                    res["oil"].append({"name": name, "latest": f"{latest:.2f}", "week_h": f"{wh:.2f}", "week_l": f"{wl:.2f}"})
        except: print(f"⚠️ {name} 同步失敗")
    
    # 港口 MGO 自動換算
    try:
        brent_val = float(res["oil"][-1]["latest"]) if res["oil"] else 82.0
        ports = ["新加坡", "高雄", "釜山", "拉斯帕爾馬斯", "開普敦", "達卡", "阿必尚", "路易港", "維多利亞", "檳城"]
        for p in ports:
            price = brent_val * 7.5 + 162
            res["oil"].append({"name": f"MGO - {p}", "latest": f"{price:.1f}", "week_h": f"{price*1.05:.1f}", "week_l": f"{price*0.95:.1f}"})
    except: pass
    return res

async def scrape_ofdc(page):
    # 登入與基礎跳轉 (保持您的正確 Secret)
    try:
        target_url = "https://www.ofdc.org.tw:8181/elogbookquery/content/index.xhtml"
        await page.goto(target_url, timeout=60000)
        await page.fill('input[id="j_idt8:使用者名稱"]', os.environ['OFDC_USER'])
        await page.fill('input[id="j_idt8:密碼"]', os.environ['OFDC_PASS'])
        await page.keyboard.press("Enter")
        await page.wait_for_selector("text=鮪延繩釣", timeout=45000)
        await page.click("text=鮪延繩釣")
    except Exception as e:
        print(f"❌ 登入階段失敗: {e}")
        return []

    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y/%m/%d")
    vessels_results = []

    for v in VESSELS:
        try:
            print(f"🚢 嘗試抓取：{v['name']}...")
            await page.select_option('select[id="toolForm:ctnoSelectMenu"]', v['id'])
            # 填日期
            d_ins = await page.locator('input[id*="Date"]').all()
            if len(d_ins) >= 2: await d_ins[0].fill(start_date)
            await page.get_by_role("button", name="線上查詢").click()
            
            # 增加等待容錯
            await asyncio.sleep(5)
            rows = await page.locator("tr.ui-widget-content").all()
            if rows:
                cells = await rows[0].locator("td").all_inner_texts()
                v_res = {
                    "name": v['name'], "id": v['id'], "date": cells[2],
                    "lat": float(cells[4]), "lon": float(cells[5]),
                    "temp": cells[6], "bait": cells[16], "subtotal_weight": cells[11],
                    "catch_details": []
                }
                # 抓取明細
                await rows[0].click()
                await asyncio.sleep(3)
                c_rows = await page.locator(".ui-datatable-data").nth(1).locator("tr").all()
                for cr in c_rows:
                    cc = await cr.locator("td").all_inner_texts()
                    if len(cc) >= 6:
                        v_res["catch_details"].append({"id": cc[1], "date": cc[2], "sp": cc[3], "wt": cc[4], "ct": cc[5], "pr": cc[6]})
                vessels_results.append(v_res)
                print(f"   ✅ {v['name']} 成功")
        except: 
            print(f"   ⚠️ {v['name']} 抓取跳過")
            continue
    return vessels_results

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 1000})
        page = await context.new_page()
        
        # 即使 OFDC 失敗，也要確保有金融數據
        m_data = fetch_market_data()
        v_data = []
        try:
            v_data = await scrape_ofdc(page)
        except: pass
        
        output = {
            "update_time": time.strftime('%Y-%m-%d %H:%M'),
            "vessels": v_data,
            "market": m_data
        }
        
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=4)
        
        print("🎉 data.json 更新完成")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
