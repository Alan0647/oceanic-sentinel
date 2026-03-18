import os
import asyncio
import time
from playwright.async_api import async_playwright

# 您要追蹤的六艘漁船
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
        
        target_url = "https://www.ofdc.org.tw:8181/elogbookquery/content/index.xhtml"
        print(f"🚀 啟動自動化程序 | 目標：OFDC 8181 系統")
        print(f"⏰ 執行時間：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 50)

        try:
            # 1. 前往網址與登入
            await context.goto(target_url, timeout=60000, wait_until="networkidle")
            await context.fill('input[id="j_idt8:使用者名稱"]', os.environ['OFDC_USER'])
            await context.fill('input[id="j_idt8:密碼"]', os.environ['OFDC_PASS'])
            await context.keyboard.press("Enter")
            
            # 等待登入後的選單出現
            await context.wait_for_selector('select[id="toolForm:ctnoSelectMenu"]', timeout=30000)
            print("🔐 登入驗證成功，開始讀取船隻數據...")

            final_results = []
            for vessel in VESSELS:
                print(f"🚢 讀取中：{vessel['name']} ({vessel['id']})")
                
                # 切換船隻選單
                await context.select_option('select[id="toolForm:ctnoSelectMenu"]', vessel['id'])
                await context.wait_for_timeout(3000) # 等待資料刷新
                
                # 抓取表格中最新的一筆數據列
                cells = await context.query_selector_all('tr.ui-widget-content >> td')
                
                if len(cells) >= 12:
                    data = {
                        "name": vessel['name'],
                        "date": await cells[2].inner_text(),
                        "lat": await cells[4].inner_text(),
                        "lon": await cells[5].inner_text(),
                        "weight": await cells[11].inner_text(),
                        "status": await cells[20].inner_text()
                    }
                    final_results.append(data)
                    print(f"   ✅ 成功：日期 {data['date']} | 座標 ({data['lat']}, {data['lon']}) | 漁獲 {data['weight']} kg")
                else:
                    print(f"   ⚠️ 警告：該船隻今日尚無回報數據。")

            # 3. 輸出美化後的總結報告到 GitHub Log
            print("\n" + "="*50)
            print(f"📊 昱友/信隆 艦隊動態彙報 ({time.strftime('%Y-%m-%d')})")
            print("="*50)
            print(f"{'船名':<10} | {'資料日期':<12} | {'座標 (Lat, Lon)':<20} | {'漁獲 (kg)':<8}")
            print("-"*50)
            for r in final_results:
                pos = f"{r['lat']}, {r['lon']}"
                print(f"{r['name']:<10} | {r['date']:<12} | {pos:<20} | {r['weight']:<8}")
            print("="*50)

        except Exception as e:
            print(f"❌ 執行過程中發生錯誤: {e}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())
