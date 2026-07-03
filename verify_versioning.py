import json
import time
import urllib.request
import urllib.error
import io
import zipfile
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
        return 500, {"detail": str(e)}


def make_multipart_request(
    path: str,
    fields: dict,
    files: dict,
    token: Optional[str] = None
) -> Tuple[int, dict]:
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    CRLF = b"\r\n"
    parts = []
    
    for key, value in fields.items():
        parts.append(b"--" + boundary.encode("utf-8"))
        parts.append(f'Content-Disposition: form-data; name="{key}"'.encode("utf-8"))
        parts.append(b"")
        parts.append(str(value).encode("utf-8"))
        
    for key, (filename, content_bytes) in files.items():
        parts.append(b"--" + boundary.encode("utf-8"))
        parts.append(f'Content-Disposition: form-data; name="{key}"; filename="{filename}"'.encode("utf-8"))
        parts.append(b"Content-Type: application/octet-stream")
        parts.append(b"")
        parts.append(content_bytes)
        
    parts.append(b"--" + boundary.encode("utf-8") + b"--")
    parts.append(b"")
    
    body = CRLF.join(parts)
    url = f"{BASE_URL}{path}"
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body))
    }
    
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    
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
        return 500, {"detail": str(e)}


def create_test_zip() -> bytes:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # File 1: Python module containing an eval security vulnerability
        zf.writestr(
            "app/auth.py",
            "def check_session(token):\n    eval(\"arbitrary_string\")\n" + "\n" * 12 + "    pass\n"
        )
        # File 2: Simple helper
        zf.writestr(
            "app/utils.py",
            "def add_nums(a, b):\n    return a + b\n"
        )
    return zip_buffer.getvalue()


