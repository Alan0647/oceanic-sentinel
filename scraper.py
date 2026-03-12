import requests
import json
import os
from datetime import datetime, timedelta

# --- 1. 配置與參數設定 ---
# 魚種配置
TUNA_SPECIES = {
    "Thunnus obesus": "大目鮪 (Bigeye)",
    "Thunnus albacares": "黃鰭鮪 (Yellowfin)",
    "Thunnus alalunga": "長鰭鮪 (Albacore)"
}

# 港口 MGO 油價設定 (建議每週一根據油價週報手動更新此處數字)
PORT_BUNKER_PRICES = {
    "高雄 (Kaohsiung)": {"coords": [22.6, 120.3], "mgo": "745", "trend": "↓"},
    "釜山 (Busan)": {"coords": [35.1, 129.0], "mgo": "762", "trend": "↑"},
    "新加坡 (Singapore)": {"coords": [1.3, 103.8], "mgo": "728", "trend": "→"},
    "拉斯帕爾馬斯 (Las Palmas)": {"coords": [28.1, -15.4], "mgo": "815", "trend": "↓"},
    "開普敦 (Cape Town)": {"coords": [-33.9, 18.4], "mgo": "842", "trend": "→"},
    "路易港 (Port Louis)": {"coords": [-20.1, 57.5], "mgo": "810", "trend": "↑"}
}

# 船隊名單 (模擬座標，若有 VMS API 可在此接入)
MY_FLEET = [
    {"name": "YUYO 668", "lat": -5.2, "lng": 55.4, "status": "作業中"},
    {"name": "SHIN LONG 168", "lat": -3.5, "lng": 60.1, "status": "航行中"},
    {"name": "NF YUYO 1", "lat": -1.2, "lng": 52.8, "status": "作業中"},
    {"name": "NF YUYO 6", "lat": -8.4, "lng": 58.2, "status": "作業中"}
]

# --- 2. 核心功能模組 ---

def get_exchange_rates():
    """抓取即時匯率 (USD/JPY, JPY/TWD, USD/TWD)"""
    try:
        res = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10).json()
        usd_jpy = res['rates']['JPY']
        usd_twd = res['rates']['TWD']
        return {
            "USD_JPY": round(usd_jpy, 2),
            "JPY_TWD": round(usd_twd / usd_jpy, 4),
            "USD_TWD": round(usd_twd, 2)
        }
    except Exception as e:
        print(f"匯率抓取失敗: {e}")
        return None

def get_sst_and_potential(lat, lng, species_name):
    """獲取座標水溫並計算漁獲潛力"""
    try:
        url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lng}&current=sea_surface_temperature"
        res = requests.get(url, timeout=5).json()
        temp = res.get('current', {}).get('sea_surface_temperature')
        
        # 簡單預測邏輯
        potential = "Low"
        if "大目" in species_name and 17 <= temp <= 22: potential = "High"
        elif "黃鰭" in species_name and 20 <= temp <= 28: potential = "High"
        elif "長鰭" in species_name and 15 <= temp <= 21: potential = "High"
        elif temp: potential = "Medium"
            
        return temp, potential
    except:
        return None, "Unknown"

def fetch_tuna_data():
    """從 OBIS 抓取魚情點位"""
    points = []
    for sci_name, c_name in TUNA_SPECIES.items():
        try:
            url = f"https://api.obis.org/v3/occurrence?scientificname={sci_name}&size=20"
            res = requests.get(url, timeout=10).json()
            for r in res.get('results', []):
                lat, lng = r.get('decimalLatitude'), r.get('decimalLongitude')
                if lat and lng:
                    temp, potential = get_sst_and_potential(lat, lng, c_name)
                    points.append({
                        "type": "tuna", "name": c_name, "lat": lat, "lng": lng,
                        "temp": temp, "potential": potential, "date": r.get('eventDate')
                    })
        except: continue
    return points

# --- 3. 主程序邏輯 ---

def main():
    file_path = 'data.json'
    
    # 讀取舊資料 (為了保留船跡歷史)
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
    else:
        all_data = {"vessels": {}, "tuna": [], "ports": [], "finance": {}}

    # 更新 1: 匯率
    rates = get_exchange_rates()
    if rates: all_data['finance'] = rates

    # 更新 2: 魚情點位
    all_data['tuna'] = fetch_tuna_data()

    # 更新 3: 港口油價
    all_data['ports'] = [
        {"name": n, "lat": i['coords'][0], "lng": i['coords'][1], "mgo": i['mgo'], "trend": i['trend']}
        for n, i in PORT_BUNKER_PRICES.items()
    ]

    # 更新 4: 船隊歷史航跡 (保留 72 小時)
    for v in MY_FLEET:
        name = v['name']
        if name not in all_data['vessels']: all_data['vessels'][name] = []
        
        all_data['vessels'][name].append({
            "lat": v['lat'], "lng": v['lng'], 
            "time": datetime.now().strftime("%m/%d %H:%M")
        })
        # 限制歷史長度 (144 個點 = 72 小時)
        all_data['vessels'][name] = all_data['vessels'][name][-144:]

    # 儲存最終結果
    all_data['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print("數據更新成功！")

if __name__ == "__main__":
    main()
