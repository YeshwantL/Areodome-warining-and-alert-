import requests
import sys
import time

BASE_URL = "http://127.0.0.1:8000"

def test_admin_reply():
    print("Testing Admin Reply...")

    # 1. Login as Regional
    print("1. Logging in as Regional (vasd)...")
    reg_payload = {"username": "vasd@gmail.com", "password": "Airport@123"}
    try:
        response = requests.post(f"{BASE_URL}/token", data=reg_payload)
    except Exception:
        print("Server not running?")
        sys.exit(1)
        
    if response.status_code != 200:
        print("Failed to login regional")
        print(response.text)
        sys.exit(1)
    
    reg_token = response.json()["access_token"]
    reg_headers = {"Authorization": f"Bearer {reg_token}"}
    
    # 2. Create Alert
    print("2. Creating Alert...")
    alert_payload = {
        "type": "Wind",
        "content": {
            "airport": "VASD",
            "speed": 10,
            "direction": 100,
            "time": "1000",
            "seq": "99"
        }
    }
    response = requests.post(f"{BASE_URL}/alerts/", json=alert_payload, headers=reg_headers)
    if response.status_code != 200:
        print("Failed to create alert")
        print(response.text)
        sys.exit(1)
    
    alert_id = response.json()["id"]
    print(f"Alert Created (ID: {alert_id})")
    
    # 3. Login as Admin
    print("3. Logging in as Admin...")
    admin_payload = {"username": "mwo_admin", "password": "admin123"}
    response = requests.post(f"{BASE_URL}/token", data=admin_payload)
    if response.status_code != 200:
        print("Failed to login admin")
        sys.exit(1)
        
    admin_token = response.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    # 4. Reply to Alert
    print(f"4. Replying to Alert {alert_id}...")
    reply_text = "Received. Validated."
    response = requests.post(f"{BASE_URL}/alerts/{alert_id}/reply?reply_text={reply_text}", headers=admin_headers)
    
    if response.status_code != 200:
        print(f"Failed to reply: {response.text}")
        sys.exit(1)
        
    updated_alert = response.json()
    if updated_alert["admin_reply"] == reply_text:
        print("SUCCESS: Reply saved correctly.")
    else:
        print(f"FAILURE: Expected '{reply_text}', got '{updated_alert.get('admin_reply')}'")
        sys.exit(1)
        
    # 5. Verify User sees reply
    print("5. Verifying User sees reply...")
    response = requests.get(f"{BASE_URL}/alerts/active", headers=reg_headers)
    alerts = response.json()
    my_alert = next((a for a in alerts if a['id'] == alert_id), None)
    
    if my_alert and my_alert["admin_reply"] == reply_text:
        print("SUCCESS: User sees the reply.")
    else:
        print("FAILURE: User does not see the reply correctly.")
        sys.exit(1)
        
    print("\nALL TESTS PASSED.")

if __name__ == "__main__":
    test_admin_reply()