def run_tests():
    print("=" * 80)
    print("STARTING INTEGRATION TEST SUITE: PROJECT VERSIONING & WORKSPACE MANAGEMENT")
    print("=" * 80)
    
    timestamp = int(time.time())
    username = f"version_tester_{timestamp}"
    password = "password123"
    
    # 1. Signup User
    print("\n[STEP 1] Registering a new test user...")
    status_code, res = make_request("POST", "/auth/signup", {
        "username": username,
        "password": password,
        "role": "user"
    })
    assert status_code == 201, f"Failed signup: {res}"
    print("User registration successful!")
    
    # 2. Login User
    print("\n[STEP 2] Logging in to retrieve Bearer token...")
    status_code, res = make_request("POST", "/auth/login", {
        "username": username,
        "password": password
    })
    assert status_code == 200, f"Failed login: {res}"
    token = res.get("access_token")
    assert token, "Bearer Token missing in response payload"
    print("Token retrieved successfully.")
    
    # 3. Create Project Node
    print("\n[STEP 3] Allocating a new project node container...")
    status_code, project = make_request("POST", "/projects", {
        "name": f"Versioning Test Project {timestamp}",
        "repo_url": None
    }, token=token)
    assert status_code == 201, f"Failed project creation: {project}"
    project_id = project["id"]
    print(f"Project created. Node ID: {project_id}")

    # 4. Ingest Codebase ZIP
    print("\n[STEP 4] Ingesting test codebase archive (creates baseline Version 1)...")
    zip_bytes = create_test_zip()
    status_code, res = make_multipart_request(
        f"/projects/{project_id}/upload",
        fields={},
        files={"file": ("codebase.zip", zip_bytes)},
        token=token
    )
    assert status_code == 200, f"ZIP upload failed: {res}"
    print("Codebase ingested successfully.")

    # 5. Fetch Version History & Verify Baseline
    print("\n[STEP 5] Retrieving version history to verify baseline Version 1...")
    status_code, history = make_request("GET", f"/projects/{project_id}/versions", token=token)
    assert status_code == 200, f"Failed listing versions: {history}"
    assert len(history) == 1, f"Expected exactly 1 baseline version, got {len(history)}"
    
    v1 = history[0]
    assert v1["version_number"] == 1, f"Expected Version 1, got {v1['version_number']}"
    assert v1["parent_version_id"] is None, "v1 should not have a parent version"
    print("Baseline Version 1 verification successful!")

    # 6. Run initial review analysis
    print("\n[STEP 6] Running AI review analysis on baseline version...")
    status_code, analysis = make_request("POST", f"/analysis/{project_id}/run", {"api_key": None}, token=token)
    assert status_code == 201, f"Failed running analysis: {analysis}"
    analysis_id = analysis["id"]
    
    # Poll for completion
    print("Waiting for review pipeline completion...")
    for _ in range(10):
        status_code, run = make_request("GET", f"/analysis/{analysis_id}", token=token)
        if run["status"] == "completed":
            break
        elif run["status"] == "failed":
            raise RuntimeError("Analysis run failed.")
        time.sleep(1)
    else:
        raise TimeoutError("Analysis timed out.")
    print("Baseline analysis completed.")

    # Fetch report issues to get target issue for fixing
    status_code, report = make_request("GET", f"/analysis/{analysis_id}/report", token=token)
    assert status_code == 200, f"Failed fetching report: {report}"
    report_data = json.loads(report["details_json"])
    issues = report_data.get("issues", [])
    assert len(issues) > 0, "No issues detected in mock codebase scan"
    print(f"Detected {len(issues)} codebase warnings.")
    
    # 7. Apply AI Fix to create Version 2
    print("\n[STEP 7] Applying AI Fix to target code (creates Version 2)...")
    target_issue = next(iss for iss in issues if iss["category"] == "Security")
    status_code, new_ver = make_request("POST", f"/projects/{project_id}/versions/apply-fix", {
        "issue": target_issue,
        "api_key": None
    }, token=token)
    assert status_code == 200, f"Apply fix failed: {new_ver}"
    assert new_ver["version_number"] == 2, f"Expected Version 2, got {new_ver['version_number']}"
    assert new_ver["parent_version_id"] == v1["id"], "Version 2 parent should point to Version 1"
    print("AI Fix applied. Version 2 snapshot created.")

    # Wait for Version 2's review analysis to complete
    print("Waiting for Version 2 review analysis to complete...")
    v2_analysis_id = new_ver["source_analysis_id"]
    for _ in range(10):
        status_code, run = make_request("GET", f"/analysis/{v2_analysis_id}", token=token)
        if run["status"] == "completed":
            break
        elif run["status"] == "failed":
            raise RuntimeError("Version 2 review analysis run failed.")
        time.sleep(1)
    else:
        raise TimeoutError("Version 2 review analysis timed out.")
    print("Version 2 review analysis completed.")

    # 8. Compare Version 1 and Version 2
    print("\n[STEP 8] Comparing Version 1 baseline and Version 2 fixed snapshot...")
    status_code, comparison = make_request(
        "GET", 
        f"/projects/{project_id}/versions/compare/details?v1_id={v1['id']}&v2_id={new_ver['id']}", 
        token=token
    )
    print("Comparison Result:", json.dumps(comparison, indent=2))
    assert status_code == 200, f"Comparison failed: {comparison}"
    assert comparison["files_changed_count"] == 1, f"Expected 1 file changed, got {comparison['files_changed_count']}"
    assert "app/auth.py" in comparison["diffs"], "Expected diff block for app/auth.py"
    assert comparison["lines_removed"] > 0, "Expected line removals"
    assert len(comparison["issues_fixed"]) > 0, "Expected at least 1 resolved issue"
    print("Version comparison checks successful!")

    # 9. Restore Version 1
    print("\n[STEP 9] Restoring project codebase back to Version 1 baseline...")
    status_code, restored_ver = make_request("POST", f"/projects/{project_id}/versions/{v1['id']}/restore", {}, token=token)
    assert status_code == 200, f"Restore failed: {restored_ver}"
    assert restored_ver["version_number"] == 3, f"Expected Version 3, got {restored_ver['version_number']}"
    print("Codebase successfully restored back to baseline Version 1 state.")

    # 10. Download Version 2 ZIP
    print("\n[STEP 10] Downloading Version 2 ZIP archive snapshot...")
    url = f"{BASE_URL}/projects/{project_id}/versions/{new_ver['id']}/download"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            assert response.status == 200, f"ZIP download failed: {response.status}"
            assert response.headers.get("Content-Type") == "application/zip", "Content-Type is not application/zip"
            zip_data = response.read()
            
            # Verify zip content actually holds fixed code
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                file_list = zf.namelist()
                assert "app/auth.py" in file_list, "Missing app/auth.py inside downloaded ZIP"
                auth_content = zf.read("app/auth.py").decode("utf-8")
                # Eval security issue should be replaced with secure comment
                assert "eval(" not in auth_content, "Security vulnerability 'eval' was not fixed in download codebase"
                assert "eval removed" in auth_content, "Vulnerability signature missing refactored log"
    except Exception as e:
        raise AssertionError(f"ZIP download verification failed: {e}")

    print("ZIP archive download check successful!")
    print("\n" + "=" * 80)
    print("ALL INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        run_tests()
    except Exception as e:
        print(f"\nTEST SUITE CRITICAL FAILURE: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
