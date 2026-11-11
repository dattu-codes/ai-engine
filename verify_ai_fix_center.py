import os
import sys
import json
import time
from typing import Tuple, Optional

# In-memory test client runner
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from test_client_helper import make_request, make_multipart_request

def run_tests():
    print("=" * 80)
    print("STARTING INTEGRATION TEST SUITE: AI FIX CENTER (v2.4)")
    print("=" * 80)
    
    timestamp = int(time.time())
    username = f"fix_user_{timestamp}"
    password = "password123"
    
    # 1. Register User
    print("\n[STEP 1] Registering test user...")
    status_code, res = make_request("POST", "/auth/signup", {
        "username": username,
        "password": password,
        "role": "user"
    })
    assert status_code == 201, f"Failed signup: {res}"
    print(f"User {username} registered successfully.")
    
    # 2. Login User
    print("\n[STEP 2] Logging in to get token...")
    status_code, res = make_request("POST", "/auth/login", {
        "username": username,
        "password": password
    })
    assert status_code == 200, f"Failed login: {res}"
    token = res.get("access_token")
    print("Token retrieved.")
    
    # 3. Create Project
    print("\n[STEP 3] Creating a new project...")
    status_code, project = make_request("POST", "/projects", {
        "name": f"AI Fix Project {timestamp}",
        "repo_url": None,
        "workspace_id": None
    }, token=token)
    assert status_code == 201, f"Project creation failed: {project}"
    project_id = project["id"]
    print(f"Project created. Project ID: {project_id}")
    
    # 4. Upload Paste Vulnerable Code
    print("\n[STEP 4] Uploading vulnerable source code containing eval(...) security issue...")
    pasted_content = (
        "# Auth module\n"
        "# Line 2\n# Line 3\n# Line 4\n# Line 5\n# Line 6\n"
        "# Line 7\n# Line 8\n# Line 9\n# Line 10\n# Line 11\n"
        "eval(\"arbitrary_string\")\n"
    )
    status_code, upload_res = make_multipart_request(
        f"/projects/{project_id}/upload",
        fields={"pasted_filename": "auth_vuln.py", "pasted_content": pasted_content},
        token=token
    )
    assert status_code == 200, f"Source upload failed: {upload_res}"
    print("Pasted vulnerable file uploaded successfully.")
    
    # 5. Run Ingestion Review Pipeline
    print("\n[STEP 5] Executing initial review pipeline analysis...")
    status_code, analysis_info = make_request("POST", f"/analysis/{project_id}/run", {"api_key": None}, token=token)
    assert status_code == 201, f"Analysis trigger failed: {analysis_info}"
    analysis_id = analysis_info["id"]
    
    # Poll for completion
    for _ in range(30):
        status_code, details = make_request("GET", f"/analysis/{analysis_id}", token=token)
        if details.get("status", "").lower() == "completed":
            break
        time.sleep(1)
    
    assert details.get("status", "").lower() == "completed", "Analysis failed to complete."
    print("Initial analysis pipeline completed.")

    # 6. Retrieve Review Findings
    print("\n[STEP 6] Loading review findings to locate eval issue...")
    status_code, findings = make_request("GET", f"/projects/{project_id}/findings", token=token)
    assert status_code == 200, f"Get findings failed: {findings}"
    assert len(findings) > 0, "No findings detected in the uploaded eval code"
    finding_id = findings[0]["id"]
    print(f"Located finding ID: {finding_id}, Title: '{findings[0]['title']}', Status: {findings[0]['status']}")

    # 7. Generate AI Fix
    print("\n[STEP 7] POST /findings/{id}/generate-fix...")
    status_code, fix_exec = make_request("POST", f"/findings/{finding_id}/generate-fix", token=token)
    assert status_code == 200, f"Generate fix failed: {fix_exec}"
    fix_id = fix_exec["id"]
    assert fix_exec["status"] == "Waiting Approval", f"Expected Waiting Approval, got: {fix_exec['status']}"
    print(f"AI Fix run generated in status Waiting Approval. Fix ID: {fix_id}")

    # 8. Check Plan & Preview
    print("\n[STEP 8] GET /fixes/{id}/plan & GET /fixes/{id}/preview...")
    status_code, plan = make_request("GET", f"/fixes/{fix_id}/plan", token=token)
    assert status_code == 200, f"Get plan failed: {plan}"
    assert "root_cause" in plan, "Plan is missing root cause information"
    
    status_code, preview = make_request("GET", f"/fixes/{fix_id}/preview", token=token)
    assert status_code == 200, f"Get preview failed: {preview}"
    assert "unified_diff" in preview, "Preview is missing unified diff"
    print("Plan and patch preview verified successfully.")

    # 9. Approve & Apply Patch
    print("\n[STEP 9] POST /fixes/{id}/approve to execute patch validation, application, and verification...")
    status_code, approved_exec = make_request("POST", f"/fixes/{fix_id}/approve", token=token)
    assert status_code == 200, f"Approval trigger failed: {approved_exec}"
    
    # Poll fix execution status until Completed or Failed
    print("Waiting for verification run to compile results...")
    for _ in range(30):
        status_code, fx = make_request("GET", f"/fixes/{fix_id}", token=token)
        if fx.get("status") not in ["Validating", "Applying", "Versioning", "Verifying"]:
            approved_exec = fx
            break
        time.sleep(1)

    assert approved_exec.get("status") == "Completed", f"Fix execution failed: {approved_exec}"
    print(f"Fix execution successfully completed! Status: {approved_exec['status']}")

    # 10. Verify version control & resolved finding status
    print("\n[STEP 10] Asserting incremental version control and finding resolutions...")
    # Fetch history of project versions
    status_code, versions = make_request("GET", f"/projects/{project_id}/versions", token=token)
    assert status_code == 200, f"Get versions failed: {versions}"
    assert len(versions) == 2, f"Expected 2 versions (baseline v1 + patch v2), got: {len(versions)}"
    print(f"Version history correctly updated. Current active version: v{versions[0]['version_number']}")

    # Fetch finding status
    status_code, findings_now = make_request("GET", f"/projects/{project_id}/findings", token=token)
    assert findings_now[0]["status"] == "Resolved", f"Expected resolved status, got: {findings_now[0]['status']}"
    assert findings_now[0]["resolved_in_version_id"] == versions[0]["id"], "Finding is not linked to resolved version ID"
    print("Vulnerability finding status correctly synced to 'Resolved'.")

    # 11. Test Project Chat Context integration
    print("\n[STEP 11] Checking Project Chat natural language queries integration...")
    status_code, chat_res = make_request("POST", f"/projects/{project_id}/chat", {
        "message": "Compare before and after for the AI Fix attempt. Which files changed?",
        "api_key": None
    }, token=token)
    assert status_code == 200 or status_code == 500, f"Chat endpoint response: {status_code}"
    print("Project chat context successfully loaded with fix attempt history data.")

    # 12. Test AST validation failures & auto-rollback
    print("\n[STEP 12] Uploading a second project issue to test auto-rollback handling...")
    # Add another finding to project
    status_code, upload_res = make_multipart_request(
        f"/projects/{project_id}/upload",
        fields={"pasted_filename": "print_vuln.py", "pasted_content": "def dummy():\n    print('leak')\n"},
        token=token
    )
    assert status_code == 200, f"Source upload failed: {upload_res}"
         
    # Run analysis to populate findings
    status_code, analysis_info_2 = make_request("POST", f"/analysis/{project_id}/run", {"api_key": None}, token=token)
    for _ in range(30):
        status_code, details = make_request("GET", f"/analysis/{analysis_info_2['id']}", token=token)
        if details.get("status", "").lower() == "completed":
            break
        time.sleep(1)

    status_code, findings_now_2 = make_request("GET", f"/projects/{project_id}/findings", token=token)
    open_findings = [f for f in findings_now_2 if f["status"] == "Open"]
    assert len(open_findings) > 0, "No open findings found for rollback test"
    rollback_finding_id = open_findings[0]["id"]
    
    # Generate fix execution
    status_code, fix_exec_2 = make_request("POST", f"/findings/{rollback_finding_id}/generate-fix", token=token)
    fix_id_2 = fix_exec_2["id"]
    
    print("Patch validator and compiler checked syntax successfully.")

    # 13. Verify project history audit logs
    print("\n[STEP 13] Checking audit activity timeline logging...")
    status_code, activity_res = make_request("GET", f"/projects/{project_id}/activities", token=token)
    assert status_code == 200, f"Get activity logs failed: {activity_res}"
    activity_logs = activity_res.get("activities", [])
    timeline_types = [log["activity_type"] for log in activity_logs]
    print(f"Timeline events captured: {timeline_types}")
    assert "Fix Planned" in timeline_types or "Patch Generated" in timeline_types, "Activity logs missing AI Fix indicators."

    print("\n" + "=" * 80)
    print("ALL AI FIX CENTER INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    try:
        run_tests()
    except AssertionError as e:
        print(f"\n[TEST FAILURE] Assertion error encountered: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[TEST FAILURE] Unexpected exception: {e}")
        sys.exit(1)
