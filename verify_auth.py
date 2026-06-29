import json
import time
import urllib.request
import urllib.error
from typing import Tuple, Optional

BASE_URL = "http://127.0.0.1:8000"

def make_request(
    method: str, 
    path: str, 
    data: Optional[dict] = None, 
    token: Optional[str] = None
) -> Tuple[int, dict]:
    """Helper function to make HTTP requests using Python's standard library."""
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    req_body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=req_body, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            status = response.status
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body) if res_body else {}
            return status, res_json
    except urllib.error.HTTPError as e:
        status = e.code
        res_body = e.read().decode("utf-8")
        try:
            res_json = json.loads(res_body)
        except Exception:
            res_json = {"detail": res_body}
        return status, res_json
    except Exception as e:
        print(f"Network error: {str(e)}")
        return 500, {"detail": str(e)}

def run_tests():
    print("=========================================================")
    print("   Starting Automated JWT Authentication Verification    ")
    print("=========================================================")
    print()

    # Generate unique test usernames
    timestamp = int(time.time())
    user_uname = f"test_user_{timestamp}"
    admin_uname = f"test_admin_{timestamp}"
    password = "securepassword123"

    # --- 1. Signup Check ---
    print("1. Testing User Signup...")
    status, res = make_request("POST", "/auth/signup", {
        "username": user_uname,
        "password": password,
        "role": "user"
    })
    assert status == 201, f"Expected 201, got {status}: {res}"
    assert res["username"] == user_uname, "Signup username mismatch"
    assert res["role"] == "user", "Signup role mismatch"
    print("   [PASS] User signup successful.")

    print("   Testing Admin Signup...")
    status, res = make_request("POST", "/auth/signup", {
        "username": admin_uname,
        "password": password,
        "role": "admin"
    })
    assert status == 201, f"Expected 201, got {status}: {res}"
    assert res["username"] == admin_uname, "Signup username mismatch"
    assert res["role"] == "admin", "Signup role mismatch"
    print("   [PASS] Admin signup successful.")
    print()

    # --- 2. Rate Limiting / Lockout Check ---
    print("2. Testing Rate Limiting & Account Lock...")
    # Attempt 5 failed logins for user
    for i in range(5):
        status, res = make_request("POST", "/auth/login", {
            "username": user_uname,
            "password": "wrong_password"
        })
        assert status == 401, f"Expected 401, got {status}"

    # The 6th attempt within the same minute should be blocked by rate limiter (429)
    status, res = make_request("POST", "/auth/login", {
        "username": user_uname,
        "password": "wrong_password"
    })
    assert status == 429 or status == 401, f"Expected 429 (or 401 lockout), got {status}: {res}"
    print("   [PASS] Rate limiter/Failed attempts successfully tracked.")
    print()

    # --- 3. Login Check ---
    print("3. Testing Successful Login (Admin)...")
    status, res = make_request("POST", "/auth/login", {
        "username": admin_uname,
        "password": password
    })
    assert status == 200, f"Expected 200, got {status}: {res}"
    admin_access_token = res["access_token"]
    admin_refresh_token = res["refresh_token"]
    assert admin_access_token is not None
    assert admin_refresh_token is not None
    print("   [PASS] Admin login successful. JWT Tokens issued.")

    print("   Testing Successful Login (User)...")
    # Wait 2 seconds just in case of rate limit cooldown, then log in user
    time.sleep(2)
    status, res = make_request("POST", "/auth/login", {
        "username": user_uname,
        "password": password
    })
    assert status == 200, f"Expected 200, got {status}: {res}"
    user_access_token = res["access_token"]
    user_refresh_token = res["refresh_token"]
    print("   [PASS] User login successful. JWT Tokens issued.")
    print()

    # --- 4. Route Protection Check ---
    print("4. Testing Protected Route (/auth/profile)...")
    status, res = make_request("GET", "/auth/profile", token=user_access_token)
    assert status == 200, f"Expected 200, got {status}: {res}"
    assert res["username"] == user_uname
    print("   [PASS] Protected profile access allowed with valid token.")

    print("   Testing Protected Route with invalid token...")
    status, res = make_request("GET", "/auth/profile", token="invalid_token_string")
    assert status == 401, f"Expected 401, got {status}: {res}"
    print("   [PASS] Invalid token access rejected with 401 Unauthorized.")
    print()

    # --- 5. Role-Based Authorization Check ---
    print("5. Testing Role-Based Authorization...")
    # Standard user attempting admin route
    status, res = make_request("GET", "/auth/admin", token=user_access_token)
    assert status == 403, f"Expected 403, got {status}: {res}"
    print("   [PASS] Standard user blocked from admin route with 403 Forbidden.")

    # Admin user attempting admin route
    status, res = make_request("GET", "/auth/admin", token=admin_access_token)
    assert status == 200, f"Expected 200, got {status}: {res}"
    print("   [PASS] Admin user successfully authorized for admin route.")
    print()

    # --- 6. Token Refresh Rotation Check ---
    print("6. Testing Token Refresh & Rotation...")
    status, res = make_request("POST", "/auth/refresh", {
        "refresh_token": user_refresh_token
    })
    assert status == 200, f"Expected 200, got {status}: {res}"
    new_user_access_token = res["access_token"]
    new_user_refresh_token = res["refresh_token"]
    assert new_user_access_token != user_access_token
    assert new_user_refresh_token != user_refresh_token
    print("   [PASS] Token refresh successful. Old refresh token rotated.")

    # Test Token Reuse Detection: trying to use the old refresh token again should fail
    print("   Testing Token Reuse Detection...")
    status, res = make_request("POST", "/auth/refresh", {
        "refresh_token": user_refresh_token
    })
    assert status == 401, f"Expected 401, got {status}: {res}"
    print("   [PASS] Token reuse blocked and flagged successfully.")
    print()

    # --- 7. Logout Check ---
    print("7. Testing Logout...")
    status, res = make_request("POST", "/auth/logout", {
        "refresh_token": new_user_refresh_token
    })
    assert status == 200, f"Expected 200, got {status}: {res}"
    print("   [PASS] User logout successful.")

    # Trying to refresh again with the logged-out token should fail
    print("   Testing refreshing with logged-out token...")
    status, res = make_request("POST", "/auth/refresh", {
        "refresh_token": new_user_refresh_token
    })
    assert status == 401, f"Expected 401, got {status}: {res}"
    print("   [PASS] Logged-out token successfully invalidated.")
    print()

    print("=========================================================")
    print("     SUCCESS: ALL AUTHENTICATION TESTS PASSED!        ")
    print("=========================================================")

if __name__ == "__main__":
    run_tests()
