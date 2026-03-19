import os
import asyncio
import json
import time
from playwright.async_api import async_playwright

# 追蹤船隻清單
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
    print(f"🔄 第 {attempt_count} 次嘗試連線...")
    
    # 1. 前往頁面
    await page.goto(target_url, timeout=60000, wait_until="networkidle")
    
    # 2. 執行登入
    await page.fill('input[id="j_idt8:使用者名稱"]', os.environ['OFDC_USER'])
    await page.fill('input[id="j_idt8:密碼"]', os.environ['OFDC_PASS'])
    await page.keyboard.press("Enter")
    
    # 3. 等待關鍵選單出現 (增加到 30 秒)
    # 如果 30 秒都還沒出現，代表這次登入失敗或網頁卡死，會觸發外層的重試
    print("⏳ 正在等待主頁面選單加載 (Timeout: 30s)...")
    await page.wait_for_selector('select[id="toolForm:ctnoSelectMenu"]', timeout=30000)
    print("✅ 進入系統成功！")

async def run_scraper():
    MAX_RETRIES = 5  # 最多嘗試 5 次
    final_results = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        success = False
        for i in range(1, MAX_RETRIES + 1):
            context = await browser.new_context(viewport={'width': 1280, 'height': 800})
            page = await context.new_page()
            
            try:
                await scrape_attempt(page, i)
                
                # 如果能執行到這裡，代表登入成功
                for vessel in VESSELS:
                    print(f"🚢 讀取：{vessel['name']}...")
                    await page.select_option('select[id="toolForm:ctnoSelectMenu"]', vessel['id'])
                    await page.wait_for_timeout(5000) # 給予足夠時間刷新數據
                    
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
                
                success = True
                break # 成功抓完資料，跳出重試迴圈
                
            except Exception as e:
                print(f"⚠️ 第 {i} 次嘗試失敗: {str(e)[:100]}")
                # 失敗時存一張截圖，方便您在 GitHub 上查看原因
                await page.screenshot(path=f"debug_attempt_{i}.png")
                await page.close()
                await context.close()
                if i < MAX_RETRIES:
                    print("🚀 等待 5 秒後進行下一次重試...")
                    await asyncio.sleep(5)
        
        await browser.close()
        
        # 最後將結果存入檔案
        if success and final_results:
            with open('data.json', 'w', encoding='utf-8') as f:
                json.dump(final_results, f, ensure_ascii=False, indent=4)
            print(f"🎉 全部任務完成！成功抓取 {len(final_results)} 艘船隻。")
        else:
            print("❌ 經過多次嘗試後依然無法獲取數據。")
            raise Exception("所有嘗試均已失敗。")

if __name__ == "__main__":
    asyncio.run(run_scraper())
