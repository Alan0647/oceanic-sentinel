import requests
import json
import os
from datetime import datetime

# --- 配置區 ---
# 獲取 GitHub Secrets 中的 GFW 鑰匙 (請參考下方教學設定)
GFW_TOKEN = os.getenv('GFW_TOKEN', 'YOUR_TOKEN_HERE') 

TUNA_SPECIES = {
    "Thunnus obesus": "大目鮪 (Bigeye)",
    "Thunnus albacares": "黃鰭鮪 (Yellowfin)",
    "Thunnus alalunga": "長鰭鮪 (Albacore)"
}

# 港口油價 (USD)
PORT_BUNKER_PRICES = {
    "高雄 (Kaohsiung)": {"coords": [22.6, 120.3], "mgo": "745", "trend": "↓"},
    "釜山 (Busan)": {"coords": [35.1, 129.0], "mgo": "762", "trend": "↑"},
    "新加坡 (Singapore)": {"coords": [1.3, 103.8], "mgo": "728", "trend": "→"},
    "拉斯帕爾馬斯 (Las Palmas)": {"coords": [28.1, -15.4], "mgo": "815", "trend": "↓"}
}

# 船隊名單
MY_FLEET_CONFIG = [
    {"name": "YUYO 668", "id": "YUYO 668"},
    {"name": "SHIN LONG 168", "id": "SHIN LONG 168"},
    {"name": "NF YUYO 1", "id": "NF YUYO 1"},
    {"name": "NF YUYO 6", "id": "NF YUYO 6"}
]

def get_finance_data():
    """抓取即時匯率並精確計算 JPY/TWD 到四位小數"""
    try:
        res = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10).json()
        usd_jpy = res['rates']['JPY']
        usd_twd = res['rates']['TWD']
        # 精確計算：台幣/日圓
        jpy_twd = usd_twd / usd_jpy
        return {
            "USD_JPY": round(usd_jpy, 2),
            "JPY_TWD": round(jpy_twd, 4), # 調整至小數點後四位
            "USD_TWD": round(usd_twd, 2)
        }
    except: return None

def fetch_vessel_positions():
    """從 GFW 抓取真實船位，若無 Token 則回傳模擬點"""
    if GFW_TOKEN == 'YOUR_TOKEN_HERE':
        return [{"name": f["name"], "lat": -5.0, "lng": 55.0, "status": "模擬數據"} for f in MY_FLEET_CONFIG]
    
    headers = {'Authorization': f'Bearer {GFW_TOKEN}'}
    real_data = []
    for ship in MY_FLEET_CONFIG:
        try:
            search = requests.get(f"https://gateway.globalfishingwatch.org/v2/vessels/search?query={ship['name']}", headers=headers).json()
            if search.get('entries'):
                v_id = search['entries'][0]['id']
                pos = requests.get(f"https://gateway.globalfishingwatch.org/v2/vessels/{v_id}/last-position", headers=headers).json()
                real_data.append({"name": ship['name'], "lat": pos['lat'], "lng": pos['lon'], "status": "真實更新"})
        except: continue
    return real_data if real_data else []

# ... (其餘 fetch_tuna_data 等邏輯維持不變) ...

def main():
    file_path = 'data.json'
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f: all_data = json.load(f)
    else:
        all_data = {"vessels": {}, "tuna": [], "ports": [], "finance": {}}

    all_data['finance'] = get_finance_data()
    
    # 更新真實船位
    current_vessels = fetch_vessel_positions()
    for v in current_vessels:
        name = v['name']
        if name not in all_data['vessels']: all_data['vessels'][name] = []
        all_data['vessels'][name].append({"lat": v['lat'], "lng": v['lng'], "time": datetime.now().strftime("%m/%d %H:%M"), "status": v['status']})
        all_data['vessels'][name] = all_data['vessels'][name][-144:]

    all_data['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
