import requests
import json
import os
from datetime import datetime

# --- 1. 配置與參數設定 ---
# 鑰匙：從 GitHub Secrets 自動讀取
GFW_TOKEN = os.getenv('GFW_TOKEN')

# 魚種配置 (OBIS 數據源)
TUNA_SPECIES = {
    "Thunnus obesus": "大目鮪 (Bigeye)",
    "Thunnus albacares": "黃鰭鮪 (Yellowfin)",
    "Thunnus alalunga": "長鰭鮪 (Albacore)"
}

# 港口 MGO 油價設定 (請根據週報定期在此修改數字)
PORT_BUNKER_PRICES = {
    "高雄 (Kaohsiung)": {"coords": [22.6, 120.3], "mgo": "745", "trend": "↓"},
    "釜山 (Busan)": {"coords": [35.1, 129.0], "mgo": "762", "trend": "↑"},
    "新加坡 (Singapore)": {"coords": [1.3, 103.8], "mgo": "728", "trend": "→"},
    "拉斯帕爾馬斯 (Las Palmas)": {"coords": [28.1, -15.4], "mgo": "815", "trend": "↓"}
}

# 核心船隊 MMSI (您提供的身分證字號)
MY_FLEET_MMSI = [
    "664070000", # 昱友 668
    "664063000", # 信隆 168
    "416004859", # NF YUYO 1
    "416005584"  # NF YUYO 6
]

# --- 2. 數據抓取功能模組 ---

def get_finance_data():
    """抓取即時匯率並精確計算 JPY/TWD 到四位小數"""
    try:
        res = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10).json()
        usd_jpy = res['rates']['JPY']
        usd_twd = res['rates']['TWD']
        return {
            "USD_JPY": round(usd_jpy, 2),
            "JPY_TWD": round(usd_twd / usd_jpy, 4), # 四位小數精確度
            "USD_TWD": round(usd_twd, 2)
        }
    except Exception as e:
        print(f"匯率抓取異常: {e}")
        return None

def fetch_real_vessel_positions():
    """透過 MMSI 抓取真實船位並反查 AIS 船名"""
    if not GFW_TOKEN or GFW_TOKEN == "YOUR_TOKEN_HERE":
        print("⚠️ 未偵測到有效 GFW_TOKEN，切換至模擬模式。")
        return [{"name": f"模擬船隻-{m}", "lat": -5.0, "lng": 55.0 + (i*5), "status": "模擬數據"} for i, m in enumerate(MY_FLEET_MMSI)]
    
    headers = {'Authorization': f'Bearer {GFW_TOKEN}'}
    vessel_results = []
    
    for mmsi in MY_FLEET_MMSI:
        try:
            # A. 搜尋船隻資訊 (反查船名)
            search_url = f"https://gateway.globalfishingwatch.org/v2/vessels/search?mmsi={mmsi}"
            search_res = requests.get(search_url, headers=headers).json()
            
            if search_res.get('entries'):
                v_info = search_res['entries'][0]
                v_id = v_info['id']
                ais_name = v_info.get('shipname', f"MMSI:{mmsi}") # 取得 AIS 登記船名
                
                # B. 獲取最後位置
                pos_url = f"https://gateway.globalfishingwatch.org/v2/vessels/{v_id}/last-position"
                pos = requests.get(pos_url, headers=headers).json()
                
                vessel_results.append({
                    "name": ais_name,
                    "lat": pos['lat'],
                    "lng": pos['lon'],
                    "status": "真實更新"
                })
                print(f"✅ 成功定位：{ais_name} ({mmsi})")
            else:
                print(f"⚠️ MMSI {mmsi} 搜尋不到公開 AIS 訊號。")
        except Exception as e:
            print(f"❌ MMSI {mmsi} 抓取出錯: {e}")
            continue
    return vessel_results

def fetch_tuna_data():
    """抓取全球魚情點位 (OBIS)"""
    tuna_points = []
    for sci_name, c_name in TUNA_SPECIES.items():
        try:
            url = f"https://api.obis.org/v3/occurrence?scientificname={sci_name}&size=15"
            res = requests.get(url, timeout=10).json()
            for r in res.get('results', []):
                lat, lng = r.get('decimalLatitude'), r.get('decimalLongitude')
                if lat and lng:
                    tuna_points.append({
                        "type": "tuna", "name": c_name, "lat": lat, "lng": lng, "date": r.get('eventDate')
                    })
        except: continue
    return tuna_points

# --- 3. 主程序邏輯 ---

def main():
    file_path = 'data.json'
    
    # 讀取舊資料 (為了保留航跡歷史)
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
    else:
        all_data = {"vessels": {}, "tuna": [], "ports": [], "finance": {}}

    # 更新 1: 金融匯率
    rates = get_finance_data()
    if rates: all_data['finance'] = rates

    # 更新 2: 魚情數據
    all_data['tuna'] = fetch_tuna_data()

    # 更新 3: 港口油價
    all_data['ports'] = [
        {"name": n, "lat": i['coords'][0], "lng": i['coords'][1], "mgo": i['mgo'], "trend": i['trend']}
        for n, i in PORT_BUNKER_PRICES.items()
    ]

    # 更新 4: 船隊真實位置與 72h 航跡累計
    real_vessels = fetch_real_vessel_positions()
    for v in real_vessels:
        name = v['name']
        if name not in all_data['vessels']:
            all_data['vessels'][name] = []
        
        # 加入新點位
        all_data['vessels'][name].append({
            "lat": v['lat'],
            "lng": v['lng'],
            "time": datetime.now().strftime("%m/%d %H:%M"),
            "status": v['status']
        })
        
        # 限制歷史長度 (144 個點 = 72 小時)
        all_data['vessels'][name] = all_data['vessels'][name][-144:]

    # 更新 5: 標註最後更新時間
    all_data['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 寫入檔案
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print(f"--- 數據更新完成於 {all_data['last_update']} ---")

if __name__ == "__main__":
    main()
