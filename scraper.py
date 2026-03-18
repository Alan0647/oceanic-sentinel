import requests
import json
import os
from datetime import datetime

# --- 1. 配置區 ---
# 這裡會自動從 GitHub Secrets 抓取您剛設定的 GFW_TOKEN
GFW_TOKEN = os.getenv('GFW_TOKEN')

TUNA_SPECIES = {
    "Thunnus obesus": "大目鮪 (Bigeye)",
    "Thunnus albacares": "黃鰭鮪 (Yellowfin)",
    "Thunnus alalunga": "長鰭鮪 (Albacore)"
}

# 港口油價 (USD) - 可根據您的週報手動更新數字
PORT_BUNKER_PRICES = {
    "高雄 (Kaohsiung)": {"coords": [22.6, 120.3], "mgo": "745", "trend": "↓"},
    "釜山 (Busan)": {"coords": [35.1, 129.0], "mgo": "762", "trend": "↑"},
    "新加坡 (Singapore)": {"coords": [1.3, 103.8], "mgo": "728", "trend": "→"},
    "拉斯帕爾馬斯 (Las Palmas)": {"coords": [28.1, -15.4], "mgo": "815", "trend": "↓"}
}

# 船隊名單 (請確保名稱與 GFW 上的名稱一致)
MY_FLEET_CONFIG = [
    {"name": "YUYO 668"},
    {"name": "SHIN LONG 168"},
    {"name": "NF YUYO 1"},
    {"name": "NF YUYO 6"}
]

# --- 2. 數據抓取功能 ---

def get_finance_data():
    """抓取即時匯率並精確計算 JPY/TWD 到四位小數"""
    try:
        res = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10).json()
        usd_jpy = res['rates']['JPY']
        usd_twd = res['rates']['TWD']
        return {
            "USD_JPY": round(usd_jpy, 2),
            "JPY_TWD": round(usd_twd / usd_jpy, 4), # 四位小數精準度
            "USD_TWD": round(usd_twd, 2)
        }
    except: return None

def fetch_real_vessel_positions():
    """從 GFW 抓取真實船位，並加入詳細診斷紀錄"""
    if not GFW_TOKEN or GFW_TOKEN == "YOUR_TOKEN_HERE":
        print("❌ 錯誤：找不到 GFW_TOKEN。請檢查 GitHub Secrets 設定。")
        return [{"name": f["name"], "lat": -5.0, "lng": 55.0, "status": "Token缺失-模擬數據"} for f in MY_FLEET_CONFIG]
    
    headers = {'Authorization': f'Bearer {GFW_TOKEN}'}
    real_data = []
    
    for ship in MY_FLEET_CONFIG:
        try:
            # 嘗試搜尋船隻
            search_url = f"https://gateway.globalfishingwatch.org/v2/vessels/search?query={ship['name']}"
            search_res = requests.get(search_url, headers=headers)
            
            if search_res.status_code == 401:
                print("❌ 錯誤：Token 失效或無權限 (401)。請重新申請 Token。")
                return [{"name": ship['name'], "lat": 0, "lng": 0, "status": "Token失效"}]

            search = search_res.json()
            if search.get('entries') and len(search['entries']) > 0:
                v_id = search['entries'][0]['id']
                pos_url = f"https://gateway.globalfishingwatch.org/v2/vessels/{v_id}/last-position"
                pos = requests.get(pos_url, headers=headers).json()
                
                real_data.append({
                    "name": ship['name'],
                    "lat": pos['lat'],
                    "lng": pos['lon'],
                    "status": "真實更新"
                })
                print(f"✅ 成功抓取：{ship['name']}")
            else:
                # 如果搜尋不到，回傳一個特殊狀態，方便我們在地圖上看到
                print(f"⚠️ 搜尋不到船隻：{ship['name']}，請確認名稱是否與 AIS 登記一致。")
                real_data.append({"name": ship['name'], "lat": -2.0, "lng": 60.0, "status": "搜尋不到AIS"})
        except Exception as e:
            print(f"❌ 抓取異常：{e}")
            continue
            
    return real_data

def fetch_tuna_data():
    """抓取魚群點位與環境潛力"""
    points = []
    for sci_name, c_name in TUNA_SPECIES.items():
        try:
            res = requests.get(f"https://api.obis.org/v3/occurrence?scientificname={sci_name}&size=20").json()
            for r in res.get('results', []):
                lat, lng = r.get('decimalLatitude'), r.get('decimalLongitude')
                if lat and lng:
                    points.append({"type": "tuna", "name": c_name, "lat": lat, "lng": lng, "date": r.get('eventDate')})
        except: continue
    return points

# --- 3. 主程序 ---

def main():
    file_path = 'data.json'
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f: all_data = json.load(f)
    else:
        all_data = {"vessels": {}, "tuna": [], "ports": [], "finance": {}}

    all_data['finance'] = get_finance_data()
    all_data['tuna'] = fetch_tuna_data()
    all_data['ports'] = [{"name": n, "lat": i['coords'][0], "lng": i['coords'][1], "mgo": i['mgo'], "trend": i['trend']} for n, i in PORT_BUNKER_PRICES.items()]

    # 更新真實船位並累計航跡
    current_vessels = fetch_real_vessel_positions()
    for v in current_vessels:
        name = v['name']
        if name not in all_data['vessels']: all_data['vessels'][name] = []
        all_data['vessels'][name].append({
            "lat": v['lat'], "lng": v['lng'], 
            "time": datetime.now().strftime("%m/%d %H:%M"), 
            "status": v['status']
        })
        all_data['vessels'][name] = all_data['vessels'][name][-144:]

    all_data['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
