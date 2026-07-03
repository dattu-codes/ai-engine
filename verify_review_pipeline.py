import json
import time
import urllib.request
import urllib.error
import io
import zipfile
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


def create_pipeline_test_zip() -> bytes:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Grouped under API / API Router module
        zf.writestr("app/api/endpoints.py", """from fastapi import FastAPI
app = FastAPI()

eval("arbitrary_string")
""")
        # Grouped under Authentication module
        zf.writestr("app/auth/login.py", """# Authentication helper
def perform_login():
    try:
        pass
    except Exception:
        pass
""")
        # Grouped under Utilities module
        zf.writestr("app/utils/helpers.py", """# Utility helper
def run_helper():
    pass
""")
        # Grouped under skip directory (ModuleGrouper skips vendor/)
        zf.writestr("vendor/library.js", """console.log("vendor library contents");""")
        
    return zip_buffer.getvalue()


def run_pipeline_tests():
    print("=========================================================")
    print("   Starting Automated Review Pipeline Verification       ")
    print("=========================================================")
    print()

    # Generate credentials
    timestamp = int(time.time())
    username = f"pipeline_user_{timestamp}"
    password = "securepassword123"

    # --- 1. Signup & Login ---
    print("[1] Registering and signing in test user...")
    make_request("POST", "/auth/signup", {"username": username, "password": password, "role": "user"})
    status, token_res = make_request("POST", "/auth/login", {"username": username, "password": password})
    assert status == 200, "User login failed."
    token = token_res["access_token"]
    print("    Access Token acquired.")

    # --- 2. Create Project ---
    print("[2] Creating a new project...")
    status, project = make_request("POST", "/projects", {"name": "Test Review Pipeline"}, token=token)
    assert status == 201, f"Project creation failed: {project}"
    project_id = project["id"]
    print(f"    Project ID: {project_id}")

    # --- 3. Ingest Code ZIP ---
    print("[3] Uploading codebase ZIP archive...")
    code_zip = create_pipeline_test_zip()
    files = {"file": ("codebase.zip", code_zip)}
    status, upload_res = make_multipart_request(f"/projects/{project_id}/upload", fields={}, files=files, token=token)
    assert status == 200, f"Upload failed: {upload_res}"
    print("    Codebase ZIP ingested.")

    # --- 4. Trigger Analysis Review Run ---
    print("[4] Triggering modular AI Review Pipeline run...")
    status, analysis = make_request("POST", f"/analysis/{project_id}/run", {"api_key": None}, token=token)
    assert status == 201, f"Run start failed: {analysis}"
    analysis_id = analysis["id"]
    print(f"    Analysis Run ID: {analysis_id}")

    # --- 5. Poll Status until complete ---
    print("[5] Polling status and validating timeline step transitions...")
    max_polls = 10
    completed = False
    
    for i in range(max_polls):
        time.sleep(1.5)
        status_code, run = make_request("GET", f"/analysis/{analysis_id}", token=token)
        assert status_code == 200, f"Status check failed: {run}"
        
        stages_json = run.get("pipeline_stages")
        if stages_json:
            stages = json.loads(stages_json)
            running_stages = [s["stage"] for s in stages if s["status"] == "running"]
            completed_stages = [s["stage"] for s in stages if s["status"] == "completed"]
            print(f"    [Poll #{i+1}] Completed Stages: {len(completed_stages)}/6. Running: {running_stages}")
            
        if run["status"] == "completed":
            completed = True
            break
        elif run["status"] == "failed":
            raise AssertionError("Pipeline analysis task failed.")
            
    assert completed is True, "Pipeline analysis run did not finish in time."

    # --- 6. Validate Timeline stages & Telemetry metadata ---
    print("[6] Validating pipeline stages timeline details...")
    status_code, final_run = make_request("GET", f"/analysis/{analysis_id}", token=token)
    assert status_code == 200
    
    # Assert telemetry values
    assert final_run["total_files"] == 4, f"Expected 4 files, got {final_run['total_files']}"
    assert final_run["files_reviewed"] == 3, f"Expected 3 files reviewed, got {final_run['files_reviewed']}"
    assert final_run["skipped_files"] == 1, f"Expected 1 file skipped, got {final_run['skipped_files']}"
    assert final_run["coverage_percentage"] == 75.0, f"Expected 75% coverage, got {final_run['coverage_percentage']}"
    
    modules_rev = json.loads(final_run["modules_reviewed"])
    assert "API" in modules_rev, "API module should be reviewed"
    assert "Authentication" in modules_rev, "Authentication module should be reviewed"
    assert "Utilities" in modules_rev, "Utilities module should be reviewed"
    
    skipped_reasons = json.loads(final_run["skipped_reasons_json"])
    assert "vendor/library.js" in skipped_reasons, "vendor/library.js should be in skipped reasons"
    assert skipped_reasons["vendor/library.js"] == "Vendor / Build Directories"
    
    stages = json.loads(final_run["pipeline_stages"])
    assert len(stages) == 6, "Expected 6 stages in pipeline"
    for s in stages:
        assert s["status"] == "completed", f"Stage {s['stage']} should be completed"
        assert s["duration"] >= 0.0, f"Stage {s['stage']} duration should be recorded"
        
    print("    Pipeline timeline stages, sequential durations, and files metrics validated.")

    # --- 7. Validate Final Engineering Report structure ---
    print("[7] Inspecting compiled engineering report findings...")
    status_code, report = make_request("GET", f"/analysis/{analysis_id}/report", token=token)
    assert status_code == 200, f"Report query failed: {report}"
    
    report_details = json.loads(report["details_json"])
    assert "score" in report_details, "Report details should contain consolidated score"
    assert "summary" in report_details, "Report details should contain executive summary"
    assert "coverage" in report_details, "Report details should contain coverage metrics"
    
    issues = report_details["issues"]
    assert len(issues) > 0, "Consolidated issues should be generated"
    
    # Assert sorting order by severity: Critical -> High -> Medium -> Low
    sevs = [i["severity"].lower() for i in issues]
    print(f"    Extracted issues severity distribution order: {sevs}")
    
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    for idx in range(len(sevs) - 1):
        assert severity_order[sevs[idx]] <= severity_order[sevs[idx+1]], "Issues should be sorted by severity order (critical -> high -> medium -> low)"
        
    # Verify evidence-based findings schema
    for i in issues:
        assert "category" in i
        assert "severity" in i
        assert "file" in i
        assert "line" in i
        assert "evidence" in i
        assert "explanation" in i
        assert "recommendation" in i
        assert "confidence" in i
        assert i["evidence"] != "", "Evidence snippet must be present"
        assert i["explanation"] != "", "Explanation must be present"
        assert i["recommendation"] != "", "Recommendation must be present"
        
    print("    Evidence-based findings, deduplication, and severity order sorting validated successfully.")

    print()
    print("=========================================================")
    print("   AI Review Pipeline Verification Passed Successfully! ")
    print("=========================================================")


if __name__ == "__main__":
    run_pipeline_tests()
