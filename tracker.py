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
    print(f"🔄 第 {attempt_count} 次嘗試（深度掃描模式）...")
    
    page.on("dialog", lambda dialog: dialog.accept())

    # 1. 登入
    await page.goto(target_url, timeout=60000)
    await page.fill('input[id="j_idt8:使用者名稱"]', os.environ['OFDC_USER'])
    await page.fill('input[id="j_idt8:密碼"]', os.environ['OFDC_PASS'])
    await page.keyboard.press("Enter")
    
    # 2. 深度等待標籤出現
    print("🔎 正在掃描「鮪延繩釣」標籤...")
    
    found = False
    for r in range(3): # 在同一節點內嘗試重新整理 3 次
        try:
            # 嘗試使用多種選取方式 (文字匹配或特定的 PrimeFaces 類別)
            tuna_tab = page.locator("a:has-text('鮪延繩釣'), span:has-text('鮪延繩釣')").first
            await tuna_tab.wait_for(state="visible", timeout=15000)
            await tuna_tab.click()
            print("✅ 成功點擊「鮪延繩釣」")
            found = True
            break
        except:
            print(f"   ⚠️ 標籤未出現，嘗試第 {r+1} 次重新整理頁面...")
            await page.reload(wait_until="networkidle")
            await asyncio.sleep(5)

    if not found:
        raise Exception("Menu Not Found After Reloads")

    vessel_data_list = []
    # 切換到您截圖中的主內容區域
    for vessel in VESSELS:
        try:
            print(f"🚢 查詢中：{vessel['name']}...")
            # 確保選單已加載
            await page.wait_for_selector('select[id="toolForm:ctnoSelectMenu"]', timeout=10000)
            await page.select_option('select[id="toolForm:ctnoSelectMenu"]', vessel['id'])
            
            # 按下「線上查詢」
            await page.get_by_role("button", name="線上查詢").click()
            await asyncio.sleep(5) # 給予充足時間讓橘框表格跳出來

            # 抓取橘框第一列
            rows = await page.locator("tr.ui-widget-content").all()
            if len(rows) > 0:
                target_row = rows[0]
                cells = await target_row.locator("td").all_texts()
                
                data = {
                    "name": vessel['name'],
                    "id": vessel['id'],
                    "date": cells[2],
                    "lat": cells[4],
                    "lon": cells[5],
                    "sea_temp": cells[6] if len(cells) > 6 else "N/A",
                    "update_time": time.strftime('%Y-%m-%d %H:%M')
                }

                # 點擊該列觸發綠框
                await target_row.click()
                await asyncio.sleep(4) 

                # 簡單抓取漁獲摘要 (搜尋所有包含 kg 的文字)
                all_text = await page.content()
                # 這是一個保險做法，抓取頁面上出現的所有數字與單位
                data["weight"] = cells[11] if len(cells) > 11 else "待確認"
                
                vessel_data_list.append(data)
                print(f"   📍 位置: {data['lat']}, {data['lon']} | 漁獲: {data['weight']}")
            else:
                print(f"   ⚠️ 查無此船今日作業資訊")

        except Exception as e:
            print(f"   ❌ {vessel['name']} 讀取失敗: {str(e)[:50]}")

    return vessel_data_list

async def run_scraper():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # 使用更像真實瀏覽器的設定
        context = await browser.new_context(
            viewport={'width': 1440, 'height': 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        results = []
        try:
            # 我們這裡只跑一輪，內層有 Reload 機制
            results = await scrape_attempt(await context.new_page(), 1)
        except Exception as e:
            print(f"❌ 任務失敗: {e}")
            # 這裡很重要！失敗時會留下一張最後的畫面截圖
            await (await context.pages)[0].screenshot(path="final_debug_error.png")
            
        if results:
            with open('data.json', 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=4)
            print(f"🎉 成功完成！共更新 {len(results)} 艘船隻。")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())
