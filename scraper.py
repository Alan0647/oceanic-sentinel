import requests
import json
import os
import time
from datetime import datetime

# --- 1. 配置與參數設定 ---
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
        res = requests.get("https://open.er-api.com/v6/latest/USD", timeout=15).json()
        usd_jpy = res['rates']['JPY']
        usd_twd = res['rates']['TWD']
        return {
            "USD_JPY": round(usd_jpy, 2),
            "JPY_TWD": round(usd_twd / usd_jpy, 4), 
            "USD_TWD": round(usd_twd, 2)
        }
    except Exception as e:
        print(f"匯率抓取異常: {e}")
        return None

def fetch_real_vessel_positions():
    """強化版：使用 Session 與偽裝 Header 避免 SSL 連線被伺服器拒絕"""
    if not GFW_TOKEN or GFW_TOKEN == "YOUR_TOKEN_HERE":
        print("⚠️ 未偵測到有效 GFW_TOKEN，切換至模擬模式。")
        return [{"name": f"模擬船-{m}", "lat": -5.0, "lng": 55.0 + (i*5), "status": "模擬數據"} for i, m in enumerate(MY_FLEET_MMSI)]
    
    # 建立穩定 Session 並偽裝成瀏覽器
    session = requests.Session()
    session.headers.update({
        'Authorization': f'Bearer {GFW_TOKEN}',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    vessel_results = []
    
    for mmsi in MY_FLEET_MMSI:
        # 增加一點隨機延遲，避免請求過快被封鎖
        time.sleep(1) 
        try:
            # A. 搜尋船隻資訊
            search_url = f"https://gateway.globalfishingwatch.org/v2/vessels/search?mmsi={mmsi}"
            response = session.get(search_url, timeout=20)
            response.raise_for_status()
            search_res = response.json()
            
            if search_res.get('entries'):
                v_info = search_res['entries'][0]
                v_id = v_info['id']
                ais_name = v_info.get('shipname', f"MMSI:{mmsi}")
                
                # B. 獲取最後位置
                pos_url = f"https://gateway.globalfishingwatch.org/v2/vessels/{v_id}/last-position"
                pos_res = session.get(pos_url, timeout=20).json()
                
                vessel_results.append({
                    "name": ais_name,
                    "lat": pos_res['lat'],
                    "lng": pos_res['lon'],
                    "status": "真實更新"
                })
                print(f"✅ 成功定位：{ais_name} ({mmsi})")
            else:
                print(f"⚠️ MMSI {mmsi} 在 GFW 數據庫中查無訊號")
        except Exception as e:
            # 如果還是失敗，我們會印出更明確的錯誤摘要
            error_msg = str(e).split(':', 1)[0]
            print(f"❌ MMSI {mmsi} 抓取失敗 ({error_msg})")
            continue
            
    return vessel_results

def fetch_tuna_data():
    """抓取全球魚情點位 (OBIS)"""
    tuna_points = []
    for sci_name, c_name in TUNA_SPECIES.items():
        try:
            url = f"https://api.obis.org/v3/occurrence?scientificname={sci_name}&size=15"
            res = requests.get(url, timeout=15).json()
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
    
    # 讀取舊資料
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                all_data = json.load(f)
        except:
            all_data = {"vessels": {}, "tuna": [], "ports": [], "finance": {}}
    else:
        all_data = {"vessels": {}, "tuna": [], "ports": [], "finance": {}}

    # 更新數據
    rates = get_finance_data()
    if rates: all_data['finance'] = rates

    all_data['tuna'] = fetch_tuna_data()

    all_data['ports'] = [
        {"name": n, "lat": i['coords'][0], "lng": i['coords'][1], "mgo": i['mgo'], "trend": i['trend']}
        for n, i in PORT_BUNKER_PRICES.items()
    ]

    # 真實位置追蹤
    real_vessels = fetch_real_vessel_positions()
    for v in real_vessels:
        name = v['name']
        if name not in all_data['vessels']:
            all_data['vessels'][name] = []
        
        all_data['vessels'][name].append({
            "lat": v['lat'],
            "lng": v['lng'],
            "time": datetime.now().strftime("%m/%d %H:%M"),
            "status": v['status']
        })
        # 保留航跡歷史
        all_data['vessels'][name] = all_data['vessels'][name][-144:]

    all_data['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 寫入檔案
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print(f"--- 數據同步完成：{all_data['last_update']} ---")

if __name__ == "__main__":
    main()
