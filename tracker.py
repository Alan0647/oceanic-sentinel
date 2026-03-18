import os
import asyncio
from playwright.async_api import async_playwright

# 您的六艘核心船隻清單
VESSELS = [
    {"name": "信隆168", "id": "61436"},
    {"name": "昱友668", "id": "61508"},
    {"name": "信友16", "id": "70157"},
    {"name": "信隆216", "id": "70296"},
    {"name": "高欣6", "id": "70506"},
    {"name": "隆昌3", "id": "70554"}
]

async def run_scraper():
    async with async_playwright() as p:
        # 啟動瀏覽器
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()

        print("🔗 正在前往 OFDC 系統...")
        await page.goto("https://efish.ofdc.org.tw/vms/login") 

        # 1. 執行登入 (使用您提供的精確 ID)
        try:
            await page.fill('input[id="j_idt8:使用者名稱"]', os.environ['OFDC_USER'])
            await page.fill('input[id="j_idt8:密碼"]', os.environ['OFDC_PASS'])
            # 由於沒抓到按鈕 ID，直接按 Enter 鍵通常最保險
            await page.keyboard.press("Enter")
            await page.wait_for_load_state("networkidle")
            print("✅ 登入成功")
        except Exception as e:
            print(f"❌ 登入階段出錯: {e}")
            await browser.close()
            return

        # 2. 開始巡迴抓取六艘船的數據
        final_report = []
        for vessel in VESSELS:
            try:
                print(f"🚢 正在切換至：{vessel['name']} ({vessel['id']})...")
                
                # 使用您提供的 Select ID 切換船隻
                await page.select_option('select[id="toolForm:ctnoSelectMenu"]', vessel['id'])
                
                # 等待表格更新 (通常選單切換後網頁會跳轉或重新整理)
                await page.wait_for_timeout(3000) 
                
                # 抓取第一列數據 (根據您提供的 <tr> 結構)
                # 我們抓取該船隻最新一筆 (第一列) 的所有 <td>
                cells = await page.query_selector_all('tr.ui-widget-content >> td')
                
                if len(cells) >= 12:
                    # 根據您提供的 HTML 排序解析資料：
                    # Index 2: 日期, Index 4: 緯度, Index 5: 經度, Index 11: 漁獲量(範例中是2560)
                    date_val = await cells[2].inner_text()
                    lat_val = await cells[4].inner_text()
                    lon_val = await cells[5].inner_text()
                    weight_val = await cells[11].inner_text()
                    status_val = await cells[20].inner_text() # "作業"

                    print(f"   📍 位置: {lat_val}, {lon_val} | 🐟 本次漁獲: {weight_val} kg | 📅 日期: {date_val}")
                    
                    final_report.append({
                        "vessel": vessel['name'],
                        "date": date_val,
                        "lat": lat_val,
                        "lon": lon_val,
                        "weight": weight_val,
                        "status": status_val
                    })
                else:
                    print(f"   ⚠️ {vessel['name']} 查無近期數據列")

            except Exception as e:
                print(f"   ❌ 處理 {vessel['name']} 時發生錯誤: {e}")

        # 3. 輸出最終結果 (目前先在 Log 顯示，之後可直接對接 Google Sheet)
        print("\n--- 📊 今日漁獲與位標匯報 ---")
        for r in final_report:
            print(f"[{r['vessel']}] 日期:{r['date']} 座標:({r['lat']}, {r['lon']}) 漁獲:{r['weight']}kg 狀態:{r['status']}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())
