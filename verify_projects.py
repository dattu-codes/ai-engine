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


def make_multipart_request(
    path: str,
    fields: dict,
    files: dict,
    token: Optional[str] = None
) -> Tuple[int, dict]:
    """Makes a POST multipart/form-data request using urllib."""
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
        print(f"Network error: {str(e)}")
        return 500, {"detail": str(e)}


def create_test_zip() -> bytes:
    """Helper to build an in-memory ZIP file with mix of valid and ignored files."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Valid source files
        zf.writestr("main.py", "def add(a, b): return a + b")
        zf.writestr("com/app/Engine.java", "package com.app; public class Engine {}")
        zf.writestr("static/script.js", "console.log('dashboard script');")
        zf.writestr("components/layout.ts", "const layoutHeight = 24;")
        
        # Ignored files
        zf.writestr("node_modules/lodash/index.js", "module.exports = {}")
        zf.writestr("venv/Scripts/activate.bat", "echo 'active'")
        zf.writestr("__pycache__/main.cpython-39.pyc", b"\x03\xf3\x0d\x0a")
        zf.writestr("build/dist/output.js", "var build = true;")
        zf.writestr("readme.txt", "Plain text file description.")
        zf.writestr("avatar.png", b"\x89PNG\r\n\x1a\n")
        
    return zip_buffer.getvalue()


def run_tests():
    print("=========================================================")
    print("   Starting Automated Project Management Verification    ")
    print("=========================================================")
    print()

    # Generate unique credentials
    timestamp = int(time.time())
    username = f"proj_user_{timestamp}"
    hacker_username = f"hacker_user_{timestamp}"
    password = "securepassword123"

    # --- 1. Signup & Signin ---
    print("[1] Registering and signing in test user...")
    make_request("POST", "/auth/signup", {"username": username, "password": password, "role": "user"})
    status, token_res = make_request("POST", "/auth/login", {"username": username, "password": password})
    assert status == 200, "User login failed."
    token = token_res["access_token"]
    print("    Access Token acquired successfully.")

    # --- 2. Hacker User (to test ownership guards) ---
    make_request("POST", "/auth/signup", {"username": hacker_username, "password": password, "role": "user"})
    status, hack_token_res = make_request("POST", "/auth/login", {"username": hacker_username, "password": password})
    hacker_token = hack_token_res["access_token"]

    # --- 3. Create Project ---
    print("[2] Creating a new project...")
    status, project = make_request("POST", "/projects", {"name": "AI Pipeline Engine"}, token=token)
    assert status == 201, f"Project creation failed with status {status}"
    project_id = project["id"]
    print(f"    Project created: '{project['name']}' (ID: {project_id})")

    # --- 4. Get Project details ---
    print("[3] Getting project details...")
    status, details = make_request("GET", f"/projects/{project_id}", token=token)
    assert status == 200, "Fetching details failed."
    assert details["name"] == "AI Pipeline Engine", "Project name mismatch."
    assert details["total_files"] == 0, "Initial project should contain 0 files."
    print("    Initial project details validated successfully.")

    # --- 5. Rename Project ---
    print("[4] Renaming the project...")
    status, renamed = make_request("PUT", f"/projects/{project_id}", {"name": "AI Automation Engine"}, token=token)
    assert status == 200, "Project renaming failed."
    assert renamed["name"] == "AI Automation Engine", "Rename did not update value."
    print(f"    Project successfully renamed to '{renamed['name']}'.")

    # --- 6. Ingest Code: Paste Code Method ---
    print("[5] Testing Paste Code ingestion...")
    paste_fields = {
        "pasted_filename": "calculator.py",
        "pasted_content": "def multiply(a, b):\n    return a * b\n"
    }
    status, run_1 = make_multipart_request(f"/projects/{project_id}/upload", fields=paste_fields, files={}, token=token)
    assert status == 200, f"Pasted code upload failed with status {status}: {run_1}"
    assert run_1["source_type"] == "paste", "Run source type should be paste."
    assert run_1["status"] == "completed", "Run status should be completed."
    print("    Pasted code metadata enqueued and run completed.")

    # Check project details count (should be 1 file now)
    _, details = make_request("GET", f"/projects/{project_id}", token=token)
    assert details["total_files"] == 1, f"Expected 1 file, found {details['total_files']}"
    assert "Python" in details["languages"], "Python should be detected."
    print("    Pasted file verified in project stats.")

    # --- 7. Ingest Code: ZIP Archive Method ---
    print("[6] Testing ZIP archive upload and filtering...")
    zip_bytes = create_test_zip()
    files = {"file": ("project.zip", zip_bytes)}
    status, run_2 = make_multipart_request(f"/projects/{project_id}/upload", fields={}, files=files, token=token)
    assert status == 200, f"ZIP file upload failed with status {status}: {run_2}"
    assert run_2["source_type"] == "zip", "Run source type should be zip."
    print("    ZIP archive accepted and processed by service.")

    # Verify enqueued files list (should contain exactly 4 valid files: main.py, Engine.java, script.js, layout.ts)
    status, parsed_files = make_request("GET", f"/projects/{project_id}/files", token=token)
    assert status == 200, "Failed to list project files."
    
    filenames = [f["filename"] for f in parsed_files]
    print(f"    Indexed files: {filenames}")
    
    # Assert correct files are enqueued
    assert "main.py" in filenames
    assert "com/app/Engine.java" in filenames
    assert "static/script.js" in filenames
    assert "components/layout.ts" in filenames
    
    # Assert ignored files are NOT enqueued
    assert not any("node_modules" in name for name in filenames)
    assert not any("venv" in name for name in filenames)
    assert not any("__pycache__" in name for name in filenames)
    assert not any("readme.txt" in name for name in filenames)
    assert not any("avatar.png" in name for name in filenames)
    
    print("    ZIP extraction correctly enqueued valid source code and skipped all junk folders/extensions.")

    # Check project stats (languages: Python, Java, JavaScript, TypeScript, files: 4)
    _, details = make_request("GET", f"/projects/{project_id}", token=token)
    assert details["total_files"] == 4, f"Expected 4 files in latest analysis run, found {details['total_files']}"
    assert set(details["languages"]) == {"Python", "Java", "JavaScript", "TypeScript"}, f"Language mismatch: {details['languages']}"
    print("    All 4 core programming languages successfully detected.")

    # --- 8. Ingest Link: Git Repository ---
    print("[7] Testing Git Repository linking (architecture placeholder)...")
    status, run_3 = make_request(
        "POST", 
        f"/projects/{project_id}/repository", 
        {"repo_url": "https://github.com/dattu-codes/ai-engine-intern.git"}, 
        token=token
    )
    assert status == 200, f"Repo linking failed: {run_3}"
    assert run_3["source_type"] == "repository", "Run source type should be repository."
    print("    GitHub repository metadata registered.")

    # --- 9. Check Run History ---
    print("[8] Checking project history logs...")
    status, history = make_request("GET", f"/projects/{project_id}/history", token=token)
    assert status == 200
    assert len(history) == 3, f"Expected 3 history runs, found {len(history)}"
    print(f"    History loaded successfully. Runs count: {len(history)}")

    # --- 10. Security Guards: Ownership & Hacker Tests ---
    print("[9] Testing ownership guard security...")
    # Hacker attempts to get project details
    status, res = make_request("GET", f"/projects/{project_id}", token=hacker_token)
    assert status == 404, f"Security Breach! Hacker could access project: {res}"
    # Hacker attempts to rename project
    status, res = make_request("PUT", f"/projects/{project_id}", {"name": "Hacked Name"}, token=hacker_token)
    assert status == 404, f"Security Breach! Hacker could modify project: {res}"
    print("    All unauthorized access attempts successfully blocked (404 Not Found).")

    # --- 11. Delete Project ---
    print("[10] Deleting project...")
    status, _ = make_request("DELETE", f"/projects/{project_id}", token=token)
    assert status == 240 or status == 204 or status == 200, f"Project deletion failed: {status}"
    
    # Confirm it is deleted
    status, _ = make_request("GET", f"/projects/{project_id}", token=token)
    assert status == 404, "Project still accessible after deletion."
    print("    Project successfully deleted and confirmed offline.")

    print()
    print("=========================================================")
    print("   ALL VERIFICATION TESTS COMPLETED SUCCESSFULLY!        ")
    print("=========================================================")

if __name__ == "__main__":
    run_tests()
