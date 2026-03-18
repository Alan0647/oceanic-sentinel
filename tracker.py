import os, json, gspread, time
from google.oauth2.service_account import Credentials

# 設定追蹤清單
VESSELS = [
    {"name": "信隆168", "id": "61436"},
    {"name": "昱友668", "id": "61508"},
    {"name": "信友16", "id": "70157"},
    {"name": "信隆216", "id": "70296"},
    {"name": "高欣6", "id": "70506"},
    {"name": "隆昌3", "id": "70554"}
]

def get_vessel_data(vessel_id):
    # 此處應插入特定網站的爬蟲邏輯 (範例為模擬數據)
    # 建議針對 OPRT 或 AIS 系統進行 API 或 HTML 解析
    return {
        "lat": "22.627", "lon": "120.265", 
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "In Transit"
    }

def main():
    # 認證 Google Sheets
    scope = ['https://www.googleapis.com/auth/spreadsheets']
    creds_dict = json.loads(os.environ['GS_CREDENTIALS'])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    
    sheet = client.open_by_key(os.environ['SHEET_ID']).worksheet("Data")
    
    for vessel in VESSELS:
        data = get_vessel_data(vessel['id'])
        row = [time.strftime("%Y-%m-%d"), vessel['name'], vessel['id'], 
               data['lat'], data['lon'], data['status'], "Auto-GitHub"]
        sheet.append_row(row)
        print(f"Updated {vessel['name']}")

if __name__ == "__main__":
    main()
