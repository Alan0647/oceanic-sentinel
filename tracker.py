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
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_page()
        target_url = "https://www.ofdc.org.tw:8181/elogbookquery/content/index.xhtml"
        
        try:
            await context.goto(target_url, timeout=60000)
            await context.fill('input[id="j_idt8:使用者名稱"]', os.environ['OFDC_USER'])
            await context.fill('input[id="j_idt8:密碼"]', os.environ['OFDC_PASS'])
            await context.keyboard.press("Enter")
            await context.wait_for_selector('select[id="toolForm:ctnoSelectMenu"]', timeout=3000)
            
            final_results = []
            for vessel in VESSELS:
                await context.select_option('select[id="toolForm:ctnoSelectMenu"]', vessel['id'])
                await context.wait_for_timeout(3000)
                cells = await context.query_selector_all('tr.ui-widget-content >> td')
                
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
            
            # 將結果存成 JSON 檔
            with open('data.json', 'w', encoding='utf-8') as f:
                json.dump(final_results, f, ensure_ascii=False, indent=4)
            print("✅ 數據已成功存入 data.json")

        except Exception as e:
            print(f"❌ 錯誤: {e}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())
