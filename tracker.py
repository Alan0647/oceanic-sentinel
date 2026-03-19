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

async def run_scraper():
    async with async_playwright() as p:
        # 啟動瀏覽器
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()
        
        target_url = "https://www.ofdc.org.tw:8181/elogbookquery/content/index.xhtml"
        print(f"🔗 正在前往 OFDC 系統...")

        try:
            # 1. 前往頁面
            await page.goto(target_url, timeout=60000)
            
            # 2. 登入 (使用您提供的正確 ID)
            await page.fill('input[id="j_idt8:使用者名稱"]', os.environ['OFDC_USER'])
            await page.fill('input[id="j_idt8:密碼"]', os.environ['OFDC_PASS'])
            print("🔑 帳密已輸入，嘗試登入...")
            await page.keyboard.press("Enter")
            
            # 3. 等待登入後的選單出現 (增加到 15 秒)
            print("⏳ 等待系統載入主介面...")
            try:
                await page.wait_for_selector('select[id="toolForm:ctnoSelectMenu"]', timeout=15000)
                print("✅ 登入成功，已進入監控主頁")
            except Exception:
                print("❌ 逾時：找不到船隻選單。正在存儲截圖以便檢查原因...")
                await page.screenshot(path="login_failed_debug.png")
                # 如果找不到選單，直接報錯結束，避免後面產生空的 json
                raise Exception("無法定位到船隻選單，可能是登入失敗或網頁加載太慢。")

            final_results = []
            for vessel in VESSELS:
                print(f"🚢 讀取：{vessel['name']}...")
                await page.select_option('select[id="toolForm:ctnoSelectMenu"]', vessel['id'])
                
                # 等待表格更新數據 (增加至 5 秒)
                await page.wait_for_timeout(5000) 
                
                cells = await page.query_selector_all('tr.ui-widget-content >> td')
                
                if len(cells) >= 12:
                    final_results.append({
                        "name": vessel['name'],
                        "id": vessel['id'],
                        "date": await cells[2].inner_text(),
                        "lat": await cells[4].inner_text(),
                        "lon": await cells[5].inner_text(),
                        "weight": await cells[11].inner_text(),
                        "update_time": time.strftime('%Y-%m-%d %H:%M')
                    })
            
            # 只有在有抓到資料的情況下才寫入檔案
            if final_results:
                with open('data.json', 'w', encoding='utf-8') as f:
                    json.dump(final_results, f, ensure_ascii=False, indent=4)
                print(f"✅ 數據抓取完成，共 {len(final_results)} 艘船。")
            else:
                print("⚠️ 警告：抓取清單為空。")

        except Exception as e:
            print(f"❌ 執行出錯: {e}")
            # 確保失敗時也能留下紀錄
            await page.screenshot(path="error_summary.png")
            raise e # 拋出錯誤讓 GitHub Action 顯示失敗

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())
