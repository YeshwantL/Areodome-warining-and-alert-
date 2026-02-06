import requests
import sys

BASE_URL = "http://localhost:8000"

def test_auth_flow():
    session = requests.Session()
    
    print("1. Access Dashboard without login...")
    r = session.get(f"{BASE_URL}/dashboard", allow_redirects=False)
    if r.status_code == 307: # Temporary Redirect
        redirect_url = r.headers.get("location")
        print(f"PASS: Redirected to {redirect_url}. Status: {r.status_code}")
    else:
        print(f"FAIL: Expected 307 Redirect, got {r.status_code}")
        # sys.exit(1) # Don't exit, keep trying

    print("\n2. Login...")
    login_data = {"username": "mwo_admin", "password": "admin123"} 
    # Login POST expects form data
    r = session.post(f"{BASE_URL}/auth/token", data=login_data)
    if r.status_code == 200:
        print("PASS: Login successful.")
        token = r.json().get("access_token")
        print(f"Token received: {token[:10]}...")
        
        # Check Cookies
        if "session" in session.cookies:
            print("PASS: Session cookie set.")
        else:
            print("FAIL: Session cookie NOT set.")
            
        print("\n3. Access Dashboard with session...")
        r = session.get(f"{BASE_URL}/dashboard")
        if r.status_code == 200:
             print("PASS: Dashboard accessed (200 OK).")
        else:
             print(f"FAIL: Dashboard access failed. Status: {r.status_code}")

        print("\n4. Logout...")
        r = session.get(f"{BASE_URL}/auth/logout", allow_redirects=False)
        if r.status_code == 302:
             print("PASS: Logout redirected.")
        else:
             print(f"FAIL: Logout returned {r.status_code}")

        print("\n5. Access Dashboard after logout...")
        r = session.get(f"{BASE_URL}/dashboard", allow_redirects=False)
        if r.status_code == 307 or r.status_code == 302:
             print(f"PASS: Redirected after logout. Status: {r.status_code}")
        else:
             print(f"FAIL: Still able to access dashboard? Status: {r.status_code}")

    else:
        print(f"FAIL: Login failed: {r.status_code} {r.text}")

if __name__ == "__main__":
    try:
        requests.get(BASE_URL)
        test_auth_flow()
    except Exception as e:
        print(f"Could not connect to {BASE_URL}: {e}")
