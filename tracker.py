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
        context = await browser.new_page()
        
        # 🔗 更新為正確的 OFDC 8181 端口網址
        target_url = "https://www.ofdc.org.tw:8181/elogbookquery/content/index.xhtml"
        print(f"🔗 正在嘗試前往 OFDC 系統: {target_url}")

        try:
            # 增加 timeout 到 60 秒，並忽略 HTTPS 憑證錯誤（針對 8181 端口常有的問題）
            await context.goto(target_url, timeout=60000, wait_until="networkidle")
            
            # 1. 執行登入 (使用您提供的精確 ID)
            await context.fill('input[id="j_idt8:使用者名稱"]', os.environ['OFDC_USER'])
            await context.fill('input[id="j_idt8:密碼"]', os.environ['OFDC_PASS'])
            
            print("🔑 帳密已輸入，嘗試登入...")
            await context.keyboard.press("Enter")
            
            # 等待登入後的特徵元素出現 (例如搜尋框)
            await context.wait_for_selector('select[id="toolForm:ctnoSelectMenu"]', timeout=30000)
            print("✅ 登入成功")

            final_report = []
            for vessel in VESSELS:
                print(f"🚢 正在查詢：{vessel['name']} ({vessel['id']})...")
                
                # 切換船隻
                await context.select_option('select[id="toolForm:ctnoSelectMenu"]', vessel['id'])
                await context.wait_for_timeout(3000) # 等待資料刷新
                
                # 抓取表格數據
                cells = await context.query_selector_all('tr.ui-widget-content >> td')
                
                if len(cells) >= 12:
                    date_val = await cells[2].inner_text()
                    lat_val = await cells[4].inner_text()
                    lon_val = await cells[5].inner_text()
                    weight_val = await cells[11].inner_text()
                    
                    final_report.append({
                        "vessel": vessel['name'], "date": date_val, 
                        "lat": lat_val, "lon": lon_val, "weight": weight_val
                    })
                    print(f"   📍 {lat_val}, {lon_val} | 🐟 {weight_val} kg")

            print("\n--- 📊 最終回報彙整 ---")
            for r in final_report:
                print(f"[{r['vessel']}] 日期:{r['date']} 座標:({r['lat']}, {r['lon']}) 漁獲:{r['weight']}kg")

        except Exception as e:
            print(f"❌ 執行出錯: {e}")
            # 這裡可以增加截圖功能，方便除錯
            await context.screenshot(path="error_debug.png")
            print("📸 已儲存錯誤截圖至 error_debug.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())
