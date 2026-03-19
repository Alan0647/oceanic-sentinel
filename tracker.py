import os
import asyncio
import json
import time
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
    print(f"🔄 第 {attempt_count} 次嘗試（解決排版不穩問題）...")
    
    # 處理彈窗
    page.on("dialog", lambda dialog: dialog.accept())

    # 1. 登入
    await page.goto(target_url, timeout=60000, wait_until="networkidle")
    await page.fill('input[id="j_idt8:使用者名稱"]', os.environ['OFDC_USER'])
    await page.fill('input[id="j_idt8:密碼"]', os.environ['OFDC_PASS'])
    await page.keyboard.press("Enter")
    
    # 2. 【紅框檢查】確認「鮪延繩釣」選單是否存在
    print("🔎 檢查頂部導航欄...")
    try:
        # 等待「鮪延繩釣」標籤出現
        tuna_tab = page.get_by_text("鮪延繩釣")
        await tuna_tab.wait_for(state="visible", timeout=20000)
        await tuna_tab.click()
        print("✅ 已點擊「鮪延繩釣」標籤")
    except:
        print("❌ 頁面刷新異常（沒看到鮪延繩釣），觸發重試...")
        raise Exception("Menu not found")

    vessel_data_list = []

    for vessel in VESSELS:
        try:
            print(f"🚢 查詢中：{vessel['name']}...")
            # 選擇船隻
            await page.select_option('select[id="toolForm:ctnoSelectMenu"]', vessel['id'])
            
            # 【橘框操作】點擊「線上查詢」按鈕
            # 這裡使用模糊匹配，因為按鈕 ID 可能會變
            await page.get_by_role("button", name="線上查詢").click()
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(3) # 等待橘框表格載入

            # 抓取橘框（作業資訊）的第一列
            rows = await page.query_selector_all('tr.ui-widget-content')
            if rows:
                target_row = rows[0]
                cells = await target_row.query_selector_all('td')
                
                # 擷取橘框基礎資訊
                base_info = {
                    "name": vessel['name'],
                    "id": vessel['id'],
                    "date": await cells[2].inner_text(),
                    "lat": await cells[4].inner_text(),
                    "lon": await cells[5].inner_text(),
                    "sea_temp": await cells[6].inner_text(), # 橘框裡的海面溫度
                    "update_time": time.strftime('%Y-%m-%d %H:%M')
                }

                # 【綠框觸發】點擊該列以顯示下方漁獲明細
                await target_row.click()
                print(f"   👇 已點擊作業列，等待漁獲明細...")
                await asyncio.sleep(3) # 等待下方綠框表格刷新

                # 擷取綠框資訊 (假設魚種資訊在特定的 table 裡)
                # 我們可以抓取所有漁獲列並加總，或抓取主要魚種
                catch_summary = ""
                catch_rows = await page.query_selector_all('.ui-datatable-data tr')
                # 這裡過濾出屬於綠框（漁獲）的資料
                for c_row in catch_rows:
                    c_cells = await c_row.query_selector_all('td')
                    if len(c_cells) > 4:
                        species = await c_cells[2].inner_text()
                        weight = await c_cells[3].inner_text()
                        catch_summary += f"{species}:{weight}kg "
                
                base_info["weight"] = catch_summary if catch_summary else "無明細"
                vessel_data_list.append(base_info)
                print(f"   📍 座標:({base_info['lat']},{base_info['lon']}) 溫度:{base_info['sea_temp']}°C")
            else:
                print(f"   ⚠️ {vessel['name']} 無作業資訊")

        except Exception as e:
            print(f"   ❌ 讀取 {vessel['name']} 失敗: {str(e)[:50]}")

    return vessel_data_list

async def run_scraper():
    MAX_RETRIES = 5
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for i in range(1, MAX_RETRIES + 1):
            context = await browser.new_context(viewport={'width': 1280, 'height': 1000})
            page = await context.new_page()
            try:
                results = await scrape_attempt(page, i)
                if results:
                    with open('data.json', 'w', encoding='utf-8') as f:
                        json.dump(results, f, ensure_ascii=False, indent=4)
                    print(f"🎉 任務完成，共抓取 {len(results)} 艘船資料。")
                    await browser.close()
                    return
            except Exception as e:
                print(f"⚠️ 嘗試 {i} 失敗。")
                await page.screenshot(path=f"debug_screen_{i}.png")
                await context.close()
        await browser.close()
        raise Exception("多次重試均失敗")

if __name__ == "__main__":
    asyncio.run(run_scraper())
