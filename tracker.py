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
        context = await browser.new_context()
        page = await context.new_page()

        # 前往 OFDC 登入頁面 (請依實際網址調整，例如 efish.ofdc.org.tw)
        print("🔗 正在前往 OFDC 系統...")
        await page.goto("https://efish.ofdc.org.tw/vms/login") 

        # 使用您指定的變數名稱進行登入
        try:
            await page.fill('input[name="username"]', os.environ['OFDC_USER'])
            await page.fill('input[name="password"]', os.environ['OFDC_PASS'])
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")
            print("✅ 登入成功")
        except Exception as e:
            print(f"❌ 登入失敗，請檢查帳密或網頁結構: {e}")
            return

        for vessel in VESSELS:
            try:
                # 這裡的搜尋邏輯需視 OFDC 介面而定
                # 假設搜尋框 ID 為 #search_vessel
                await page.fill('#search_vessel', vessel['id'])
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(3000) # 等待 3 秒載入數據

                # 擷取漁獲數據 (範例 Selector)
                # 您可以提供正確的網頁元素位置，我可以幫您寫得更精準
                catch_data = await page.inner_text('.vessel-catch-info')
                
                print(f"🚢 {vessel['name']} 數據攫取成功: {catch_data[:50]}...")
            except Exception as e:
                print(f"⚠️ 無法取得 {vessel['name']} ({vessel['id']}) 的資料: {e}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())
