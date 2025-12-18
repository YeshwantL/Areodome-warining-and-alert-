import requests

BASE_URL = "http://127.0.0.1:8000"

def test_flow():
    # 1. Login as Regional
    print("Logging in as Regional...")
    res = requests.post(f"{BASE_URL}/auth/token", data={"username": "vasd@gmail.com", "password": "newvasd123"})
    if res.status_code != 200:
        print(f"Login failed: {res.text}")
        return
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Alert
    print("Creating Alert...")
    alert_data = {
        "type": "Wind",
        "content": {
            "airport": "VASD",
            "seq": "101",
            "valid_from": "181200",
            "valid_to": "181400",
            "speed": "20",
            "gust": "30",
            "direction": "090",
            "w_type": "OBS",
            "change": "NC",
            "generated_text": "VASD 181200 AD WRNG 101 VALID 181200/181400 SFC WSPD 20KT MAX30 FROM 090 DEG OBS NC="
        }
    }
    res = requests.post(f"{BASE_URL}/alerts/", json=alert_data, headers=headers)
    if res.status_code != 200:
        print(f"Create alert failed: {res.text}")
        # return # Sometimes it fails if seq already exists or something, let's continue if it's 403/401
    else:
        print("Alert created successfully.")

    # 3. Login as Admin
    print("Logging in as Admin...")
    res = requests.post(f"{BASE_URL}/auth/token", data={"username": "mwo_admin", "password": "admin123"})
    if res.status_code != 200:
        print(f"Admin login failed: {res.text}")
        return
    admin_token = res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 4. Fetch Active Alerts
    print("Fetching Active Alerts as Admin...")
    res = requests.get(f"{BASE_URL}/alerts/active", headers=admin_headers)
    if res.status_code == 200:
        alerts = res.json()
        print(f"Found {len(alerts)} active alerts.")
        for a in alerts:
            print(f"- ID: {a['id']}, Type: {a['type']}, Text: {a['content'].get('generated_text')}")
    else:
        print(f"Fetch alerts failed: {res.status_code} {res.text}")

if __name__ == "__main__":
    test_flow()
