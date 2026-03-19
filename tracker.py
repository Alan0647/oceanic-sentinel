import os
import asyncio
import json
import time
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

VESSELS = [
    {"name": "信隆168", "id": "61436"},
    {"name": "昱友668", "id": "61508"},
    {"name": "信友16", "id": "70157"},
    {"name": "信隆216", "id": "70296"},
    {"name": "高欣6", "id": "70506"},
    {"name": "隆昌3", "id": "70554"}
]

async def scrape_attempt(page, attempt_count):
    target_url = "https://www.ofdc.org.tw:8181/elogbookquery/content/index.xhtml"
    print(f"🔄 第 {attempt_count} 次執行 | 自動回推一週查詢模式")
    
    page.on("dialog", lambda dialog: dialog.accept())

    # 1. 執行登入
    await page.goto(target_url, timeout=60000)
    await page.fill('input[id="j_idt8:使用者名稱"]', os.environ['OFDC_USER'])
    await page.fill('input[id="j_idt8:密碼"]', os.environ['OFDC_PASS'])
    await page.keyboard.press("Enter")
    
    # 2. 點擊「鮪延繩釣」標籤
    print("🔎 正在導航至鮪延繩釣區塊...")
    tuna_tab = page.locator("a:has-text('鮪延繩釣'), span:has-text('鮪延繩釣')").first
    await tuna_tab.wait_for(state="visible", timeout=20000)
    await tuna_tab.click()
    await page.wait_for_load_state("networkidle")

    # 計算日期：回推 7 天
    today = datetime.now()
    start_date = (today - timedelta(days=7)).strftime("%Y/%m/%d")
    end_date = today.strftime("%Y/%m/%d")
    print(f"📅 查詢區間設定：{start_date} ~ {end_date}")

    vessel_data_list = []

    for vessel in VESSELS:
        try:
            print(f"🚢 查詢中：{vessel['name']}...")
            await page.wait_for_selector('select[id="toolForm:ctnoSelectMenu"]', timeout=10000)
            await page.select_option('select[id="toolForm:ctnoSelectMenu"]', vessel['id'])
            
            # [新增] 設定日期區間 (針對橘框內的日期輸入欄位)
            # 通常 PrimeFaces 的日期欄位 ID 會包含 Date_input
            try:
                date_inputs = await page.locator('input[id*="Date"]').all()
                if len(date_inputs) >= 2:
                    await date_inputs[0].fill(start_date) # 開始日期
                    await date_inputs[1].fill(end_date)   # 結束日期
            except:
                print("   ⚠️ 無法自動填寫日期，嘗試直接查詢預設範圍")

            # 按下「線上查詢」
            await page.get_by_role("button", name="線上查詢").click()
            await asyncio.sleep(6) # 穩定等待 AJAX 載入

            # 3. 抓取橘框第一列 (最新作業資訊)
            rows = await page.locator("tr.ui-widget-content").all()
            if len(rows) > 0:
                target_row = rows[0]
                # 修正 all_inner_texts 語法錯誤
                cells = await target_row.locator("td").all_inner_texts()
                
                if len(cells) > 10:
                    data = {
                        "name": vessel['name'],
                        "id": vessel['id'],
                        "date": cells[2],
                        "lat": cells[4],
                        "lon": cells[5],
                        "sea_temp": cells[6] if len(cells) > 6 else "N/A",
                        "update_time": time.strftime('%Y-%m-%d %H:%M')
                    }

                    # 4. 點擊該列觸發綠框 (漁獲明細)
                    await target_row.click()
                    await asyncio.sleep(4) 

                    # 擷取漁獲重量 (依照您先前提供的 index 11)
                    data["weight"] = cells[11] if len(cells) > 11 else "待確認"
                    
                    vessel_data_list.append(data)
                    print(f"   ✅ 成功抓取：{data['date']} | 座標:({data['lat']},{data['lon']}) | 漁獲:{data['weight']}")
                else:
                    print(f"   ⚠️ 欄位結構異常")
            else:
                print(f"   ⚠️ 近一週無作業紀錄")

        except Exception as e:
            print(f"   ❌ {vessel['name']} 讀取失敗: {str(e)[:100]}")

    return vessel_data_list

async def run_scraper():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1440, 'height': 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)..."
        )
        
        results = []
        try:
            results = await scrape_attempt(await context.new_page(), 1)
        except Exception as e:
            print(f"❌ 嚴重錯誤: {e}")
            
        if results:
            with open('data.json', 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=4)
            print(f"🎉 更新完成，共 {len(results)} 艘船。")
        else:
            print("💀 未能抓取到任何資料。")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())
