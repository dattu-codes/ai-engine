import json
import time
import urllib.request
import urllib.error
import sys
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
        with urllib.request.urlopen(req, timeout=30) as response:
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
        print(f"Network error on {method} {path}: {str(e)}")
        return 500, {"detail": str(e)}

def main():
    print("===================================================")
    print("   AI Engine - GitHub Integration Verification")
    print("===================================================\n")
    
    # 1. Register a test user
    timestamp = int(time.time())
    username = f"gituser_{timestamp}"
    password = "password123"
    
    print(f"[*] Registering test user: {username}...")
    status, res = make_request("POST", "/auth/signup", {
        "username": username,
        "password": password
    })
    
    if status != 201:
        print(f"[FAIL] Registration failed with status {status}: {res}")
        sys.exit(1)
    print("[OK] Test user registered successfully.")
    
    # 2. Login
    print("[*] Logging in...")
    status, res = make_request("POST", "/auth/login", {
        "username": username,
        "password": password
    })
    
    if status != 200:
        print(f"[FAIL] Login failed with status {status}: {res}")
        sys.exit(1)
        
    token = res.get("access_token")
    if not token:
        print("[FAIL] Access token not returned on login.")
        sys.exit(1)
    print("[OK] Logged in successfully.")
    
    # 3. Create project with invalid GitHub URL
    bad_repo = "https://github.com/invalid-owner-name-12345/nonexistent-repo-abcde"
    print(f"[*] Attempting to create project with invalid repo URL: {bad_repo} (Expecting failure)...")
    status, res = make_request("POST", "/projects", {
        "name": "Invalid Repo Project",
        "repo_url": bad_repo
    }, token=token)
    
    if status == 400:
        print(f"[OK] Creation failed as expected with 400: {res.get('detail')}")
    else:
        print(f"[FAIL] Expected 400 Bad Request, got status {status}: {res}")
        sys.exit(1)
        
    # 4. Create project with valid public GitHub URL
    valid_repo = "https://github.com/dattu-codes/ai-engine-intern.git"
    print(f"[*] Creating project with valid public repo URL: {valid_repo}...")
    status, res = make_request("POST", "/projects", {
        "name": "AI Engine Intern Repo",
        "repo_url": valid_repo
    }, token=token)
    
    if status != 201:
        print(f"[FAIL] Project creation failed with status {status}: {res}")
        sys.exit(1)
        
    project_id = res.get("id")
    print(f"[OK] Project created successfully. Project ID: {project_id}")
    
    # 5. Fetch project details and assert metadata
    print(f"[*] Fetching details for project {project_id}...")
    status, details = make_request("GET", f"/projects/{project_id}", token=token)
    
    if status != 200:
        print(f"[FAIL] Failed to fetch project details with status {status}: {details}")
        sys.exit(1)
        
    # Assertions on project repository metadata fields
    print("[*] Asserting repository metadata...")
    errors = []
    
    if details.get("repo_url") != valid_repo:
        errors.append(f"repo_url mismatch: expected {valid_repo}, got {details.get('repo_url')}")
    if details.get("repo_name") != "ai-engine-intern":
        errors.append(f"repo_name mismatch: expected 'ai-engine-intern', got {details.get('repo_name')}")
    if details.get("repo_owner") != "dattu-codes":
        errors.append(f"repo_owner mismatch: expected 'dattu-codes', got {details.get('repo_owner')}")
    if not details.get("default_branch"):
        errors.append("default_branch is empty")
    if not details.get("current_branch"):
        errors.append("current_branch is empty")
    if not details.get("last_commit_sha"):
        errors.append("last_commit_sha is empty")
    if not details.get("last_commit_message"):
        errors.append("last_commit_message is empty")
    if details.get("total_files", 0) <= 0:
        errors.append(f"total_files should be > 0, got {details.get('total_files')}")
        
    if errors:
        print("[FAIL] Metadata assertion failures:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
        
    print("[OK] All repository metadata fields correctly populated:")
    print(f"  Owner: {details.get('repo_owner')}")
    print(f"  Name: {details.get('repo_name')}")
    print(f"  Branch: {details.get('current_branch')}")
    print(f"  Commit SHA: {details.get('last_commit_sha')}")
    print(f"  Commit Message: {details.get('last_commit_message').strip().splitlines()[0]}")
    print(f"  Total Files Ingested: {details.get('total_files')}")
    
    # 6. Test sync repository (already up to date)
    print(f"[*] Triggering repository sync for project {project_id}...")
    status, sync_res = make_request("POST", f"/projects/{project_id}/sync", token=token)
    
    if status != 200:
        print(f"[FAIL] Repository sync failed with status {status}: {sync_res}")
        sys.exit(1)
        
    if sync_res.get("status") != "up_to_date":
        print(f"[FAIL] Expected sync status 'up_to_date', got: {sync_res}")
        sys.exit(1)
        
    print("[OK] Sync endpoint returned 'up_to_date' successfully.")
    
    # 7. Check project files list
    print(f"[*] Fetching project files list...")
    status, files = make_request("GET", f"/projects/{project_id}/files", token=token)
    
    if status != 200:
        print(f"[FAIL] Failed to fetch project files with status {status}: {files}")
        sys.exit(1)
        
    if len(files) != details.get("total_files"):
        print(f"[FAIL] Files count mismatch: details say {details.get('total_files')}, files list returned {len(files)}")
        sys.exit(1)
        
    print(f"[OK] Correctly loaded {len(files)} files metadata from project files endpoint.")
    print("\n[SUCCESS] GitHub Integration functionality verified successfully!")

if __name__ == "__main__":
    main()
