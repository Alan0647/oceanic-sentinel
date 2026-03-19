import os, asyncio, json, time
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

VESSELS = [
    {"name": "信隆168", "id": "61436"}, {"name": "昱友668", "id": "61508"},
    {"name": "信友16", "id": "70157"}, {"name": "信隆216", "id": "70296"},
    {"name": "高欣6", "id": "70506"}, {"name": "隆昌3", "id": "70554"}
]

async def scrape_attempt(page, attempt_count):
    target_url = "https://www.ofdc.org.tw:8181/elogbookquery/content/index.xhtml"
    page.on("dialog", lambda dialog: dialog.accept())
    await page.goto(target_url, timeout=60000)
    
    # 登入與導航
    await page.fill('input[id="j_idt8:使用者名稱"]', os.environ['OFDC_USER'])
    await page.fill('input[id="j_idt8:密碼"]', os.environ['OFDC_PASS'])
    await page.keyboard.press("Enter")
    await page.click("text=鮪延繩釣")
    await page.wait_for_load_state("networkidle")

    vessel_data_list = []
    # 查詢區間設定 (回推7天)
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y/%m/%d")

    for vessel in VESSELS:
        try:
            print(f"🚢 深度分析：{vessel['name']}...")
            await page.select_option('select[id="toolForm:ctnoSelectMenu"]', vessel['id'])
            # 填寫日期
            date_inputs = await page.locator('input[id*="Date"]').all()
            if len(date_inputs) >= 2: await date_inputs[0].fill(start_date)
            
            await page.get_by_role("button", name="線上查詢").click()
            await asyncio.sleep(5) 

            rows = await page.locator("tr.ui-widget-content").all()
            if len(rows) > 0:
                target_row = rows[0]
                cells = await target_row.locator("td").all_inner_texts()
                
                # 擷取橘框資訊
                data = {
                    "name": vessel['name'], "id": vessel['id'],
                    "date": cells[2], "lat": float(cells[4]), "lon": float(cells[5]),
                    "sea_temp": cells[6], "bait": cells[16],
                    "total_weight": cells[11], "update_time": time.strftime('%Y-%m-%d %H:%M')
                }

                # 【點擊綠框連動】
                await target_row.click()
                await asyncio.sleep(3) 

                # 抓取漁獲明細表格
                catch_list = []
                catch_rows = await page.locator(".ui-datatable-data").nth(1).locator("tr").all()
                for cr in catch_rows:
                    c_cells = await cr.locator("td").all_inner_texts()
                    if len(c_cells) >= 5:
                        catch_list.append({
                            "species": c_cells[2], "weight": c_cells[3],
                            "count": c_cells[4], "process": c_cells[5]
                        })
                data["catch_details"] = catch_list
                vessel_data_list.append(data)
                print(f"   ✅ 抓取到 {len(catch_list)} 項漁獲明細")
            
        except Exception as e:
            print(f"   ❌ {vessel['name']} 失敗: {e}")

    return vessel_data_list

async def run_scraper():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1440, 'height': 1000})
        try:
            results = await scrape_attempt(await context.new_page(), 1)
            if results:
                with open('data.json', 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=4)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())
