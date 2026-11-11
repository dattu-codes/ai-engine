import os
import sys
import json
import time
from typing import Tuple, Optional

# In-memory test client runner
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from test_client_helper import make_request, make_multipart_request


def run_analysis_tests():
    print("=========================================================")
    print("   Starting Automated AI Review Engine Verification      ")
    print("=========================================================")
    print()

    # Generate unique credentials
    timestamp = int(time.time())
    username = f"anal_user_{timestamp}"
    hacker_username = f"anal_hack_{timestamp}"
    password = "securepassword123"

    # --- 1. Signup & Signin ---
    print("[1] Registering and signing in test user...")
    make_request("POST", "/auth/signup", {"username": username, "password": password, "role": "user"})
    status, token_res = make_request("POST", "/auth/login", {"username": username, "password": password})
    assert status == 200, "User login failed."
    token = token_res["access_token"]
    print("    Access Token acquired successfully.")

    # Hacker User
    make_request("POST", "/auth/signup", {"username": hacker_username, "password": password, "role": "user"})
    status, hack_token_res = make_request("POST", "/auth/login", {"username": hacker_username, "password": password})
    hacker_token = hack_token_res["access_token"]

    # --- 2. Create Project ---
    print("[2] Creating a new project...")
    status, project = make_request("POST", "/projects", {"name": "AI Review Project"}, token=token)
    assert status == 201, f"Project creation failed with status {status}"
    project_id = project["id"]
    print(f"    Project created: '{project['name']}' (ID: {project_id})")

    # --- 3. Test Empty Analysis Rejection ---
    print("[3] Testing empty project analysis run rejection...")
    status, res = make_request("POST", f"/analysis/{project_id}/run", {"api_key": None}, token=token)
    assert status == 400, f"Expected 400 Bad Request, got {status}: {res}"
    print(f"    Correctly rejected empty analysis: {res['detail']}")

    # --- 4. Ingest Code files ---
    print("[4] Ingesting test script files...")
    paste_fields = {
        "pasted_filename": "process.py",
        "pasted_content": "def process_data(data):\n    eval(data)\n    print(data)\n    # TODO: add checks\n"
    }
    status, upload_res = make_multipart_request(f"/projects/{project_id}/upload", fields=paste_fields, token=token)
    assert status == 200, f"Upload failed: {upload_res}"
    print("    Test code uploaded successfully.")

    # --- 5. Start Analysis Run ---
    print("[5] Running AI Review analysis (mock simulation)...")
    status, run_info = make_request("POST", f"/analysis/{project_id}/run", {"api_key": None}, token=token)
    assert status == 201, f"Analysis trigger failed: {status}"
    analysis_id = run_info["id"]
    print(f"    Analysis run scheduled. ID: {analysis_id}, Status: {run_info['status']}")

    # --- 6. Poll Job Status ---
    print("[6] Polling analysis job status...")
    completed = False
    for attempt in range(8):
        time.sleep(1)
        status, poll_res = make_request("GET", f"/analysis/{analysis_id}", token=token)
        assert status == 200, "Polling failed"
        print(f"    Attempt {attempt+1}: Status is '{poll_res['status']}'")
        if poll_res["status"] == "completed":
            completed = True
            break
        elif poll_res["status"] == "failed":
            raise RuntimeError("Analysis task failed.")
            
    assert completed, "Analysis run did not complete in time."
    print(f"    Job completed successfully in {poll_res['duration']}s via {poll_res['model_used']}.")

    # --- 7. Fetch Analysis Report ---
    print("[7] Fetching quality review report details...")
    status, report = make_request("GET", f"/analysis/{analysis_id}/report", token=token)
    assert status == 200, f"Fetching report failed: {status}"
    assert report["analysis_id"] == analysis_id
    
    report_details = json.loads(report["details_json"])
    print(f"    Overall Score: {report_details['score']}/100")
    print(f"    Summary: {report_details['summary']}")
    print(f"    Strengths: {report_details['strengths']}")
    print(f"    Weaknesses: {report_details['weaknesses']}")
    
    # Assert issues are populated correctly (we uploaded process.py containing eval, print, and TODO)
    issues = report_details["issues"]
    print(f"    Detected issues count: {len(issues)}")
    assert len(issues) >= 3, f"Expected at least 3 issues (eval, print, TODO), found {len(issues)}"
    
    issue_categories = [iss["category"] for iss in issues]
    assert "Security" in issue_categories, "Should detect Security category for eval"
    assert "Style" in issue_categories, "Should detect Style category for print/TODO"
    print("    Issues normalized structure correctly parsed.")

    # --- 8. Security Guard Tests ---
    print("[8] Testing ownership checks (hacker access block)...")
    status, res = make_request("GET", f"/analysis/{analysis_id}", token=hacker_token)
    assert status == 404, f"Security Breach! Hacker can query analysis status: {res}"
    
    status, res = make_request("GET", f"/analysis/{analysis_id}/report", token=hacker_token)
    assert status == 404, f"Security Breach! Hacker can read report details: {res}"
    print("    All unauthorized routes blocked successfully (404 Not Found).")

    print()
    print("=========================================================")
    print("   ALL AI ANALYSIS VERIFICATIONS PASSED SUCCESSFULLY!    ")
    print("=========================================================")

if __name__ == "__main__":
    run_analysis_tests()
