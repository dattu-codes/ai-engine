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
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    req_body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=req_body, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
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


def make_multipart_request(
    path: str,
    fields: dict,
    token: Optional[str] = None
) -> Tuple[int, dict]:
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    url = f"{BASE_URL}{path}"
    
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    body_parts = []
    for key, val in fields.items():
        body_parts.append(f"--{boundary}")
        body_parts.append(f'Content-Disposition: form-data; name="{key}"')
        body_parts.append("")
        body_parts.append(str(val))
        
    body_parts.append(f"--{boundary}--")
    body_parts.append("")
    req_body = "\r\n".join(body_parts).encode("utf-8")
    
    req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            res_body = response.read().decode("utf-8")
            return response.status, json.loads(res_body) if res_body else {}
    except urllib.error.HTTPError as e:
        res_body = e.read().decode("utf-8")
        try:
            res_json = json.loads(res_body)
        except Exception:
            res_json = {"detail": res_body}
        return e.code, res_json
    except Exception as e:
        return 500, {"detail": str(e)}


def run_tests():
    print("=========================================================")
    print("     Starting Automated Static Analyzer Verification     ")
    print("=========================================================")

    # 1. Register and sign in user
    username = f"analyzer_user_{int(time.time())}"
    password = "secure_password_123"
    
    print("\n1. Registering test user...")
    status, res = make_request("POST", "/auth/signup", {"username": username, "password": password})
    assert status == 201, f"Failed signup: {res}"
    print("   [PASS] User registered successfully.")

    print("\n2. Logging in to acquire token...")
    status, res = make_request("POST", "/auth/login", {"username": username, "password": password})
    assert status == 200, f"Failed login: {res}"
    token = res["access_token"]
    print("   [PASS] Login successful.")

    # 2. Create project
    print("\n3. Creating project...")
    status, project = make_request("POST", "/projects", {"name": "Static Analysis Verification"}, token)
    assert status == 201, f"Failed to create project: {project}"
    project_id = project["id"]
    print(f"   [PASS] Project created successfully. (ID: {project_id})")

    # 3. Paste complex & vulnerable python code
    complex_code = """
def process_data(data, user_role):
    # Security violation: eval usage
    eval(data)
    
    # Insecure temporary file
    import tempfile
    tempfile.mktemp()
    
    # Hardcoded credential
    api_key = "secret_token_12345"
    
    # Complexity points: control structures
    if user_role == "admin":
        for item in data:
            if item.get("status") == "active":
                print("Active item")
            elif item.get("status") == "pending":
                print("Pending item")
            else:
                print("Unknown item")
    else:
        print("Standard access")
        
    return True
"""
    print("\n4. Ingesting complex & vulnerable Python code file...")
    status, res = make_multipart_request(
        f"/projects/{project_id}/upload",
        {
            "pasted_filename": "analyzer_test.py",
            "pasted_content": complex_code
        },
        token
    )
    assert status == 200, f"Failed to upload code: {res}"
    print("   [PASS] Code uploaded successfully.")

    # 4. Trigger review analysis run (mock simulation fallback is active since API Key is blank)
    print("\n5. Running AI Review analysis (Offline Simulator)...")
    status, run = make_request("POST", f"/analysis/{project_id}/run", {}, token)
    assert status == 201, f"Failed to start analysis: {run}"
    analysis_id = run["id"]
    print(f"   [PASS] Analysis run successfully enqueued. (ID: {analysis_id})")

    # 5. Poll status
    print("\n6. Polling analysis job status...")
    completed = False
    for attempt in range(10):
        status, run_status = make_request("GET", f"/analysis/{analysis_id}", token=token)
        assert status == 200, f"Failed to get run status: {run_status}"
        
        current_status = run_status["status"]
        print(f"   Attempt {attempt+1}: Status is '{current_status}'")
        if current_status == "completed":
            completed = True
            break
        elif current_status == "failed":
            raise AssertionError("Analysis execution failed.")
        time.sleep(1)
        
    assert completed, "Analysis job did not complete in time."

    # 6. Fetch report and verify static metrics assertions
    print("\n7. Fetching review report details...")
    status, report = make_request("GET", f"/analysis/{analysis_id}/report", token=token)
    assert status == 200, f"Failed to get report: {report}"
    
    details_json = json.loads(report["details_json"])
    assert "analyzers" in details_json, "Report does not contain 'analyzers' static data."
    
    analyzers = details_json["analyzers"]
    summary = analyzers["summary"]
    
    # Assert Complexity (base 1 + 1 (if user_role) + 1 (for item) + 1 (if active) + 1 (elif pending)) = 5
    complexity = summary["avg_complexity"]
    print(f"   - Average complexity calculated: {complexity}")
    assert complexity == 5.0, f"Complexity rating calculated inaccurately. Expected 5.0, got {complexity}"
    print("     [PASS] Complexity metrics are mathematically accurate.")
    
    # Assert Security warnings (eval, mktemp, hardcoded password)
    vulnerabilities = analyzers["vulnerabilities"]
    vulnerabilities_count = summary["vulnerabilities_count"]
    print(f"   - Vulnerabilities count: {vulnerabilities_count}")
    assert len(vulnerabilities) == 3, f"Expected 3 warnings, got {len(vulnerabilities)}"
    
    # Validate specific categories
    categories = [v["category"] for v in vulnerabilities]
    assert "Insecure Execution" in categories, "Failed to flag insecure eval execution."
    assert "File Handling" in categories, "Failed to flag symlink race condition (mktemp)."
    assert "Hardcoded Credentials" in categories, "Failed to flag hardcoded credential assignments."
    print("     [PASS] Security warnings correctly detected all AST vulnerabilities.")

    # Assert Maintainability Index (MI) calculation bounds
    avg_maintainability = summary["avg_maintainability"]
    print(f"   - Average maintainability score: {avg_maintainability}%")
    assert 0 <= avg_maintainability <= 100, f"Maintainability Index out of bounds: {avg_maintainability}"
    print("     [PASS] Maintainability Index calculation is bounded correctly.")

    print("\n=========================================================")
    print("  ALL STATIC CODE ANALYZER VERIFICATIONS PASSED!        ")
    print("=========================================================")

if __name__ == "__main__":
    run_tests()
