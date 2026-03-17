import requests
import json
import os
from datetime import datetime

# --- 配置區 ---
# 如果您申請到了 GFW Token，請填在這裡，或者設為 GitHub Secret
GFW_TOKEN = os.getenv('GFW_TOKEN', 'YOUR_TOKEN_HERE') 

# 您的核心船隊資訊 (加入 MMSI 號碼會更精準，若無則用名稱搜尋)
MY_FLEET_CONFIG = [
    {"name": "YUYO 668", "id": "昱友668"},
    {"name": "SHIN LONG 168", "id": "信隆168"},
    {"name": "NF YUYO 1", "id": "NF YUYO 1"},
    {"name": "NF YUYO 6", "id": "NF YUYO 6"}
]

def fetch_gfw_vessel_data():
    """嘗試從 Global Fishing Watch 抓取真實船位"""
    if GFW_TOKEN == 'YOUR_TOKEN_HERE':
        print("尚未設定 GFW_TOKEN，將使用模擬座標。")
        return [
            {"name": "YUYO 668", "lat": -5.2, "lng": 55.4, "status": "模擬數據"},
            {"name": "SHIN LONG 168", "lat": -3.5, "lng": 60.1, "status": "模擬數據"}
        ]

    headers = {'Authorization': f'Bearer {GFW_TOKEN}'}
    real_vessels = []
    
    for ship in MY_FLEET_CONFIG:
        try:
            # 搜尋該船隻的最新位置
            search_url = f"https://gateway.globalfishingwatch.org/v2/vessels/search?query={ship['name']}"
            res = requests.get(search_url, headers=headers).json()
            
            if res.get('entries'):
                vessel_id = res['entries'][0]['id']
                # 取得該 ID 的最新位置
                pos_url = f"https://gateway.globalfishingwatch.org/v2/vessels/{vessel_id}/last-position"
                pos_res = requests.get(pos_url, headers=headers).json()
                
                real_vessels.append({
                    "name": ship['name'],
                    "lat": pos_res['lat'],
                    "lng": pos_res['lon'],
                    "status": "真實更新"
                })
        except:
            continue
            
    return real_vessels if real_vessels else [{"name": "系統搜尋中", "lat": 0, "lng": 0, "status": "等待數據"}]

# --- 原有的匯率、魚情、油價抓取邏輯不變，僅在 main 函數中調用上述函數 ---
# (此處省略重複的 fetch_tuna_data 等，請保留您原本 scraper.py 裡的其餘部分)

def main():
    # ... 原有的讀取 data.json 邏輯 ...
    
    # 更新船隊位置：切換為真實抓取
    current_vessels = fetch_gfw_vessel_data()
    
    for v in current_vessels:
        name = v['name']
        if name not in all_data['vessels']: all_data['vessels'][name] = []
        all_data['vessels'][name].append({
            "lat": v['lat'], "lng": v['lng'], "time": datetime.now().strftime("%m/%d %H:%M"), "status": v['status']
        })
        all_data['vessels'][name] = all_data['vessels'][name][-144:]
        
    # ... 原有的存檔邏輯 ...

if __name__ == "__main__":
    main()
