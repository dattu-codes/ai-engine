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
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    req_body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=req_body, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
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
        return 500, {"detail": str(e)}


def run_tests():
    print("=" * 80)
    print("STARTING INTEGRATION TEST SUITE: TEAM COLLABORATION & WORKFLOWS (v2.3)")
    print("=" * 80)
    
    timestamp = int(time.time())
    owner_username = f"ws_owner_{timestamp}"
    dev_username = f"ws_dev_{timestamp}"
    password = "password123"
    
    # 1. Register Owner
    print("\n[STEP 1] Registering Owner user...")
    status_code, res = make_request("POST", "/auth/signup", {
        "username": owner_username,
        "password": password,
        "role": "user"
    })
    assert status_code == 201, f"Failed signup: {res}"
    print(f"Owner {owner_username} registered successfully.")
    
    # 2. Register Developer
    print("\n[STEP 2] Registering Developer user...")
    status_code, res = make_request("POST", "/auth/signup", {
        "username": dev_username,
        "password": password,
        "role": "user"
    })
    assert status_code == 201, f"Failed signup: {res}"
    print(f"Developer {dev_username} registered successfully.")
    
    # 3. Login Owner
    print("\n[STEP 3] Logging in as Owner to get token...")
    status_code, res = make_request("POST", "/auth/login", {
        "username": owner_username,
        "password": password
    })
    assert status_code == 200, f"Failed login: {res}"
    owner_token = res.get("access_token")
    print("Owner token retrieved.")
    
    # 4. Login Developer
    print("\n[STEP 4] Logging in as Developer to get token...")
    status_code, res = make_request("POST", "/auth/login", {
        "username": dev_username,
        "password": password
    })
    assert status_code == 200, f"Failed login: {res}"
    dev_token = res.get("access_token")
    print("Developer token retrieved.")
    
    # 5. Create Collaborative Workspace
    print("\n[STEP 5] Creating a new collaborative workspace...")
    status_code, workspace = make_request("POST", "/workspaces", {
        "name": f"Core Eng Workspace {timestamp}",
        "description": "Collaborative workspace for core engineering projects"
    }, token=owner_token)
    assert status_code == 201, f"Workspace creation failed: {workspace}"
    workspace_id = workspace["id"]
    print(f"Workspace created. ID: {workspace_id}")
    
    # 6. Add/Invite Developer member to the workspace
    print("\n[STEP 6] Adding Developer user as Developer member...")
    status_code, member = make_request("POST", f"/workspaces/{workspace_id}/members", {
        "username": dev_username,
        "role": "Developer"
    }, token=owner_token)
    assert status_code == 201, f"Adding member failed: {member}"
    print("Developer added to workspace members.")
    
    # 7. Create Project in Workspace
    print("\n[STEP 7] Creating a new project inside the workspace...")
    status_code, project = make_request("POST", "/projects", {
        "name": f"Workspace Project {timestamp}",
        "repo_url": None,
        "workspace_id": workspace_id
    }, token=owner_token)
    assert status_code == 201, f"Project creation inside workspace failed: {project}"
    project_id = project["id"]
    print(f"Project created inside workspace. Project ID: {project_id}")
    
    # 8. Upload pasted code and start review pipeline (to populate findings)
    print("\n[STEP 8] Ingesting source code containing issues...")
    # PASTED FILE
    url = f"{BASE_URL}/projects/{project_id}/upload"
    boundary = "---BoundaryVal---"
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Authorization": f"Bearer {owner_token}"
    }
    body_str = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="pasted_filename"\r\n\r\n'
        f"vuln.py\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="pasted_content"\r\n\r\n'
        f"import sqlite3\n"
        f"def get_user(uid):\n"
        f"    # CRITICAL: Sqlite SQL Injection flaw!\n"
        f"    conn = sqlite3.connect('test.db')\n"
        f"    return conn.execute(f'SELECT * FROM users WHERE id = {{uid}}')\n\r\n"
        f"--{boundary}--\r\n"
    )
    req = urllib.request.Request(url, data=body_str.encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200, f"Source upload failed: {resp.status}"
    print("Pasted file uploaded successfully.")
    
    # Start analysis
    status_code, analysis_info = make_request("POST", f"/analysis/{project_id}/run", {"api_key": None}, token=owner_token)
    assert status_code == 201, f"Analysis trigger failed: {analysis_info}"
    analysis_id = analysis_info["id"]
    print(f"Analysis started. ID: {analysis_id}")
    
    # Poll for completion
    print("Waiting for review pipeline to complete...")
    for _ in range(20):
        status_code, details = make_request("GET", f"/analysis/{analysis_id}", token=owner_token)
        if details.get("status") == "COMPLETED":
            print("Pipeline execution completed!")
            break
        time.sleep(1)
    
    # 9. Verify findings generated
    print("\n[STEP 9] Verifying generated review findings...")
    status_code, findings = make_request("GET", f"/projects/{project_id}/findings", token=owner_token)
    assert status_code == 200, f"Get findings failed: {findings}"
    assert len(findings) > 0, "No findings detected in the uploaded SQL injection code"
    finding_id = findings[0]["id"]
    print(f"Review findings verified. Finding ID: {finding_id}, Severity: {findings[0]['severity']}")
    
    # 10. Assign finding to Developer member
    print("\n[STEP 10] Assigning the finding to Developer member...")
    status_code, updated_finding = make_request("PATCH", f"/findings/{finding_id}/assign", {
        "assigned_to": dev_username
    }, token=owner_token)
    assert status_code == 200, f"Assignment failed: {updated_finding}"
    assert updated_finding["assigned_to"] == dev_username, "Assignee was not updated in database"
    print("Finding successfully assigned to Developer.")
    
    # 11. Add thread comment to the finding
    print("\n[STEP 11] Adding collaborative thread comments to the finding...")
    status_code, comment1 = make_request("POST", f"/findings/{finding_id}/comments", {
        "comment": "This is a genuine SQL Injection risk. Let's fix it ASAP."
    }, token=owner_token)
    assert status_code == 201, f"Failed posting comment 1: {comment1}"
    
    status_code, comment2 = make_request("POST", f"/findings/{finding_id}/comments", {
        "comment": "I agree. I will refactor it using parameterized parameters."
    }, token=dev_token)
    assert status_code == 201, f"Failed posting comment 2: {comment2}"
    print("Thread comments posted by owner and developer successfully.")
    
    # 12. Fetch Comments Thread
    print("\n[STEP 12] Fetching comment discussion thread history...")
    status_code, comments_list = make_request("GET", f"/findings/{finding_id}/comments", token=dev_token)
    assert status_code == 200, f"Get comments failed: {comments_list}"
    assert len(comments_list) == 2, f"Expected 2 comments, got: {len(comments_list)}"
    print(f"Comment 1: [{comments_list[0]['username']}] {comments_list[0]['comment']}")
    print(f"Comment 2: [{comments_list[1]['username']}] {comments_list[1]['comment']}")
    
    # 13. Suppress/Ignore Finding with Reason
    print("\n[STEP 13] Testing false positive suppression (Ignoring finding with reason)...")
    status_code, ignored_finding = make_request("PATCH", f"/findings/{finding_id}/ignore", {
        "reason": "This is a test database not exposed in production"
    }, token=dev_token)
    assert status_code == 200, f"Ignoring finding failed: {ignored_finding}"
    assert ignored_finding["status"] == "Ignored", "Finding status not updated to Ignored"
    assert ignored_finding["ignored_reason"] == "This is a test database not exposed in production", "Ignored reason mismatch"
    print("Finding successfully ignored/suppressed.")
    
    # 14. Reopen Finding
    print("\n[STEP 14] Testing reopening the finding...")
    status_code, reopened_finding = make_request("PATCH", f"/findings/{finding_id}/reopen", token=owner_token)
    assert status_code == 200, f"Reopening finding failed: {reopened_finding}"
    assert reopened_finding["status"] == "Open", "Finding status not reverted to Open"
    print("Finding successfully reopened.")
    
    # 15. Check Workspace Activity timeline logs
    print("\n[STEP 15] Retrieving workspace activity audit timeline logs...")
    status_code, res = make_request("GET", f"/workspaces/{workspace_id}/activities", token=owner_token)
    assert status_code == 200, f"Get activities failed: {res}"
    activity_logs = res.get("activities", [])
    assert len(activity_logs) > 0, "No workspace activities logged"
    print(f"Found {len(activity_logs)} timeline activity logs:")
    for log in activity_logs:
        print(f" - [{log['username']}] {log['activity_type']}: {log.get('description', '')}")
        
    print("\n" + "=" * 80)
    print("SUCCESS: ALL COLLABORATION & TEAM WORKFLOW TESTS PASSED!")
    print("=" * 80)

if __name__ == "__main__":
    try:
        run_tests()
    except AssertionError as e:
        print(f"\n[TEST FAILURE]: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR]: {e}")
        sys.exit(1)
