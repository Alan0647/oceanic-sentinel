import requests
import json
import os
import time
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- 1. 核心配置 ---
# 從 GitHub Secrets 讀取 Token
GFW_TOKEN = os.getenv('GFW_TOKEN')

# 魚種配置 (來源：OBIS 海洋生物數據庫)
TUNA_SPECIES = {
    "Thunnus obesus": "大目鮪 (Bigeye)",
    "Thunnus albacares": "黃鰭鮪 (Yellowfin)",
    "Thunnus alalunga": "長鰭鮪 (Albacore)"
}

# 港口 MGO 油價 (USD) - 建議每週一根據您的油價週報手動更新此處數字
PORT_BUNKER_PRICES = {
    "高雄 (Kaohsiung)": {"coords": [22.61, 120.29], "mgo": "745", "trend": "↓"},
    "釜山 (Busan)": {"coords": [35.10, 129.04], "mgo": "762", "trend": "↑"},
    "新加坡 (Singapore)": {"coords": [1.28, 103.85], "mgo": "728", "trend": "→"},
    "拉斯帕爾馬斯 (Las Palmas)": {"coords": [28.12, -15.43], "mgo": "815", "trend": "↓"}
}

# 您提供的四組核心船隊 MMSI
MY_FLEET_MMSI = [
    "664070000", # 昱友 668
    "664063000", # 信隆 168
    "416004859", # NF YUYO 1
    "416005584"  # NF YUYO 6
]

# --- 2. 工具函數：建立強韌的連線環境 ---

def get_robust_session():
    """建立具備自動重試與官方規格標頭的連線會話"""
    session = requests.Session()
    # 設定重試邏輯：失敗時自動重試 5 次，且間隔時間遞增 (1s, 2s, 4s...)
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('https://', adapter)
    
    # 模仿官方 SDK 與瀏覽器的 Header，增加穿透率
    session.headers.update({
        'Authorization': f'Bearer {GFW_TOKEN}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Cache-Control': 'no-cache'
    })
    return session

# --- 3. 數據抓取模組 ---

def get_finance_data():
    """抓取匯率並計算 JPY/TWD 到四位小數"""
    try:
        res = requests.get("https://open.er-api.com/v6/latest/USD", timeout=15).json()
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
        print("⚠️ 未偵測到 GFW_TOKEN，切換為模擬模式。")
        return [{"name": f"模擬船-{m}", "lat": -5.0, "lng": 55.0+(i*2), "status": "模擬數據"} for i, m in enumerate(MY_FLEET_MMSI)]
    
    session = get_robust_session()
    vessel_results = []
    
    for mmsi in MY_FLEET_MMSI:
        try:
            time.sleep(1.5) # 避免請求過快
            # A. 搜尋船隻資訊
            search_url = f"https://gateway.globalfishingwatch.org/v2/vessels/search?mmsi={mmsi}"
            res = session.get(search_url, timeout=30)
            res.raise_for_status()
            search_data = res.json()
            
            if search_data.get('entries'):
                v = search_data['entries'][0]
                v_id = v['id']
                # 反查名稱：優先取船名，若無則用 MMSI
                ais_name = v.get('shipname') or v.get('prettyName') or f"MMSI:{mmsi}"
                
                # B. 獲取最後位置
                pos_url = f"https://gateway.globalfishingwatch.org/v2/vessels/{v_id}/last-position"
                pos_res = session.get(pos_url, timeout=30).json()
                
                vessel_results.append({
                    "name": ais_name,
                    "lat": pos_res['lat'],
                    "lng": pos_res['lon'],
                    "status": "真實更新"
                })
                print(f"✅ 定位成功：{ais_name} ({mmsi})")
            else:
                print(f"⚠️ MMSI {mmsi} 查無公開 AIS 訊號")
        except Exception as e:
            print(f"❌ MMSI {mmsi} 通訊失敗: {type(e).__name__}")
            continue
            
    return vessel_results

def fetch_tuna_data():
    """抓取全球魚情 (OBIS)"""
    tuna_points = []
    for sci_name, c_name in TUNA_SPECIES.items():
        try:
            url = f"https://api.obis.org/v3/occurrence?scientificname={sci_name}&size=15"
            res = requests.get(url, timeout=15).json()
            for r in res.get('results', []):
                lat, lng = r.get('decimalLatitude'), r.get('decimalLongitude')
                if lat and lng:
                    tuna_points.append({"type": "tuna", "name": c_name, "lat": lat, "lng": lng})
        except: continue
    return tuna_points

# --- 4. 主程序 ---

def main():
    file_path = 'data.json'
    
    # 載入歷史資料 (保留航跡)
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                all_data = json.load(f)
        except:
            all_data = {"vessels": {}, "tuna": [], "ports": [], "finance": {}}
    else:
        all_data = {"vessels": {}, "tuna": [], "ports": [], "finance": {}}

    # 更新金融與環境數據
    all_data['finance'] = get_finance_data() or all_data.get('finance')
    all_data['tuna'] = fetch_tuna_data()
    all_data['ports'] = [
        {"name": n, "lat": i['coords'][0], "lng": i['coords'][1], "mgo": i['mgo'], "trend": i['trend']}
        for n, i in PORT_BUNKER_PRICES.items()
    ]

    # 更新真實船隊與 72 小時航跡 (144 個點)
    real_vessels = fetch_real_vessel_positions()
    for v in real_vessels:
        name = v['name']
        if name not in all_data['vessels']:
            all_data['vessels'][name] = []
        
        all_data['vessels'][name].append({
            "lat": v['lat'], "lng": v['lng'],
            "time": datetime.now().strftime("%m/%d %H:%M"),
            "status": v['status']
        })
        all_data['vessels'][name] = all_data['vessels'][name][-144:]

    all_data['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 存檔
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print(f"--- 數據同步完成：{all_data['last_update']} ---")

if __name__ == "__main__":
    main()
