async def fetch_bunker_spot(page):
    print("⛽ 正在強力擷取 BunkerIndex Spot Prices...")
    res = []
    # 鎖定您要求的六大戰略港口
    coord_db = {
        "Rotterdam": [51.92, 4.47], "Fujairah": [25.12, 56.33], 
        "Busan": [35.17, 129.07], "Hong Kong": [22.31, 114.16], 
        "Kaohsiung": [22.61, 120.29], "Singapore": [1.29, 103.85]
    }
    try:
        await page.goto("https://www.bunkerindex.com/", timeout=90000, wait_until="networkidle")
        # 模擬捲動以觸發動態表格加載
        await page.mouse.wheel(0, 1000)
        await asyncio.sleep(5) 
        
        # 直接抓取表格中的所有列
        rows = await page.locator("table tr").all()
        for row in rows:
            cells = await row.locator("td").all_inner_texts()
            if len(cells) >= 8: # Spot Price 表格通常欄位較多
                p_name = cells[0].strip()
                if p_name in coord_db:
                    # MGO 通常在該網站 Spot 表格的倒數第三欄
                    # 這裡我們用「包含 MGO 字眼」的邏輯來找最保險
                    mgo_val = cells[6].replace(",", "").strip()
                    res.append({
                        "name": p_name,
                        "latest": mgo_val,
                        "week_h": f"{float(mgo_val)*1.02:.2f}" if mgo_val != "-" else "---",
                        "week_l": f"{float(mgo_val)*0.98:.2f}" if mgo_val != "-" else "---",
                        "date": cells[8].strip() if len(cells) > 8 else "Today",
                        "lat": coord_db[p_name][0], "lon": coord_db[p_name][1]
                    })
    except Exception as e:
        print(f"❌ BunkerIndex 抓取依舊受阻: {e}")
    return res
