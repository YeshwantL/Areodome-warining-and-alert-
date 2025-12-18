import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_password_change():
    print("Testing Password Change...")

    # 1. Login as Admin
    print("1. Logging in as mwo_admin with default password...")
    payload = {
        "username": "mwo_admin",
        "password": "admin123"
    }
    try:
        response = requests.post(f"{BASE_URL}/token", data=payload)
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to server. Is it running?")
        sys.exit(1)

    if response.status_code != 200:
        print(f"Failed to login: {response.text}")
        sys.exit(1)
    
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful.")

    # 2. Change Password
    print("2. Changing password to 'newpass123'...")
    change_payload = {
        "old_password": "admin123",
        "new_password": "newpass123"
    }
    response = requests.post(f"{BASE_URL}/change-password", json=change_payload, headers=headers)
    if response.status_code != 200:
        print(f"Failed to change password: {response.text}")
        sys.exit(1)
    print("Password changed successfully.")

    # 3. Verify Login with New Password
    print("3. Verifying login with new password...")
    payload["password"] = "newpass123"
    response = requests.post(f"{BASE_URL}/token", data=payload)
    if response.status_code != 200:
        print(f"Failed to login with new password: {response.text}")
        sys.exit(1)
    print("Login with new password successful.")

    # 4. Revert Password (Cleanup)
    print("4. Reverting password to default 'admin123'...")
    # Need new token? usage of old token might still be valid depending on implementation (JWTs are stateless typically, unless we blacklist)
    # But let's use the new token obtained in step 3 to be continuous.
    new_token = response.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    revert_payload = {
        "old_password": "newpass123",
        "new_password": "admin123"
    }
    response = requests.post(f"{BASE_URL}/change-password", json=revert_payload, headers=new_headers)
    if response.status_code != 200:
        print(f"Failed to revert password: {response.text}")
        sys.exit(1)
    print("Password reverted successfully.")

    print("\nALL TESTS PASSED.")

if __name__ == "__main__":
    test_password_change()
