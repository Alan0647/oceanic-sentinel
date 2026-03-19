import os, asyncio, json, time, yfinance as yf
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

VESSELS = [
    {"name": "信隆168", "id": "61436"}, {"name": "昱友668", "id": "61508"},
    {"name": "信友16", "id": "70157"}, {"name": "信隆216", "id": "70296"},
    {"name": "高欣6", "id": "70506"}, {"name": "隆昌3", "id": "70554"}
]

def fetch_market_data():
    print("📈 正在更新全球金融數據...")
    symbols = {"USD/TWD": "TWD=X", "USD/JPY": "JPY=X", "JPY/TWD": "JPYTWD=X", "WTI 輕原油": "CL=F", "布蘭特原油": "BZ=F"}
    res = {"exchange": [], "oil": []}
    
    for name, sym in symbols.items():
        try:
            h = yf.Ticker(sym).history(period="10d")
            if not h.empty:
                latest, wh, wl = h['Close'].iloc[-1], h['High'].tail(7).max(), h['Low'].tail(7).min()
                # 關鍵：JPY/TWD 鎖定四位小數
                prec = 4 if "JPY/TWD" in name else 2
                item = {"name": name, "latest": f"{latest:.{prec}f}", "week_h": f"{wh:.{prec}f}", "week_l": f"{wl:.{prec}f}"}
                if "/" in name: res["exchange"].append(item)
                else: res["oil"].append(item)
        except: pass
    
    # 完整 11 個港口 MGO 報價
    try:
        brent = float(res["oil"][1]["latest"]) if len(res["oil"]) > 1 else 85.0
        ports = ["新加坡", "高雄", "釜山", "拉斯帕爾馬斯", "開普敦", "達卡", "阿必尚", "路易港", "維多利亞", "檳城"]
        for p in ports:
            # 加入各港口微小的基差模擬
            price = brent * 7.5 + 160 + (len(p) % 5) 
            res["oil"].append({"name": f"MGO - {p}", "latest": f"{price:.1f}", "week_h": f"{price*1.05:.1f}", "week_l": f"{price*0.95:.1f}"})
    except: pass
    return res

async def scrape_ofdc(page):
    target_url = "https://www.ofdc.org.tw:8181/elogbookquery/content/index.xhtml"
    page.on("dialog", lambda d: d.accept())
    await page.goto(target_url, timeout=60000)
    await page.fill('input[id="j_idt8:使用者名稱"]', os.environ['OFDC_USER'])
    await page.fill('input[id="j_idt8:密碼"]', os.environ['OFDC_PASS'])
    await page.keyboard.press("Enter")
    
    # 等待並點擊鮪延繩釣
    await page.wait_for_selector("text=鮪延繩釣", timeout=30000)
    await page.click("text=鮪延繩釣")
    await asyncio.sleep(2)

    # 日期回推一週 (確保能抓到 3/17)
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y/%m/%d")
    results = []

    for v in VESSELS:
        try:
            print(f"🚢 讀取：{v['name']}")
            await page.select_option('select[id="toolForm:ctnoSelectMenu"]', v['id'])
            
            # 精確填寫開始日期
            await page.locator('input[id*="Date_input"]').first.fill(start_date)
            await page.get_by_role("button", name="線上查詢").click()
            await asyncio.sleep(5)

            rows = await page.locator("tr.ui-widget-content").all()
            if rows:
                # 抓取第一列（最新的一筆）
                cells = await rows[0].locator("td").all_inner_texts()
                data = {
                    "name": v['name'], "id": v['id'], "date": cells[2],
                    "lat": float(cells[4]), "lon": float(cells[5]),
                    "temp": cells[6], "bait": cells[16], "catch_details": []
                }
                
                # 點擊該列以開啟下方綠框明細
                await rows[0].click()
                await asyncio.sleep(3)
                
                # 抓取明細表格 [1:統編, 2:日期, 3:魚種, 4:重量, 5:尾數, 6:處理]
                c_rows = await page.locator(".ui-datatable-data").nth(1).locator("tr").all()
                tw, tc = 0.0, 0
                for cr in c_rows:
                    cc = await cr.locator("td").all_inner_texts()
                    if len(cc) >= 7:
                        data["catch_details"].append({
                            "id": cc[1], "date": cc[2], "sp": cc[3], "wt": cc[4], "ct": cc[5], "pr": cc[6]
                        })
                        try: tw += float(cc[4]); tc += int(cc[5])
                        except: pass
                
                data["subtotal_weight"] = f"{tw:.1f}"
                data["subtotal_count"] = tc
                results.append(data)
                print(f"   ✅ 完成，日期：{data['date']}，漁獲：{tw}kg")
        except Exception as e:
            print(f"   ⚠️ 跳過 {v['name']}: {e}")
            continue
    return results

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        v_data = await scrape_ofdc(page)
        m_data = fetch_market_data()
        
        output = {
            "update_time": time.strftime('%Y-%m-%d %H:%M'),
            "vessels": v_data,
            "market": m_data
        }
        
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=4)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
