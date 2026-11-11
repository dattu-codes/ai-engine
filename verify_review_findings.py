import os
import sys
import json
import time
import io
import zipfile
from typing import Tuple, Optional

# In-memory test client runner
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from test_client_helper import make_request, make_multipart_request


def create_test_zip() -> bytes:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "app/auth.py",
            "def check_session(token):\n    eval(\"arbitrary_string\")\n" + "\n" * 12 + "    pass\n"
        )
        zf.writestr(
            "app/utils.py",
            "def debug_log(val):\n    print(val)\n"
        )
    return zip_buffer.getvalue()


def run_tests():
    print("=" * 80)
    print("STARTING INTEGRATION TEST SUITE: REVIEW QUALITY CENTER (v2.1)")
    print("=" * 80)

    # STEP 1: Registration
    username = f"tester_{int(time.time())}"
    print(f"[STEP 1] Registering a new test user '{username}'...")
    st, resp = make_request("POST", "/auth/signup", {
        "username": username,
        "password": "testpassword123",
        "role": "user"
    })
    assert st == 201, f"User registration failed: {resp}"
    print("User registration successful!")

    # STEP 2: Login
    print("[STEP 2] Logging in to retrieve token...")
    st, resp = make_request("POST", "/auth/login", {
        "username": username,
        "password": "testpassword123"
    })
    assert st == 200, f"Login failed: {resp}"
    token = resp.get("access_token")
    assert token, "Access token not found in login response"
    print("Token retrieved successfully.")

    # STEP 3: Create Project
    print("[STEP 3] Allocating a new project node...")
    st, resp = make_request("POST", "/projects", {
        "name": "Quality Center Test Project",
        "repo_url": None
    }, token)
    assert st == 201, f"Project creation failed: {resp}"
    project_id = resp.get("id")
    print(f"Project created. ID: {project_id}")

    # STEP 4: Ingest codebase
    print("[STEP 4] Ingesting codebase ZIP archive (creates initial findings)...")
    zip_data = create_test_zip()
    st, resp = make_multipart_request(
        f"/projects/{project_id}/upload",
        {},
        {"file": ("project.zip", zip_data)},
        token
    )
    assert st == 200, f"Zip ingestion failed: {resp}"
    print("Codebase ingested successfully.")

    # STEP 5: Run AI review pipeline
    print("[STEP 5] Running review pipeline analysis to detect findings...")
    st, resp = make_request("POST", f"/analysis/{project_id}/run", {}, token)
    assert st == 201, f"Review trigger failed: {resp}"
    analysis_id = resp.get("id")
    
    # Poll analysis completion
    print("Polling analysis completion...")
    for _ in range(10):
        st, resp = make_request("GET", f"/analysis/{analysis_id}", {}, token)
        if resp.get("status") in ["completed", "failed"]:
            break
        time.sleep(1)
        
    assert resp.get("status") == "completed", f"Analysis failed: {resp}"
    print("AI Review analysis completed successfully.")

    # STEP 6: Query Findings Explorer
    print("[STEP 6] Fetching persisted Review Findings...")
    st, resp = make_request("GET", f"/projects/{project_id}/findings", {}, token)
    assert st == 200, f"Failed to fetch findings: {resp}"
    findings = resp
    assert len(findings) > 0, "No findings created in database"
    print(f"Verified {len(findings)} Review Findings successfully created. Content: {json.dumps(findings, indent=2)}")

    # STEP 7: Verify finding detail and metadata fields
    finding = findings[0]
    finding_id = finding["id"]
    print(f"[STEP 7] Verifying detailed fields for finding ID {finding_id}...")
    st, resp = make_request("GET", f"/findings/{finding_id}", {}, token)
    assert st == 200, f"Failed to get finding detail: {resp}"
    assert resp["project_id"] == project_id
    assert resp["status"] == "Open"
    assert resp["file_path"] in ["app/auth.py", "app/utils.py"]
    print("Finding detailed fields verified successfully.")

    # STEP 8: Status transitions (In Progress)
    print("[STEP 8] Transitioning finding status to 'In Progress'...")
    st, resp = make_request("PATCH", f"/findings/{finding_id}/status", {"status": "In Progress"}, token)
    assert st == 200, f"Failed to transition status: {resp}"
    assert resp["status"] == "In Progress"
    print("Status transition verified.")

    # STEP 9: Reassign Finding
    print("[STEP 9] Reassigning finding assignee...")
    st, resp = make_request("PATCH", f"/findings/{finding_id}/assign", {"assigned_to": "dattu"}, token)
    assert st == 200, f"Failed to assign finding: {resp}"
    assert resp["assigned_to"] == "dattu"
    print("Assignee update verified.")

    # STEP 10: Ignore Finding (with reason override)
    print("[STEP 10] Overriding finding with Ignore override and comment reason...")
    st, resp = make_request("PATCH", f"/findings/{finding_id}/ignore", {"reason": "Accepted test risk"}, token)
    assert st == 200, f"Failed to ignore finding: {resp}"
    assert resp["status"] == "Ignored"
    assert resp["ignored_reason"] == "Accepted test risk"
    print("Ignore override and reason validated successfully.")

    # STEP 11: Reopen Finding
    print("[STEP 11] Reopening finding back to Open status...")
    st, resp = make_request("PATCH", f"/findings/{finding_id}/reopen", {}, token)
    assert st == 200, f"Failed to reopen finding: {resp}"
    assert resp["status"] == "Open"
    assert resp["ignored_reason"] is None
    print("Reopen flow validated successfully.")

    # STEP 12: Run another review (deduplication/no-duplication check)
    print("[STEP 12] Re-running review analysis to verify duplicate avoidance...")
    st, resp = make_request("POST", f"/analysis/{project_id}/run", {}, token)
    assert st == 201, f"Review trigger failed: {resp}"
    analysis_id2 = resp.get("id")
    
    for _ in range(10):
        st, resp = make_request("GET", f"/analysis/{analysis_id2}", {}, token)
        if resp.get("status") in ["completed", "failed"]:
            break
        time.sleep(1)
        
    assert resp.get("status") == "completed"
    
    # Query findings list count again
    st, resp = make_request("GET", f"/projects/{project_id}/findings", {}, token)
    assert len(resp) == len(findings), f"Duplicate findings created! Expected {len(findings)} but got {len(resp)}"
    print("Deduplication and match-merging verified successfully.")

    # STEP 13: Apply AI Fix integration (resolves finding and links Version)
    print("[STEP 13] Applying AI Fix to resolve a finding...")
    target_finding = None
    for f in resp:
        if f["file_path"] == "app/auth.py":
            target_finding = f
            break
    assert target_finding, "Vulnerable file auth.py finding not found"

    issue_data = {
        "file": target_finding["file_path"],
        "line": target_finding["line_number"],
        "category": target_finding["category"],
        "severity": target_finding["severity"],
        "explanation": target_finding["description"],
        "recommendation": target_finding["recommendation"],
        "evidence": target_finding["title"]
    }
    
    st, resp = make_request("POST", f"/projects/{project_id}/versions/apply-fix", {
        "issue": issue_data
    }, token)
    assert st == 200, f"Apply fix failed: {resp}"
    new_version_id = resp["id"]
    
    # Verify the finding status got resolved automatically
    st, resp = make_request("GET", f"/findings/{target_finding['id']}", {}, token)
    assert resp["status"] == "Resolved", f"Finding should be Resolved but got: {resp['status']}"
    print(f"DEBUG: finding resolved_in_version_id = {resp['resolved_in_version_id']}, new_version_id = {new_version_id}")
    assert resp["resolved_in_version_id"] == new_version_id
    assert resp["resolved_at"] is not None
    print("AI Fix auto-resolution and version linkage verified successfully.")

    # STEP 14: History Timeline retrieval
    print("[STEP 14] Querying findings resolution history timeline...")
    st, resp = make_request("GET", f"/projects/{project_id}/findings/history", {}, token)
    assert st == 200, f"Failed to fetch history: {resp}"
    assert len(resp) > 0, "Resolved findings not found in history timeline"
    print("Findings history verification successful.")

    # STEP 15: Pull Request review findings update
    print("[STEP 15] Triggering a PR review to verify incremental findings sync...")
    # Add a mock Pull Request record
    st, resp = make_request("POST", f"/projects/{project_id}/pull-requests/review", {
        "pull_request_number": 22
    }, token)
    assert st == 201, f"PR review trigger failed: {resp}"
    pr_id = resp["id"]
    
    # Poll status
    for _ in range(10):
        st, resp = make_request("GET", f"/pull-requests/{pr_id}", {}, token)
        if resp.get("latest_analysis_id"):
            anal_id = resp["latest_analysis_id"]
            st2, resp2 = make_request("GET", f"/analysis/{anal_id}", {}, token)
            if resp2.get("status") in ["completed", "failed"]:
                break
        time.sleep(1)
        
    st, resp = make_request("GET", f"/projects/{project_id}/findings", {}, token)
    assert len(resp) >= len(findings), "PR review should sync and merge findings without duplicate creations"
    print("Pull Request review findings integration verified successfully.")

    print("=" * 80)
    print("ALL REVIEW QUALITY CENTER INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()
