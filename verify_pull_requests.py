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
    print("STARTING INTEGRATION TEST SUITE: PULL REQUEST AUDITS & CI/CD MANUAL PORTAL")
    print("=" * 80)
    
    timestamp = int(time.time())
    username = f"pr_tester_{timestamp}"
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
    
    # 3. Create Project Node linked to Mock repo URL
    print("\n[STEP 3] Allocating a new project node linked to a mock GitHub repo...")
    status_code, project = make_request("POST", "/projects", {
        "name": f"Mock PR Test Project {timestamp}",
        "repo_url": "https://github.com/dattu-codes/ai-engine-intern.git"
    }, token=token)
    assert status_code == 201, f"Failed project creation: {project}"
    project_id = project["id"]
    print(f"Project created. Node ID: {project_id}")

    # 4. Trigger review for PR 15 (Mock fallback)
    print("\n[STEP 4] Triggering Pull Request #15 review via manual audit portal...")
    status_code, pr_info = make_request("POST", f"/projects/{project_id}/pull-requests/review", {
        "pull_request_number": 15
    }, token=token)
    assert status_code == 201, f"PR Trigger failed: {pr_info}"
    
    pr_id = pr_info["id"]
    latest_analysis_id = pr_info["latest_analysis_id"]
    assert pr_id, "Missing pull request ID"
    assert latest_analysis_id, "Missing analysis run ID"
    print(f"Manual PR Review enqueued! PR DB ID: {pr_id}, Analysis ID: {latest_analysis_id}")

    # 5. Poll for review analysis completion
    print("\n[STEP 5] Polling status for PR review completion...")
    completed = False
    for i in range(15):
        status_code, analysis = make_request("GET", f"/analysis/{latest_analysis_id}", token=token)
        assert status_code == 200, f"Failed loading analysis: {analysis}"
        
        status = analysis["status"]
        print(f"  Attempt {i+1}: Analysis status is '{status}'")
        if status == "completed":
            completed = True
            break
        elif status == "failed":
            raise RuntimeError("Analysis pipeline execution failed.")
        time.sleep(1)
    
    assert completed, "PR review pipeline analysis failed to complete in time."
    print("PR Analysis completed successfully!")

    # 6. Verify PR metadata details via List endpoint
    print("\n[STEP 6] Listing project pull requests to verify metadata fields...")
    status_code, pr_list = make_request("GET", f"/projects/{project_id}/pull-requests", token=token)
    assert status_code == 200, f"Failed listing PRs: {pr_list}"
    assert len(pr_list) > 0, "No PRs listed in history"
    
    pr = [p for p in pr_list if p["id"] == pr_id][0]
    assert pr["github_pr_number"] == 15
    assert pr["author"] == "security_engineer"
    assert pr["title"] == "Resolve session vulnerability in auth.py"
    assert pr["base_branch"] == "main"
    assert pr["head_branch"] == "feature/fix-auth"
    assert pr["files_changed"] == 1
    assert pr["additions"] == 2
    assert pr["deletions"] == 1
    assert pr["commits"] == 1
    assert pr["latest_analysis_id"] == latest_analysis_id
    
    # Check that historical timeline is returned in the response
    assert len(pr["analyses"]) > 0, "Timeline run list missing"
    assert pr["analyses"][0]["id"] == latest_analysis_id
    assert pr["analyses"][0]["score"] is not None, "Pipeline score missing from timeline item"
    print("Pull Request metadata verified successfully!")

    # 7. Get PR Details
    print("\n[STEP 7] Fetching details for the Pull Request...")
    status_code, details = make_request("GET", f"/pull-requests/{pr_id}", token=token)
    assert status_code == 200, f"Failed getting details: {details}"
    assert details["github_pr_number"] == 15
    print("Pull Request detail lookup verified.")

    # 8. Fetch PR Summary Details
    print("\n[STEP 8] Retrieving PR audit score card and executive summary...")
    status_code, summary = make_request("GET", f"/pull-requests/{pr_id}/summary", token=token)
    assert status_code == 200, f"Failed getting summary: {summary}"
    assert summary["score"] is not None, "PR score field missing"
    assert summary["summary"], "Executive summary missing"
    assert summary["risk_assessment"] in ["critical", "high", "medium", "low"], f"Invalid risk level: {summary['risk_assessment']}"
    print(f"PR Score Card: {summary['score']}/100 | Risk: {summary['risk_assessment'].upper()}")
    print(f"Summary: {summary['summary']}")

    # 9. Fetch PR findings and security recommendations
    print("\n[STEP 9] Fetching PR review findings...")
    status_code, findings = make_request("GET", f"/pull-requests/{pr_id}/findings", token=token)
    assert status_code == 200, f"Failed getting findings: {findings}"
    assert len(findings) > 0, "Expected findings to be generated for mock PR"
    
    # Check structure
    finding = findings[0]
    assert finding["file"], "Finding missing file path"
    assert finding["category"], "Finding missing category"
    assert finding["severity"], "Finding missing severity"
    assert finding["explanation"], "Finding missing explanation"
    print(f"Found {len(findings)} review issues. First: {finding['category']} in {finding['file']} (Severity: {finding['severity']})")

    # 10. Refresh PR metadata
    print("\n[STEP 10] Triggering Pull Request metadata refresh...")
    status_code, refreshed = make_request("POST", f"/pull-requests/{pr_id}/refresh", token=token)
    assert status_code == 200, f"Refresh failed: {refreshed}"
    assert refreshed["github_pr_number"] == 15, "Refresh modified PR number"
    print("PR metadata refreshed successfully.")

    # 11. Trigger re-review
    print("\n[STEP 11] Triggering a re-review on the Pull Request...")
    status_code, re_reviewed = make_request("POST", f"/pull-requests/{pr_id}/review-again", token=token)
    assert status_code == 200, f"Re-review trigger failed: {re_reviewed}"
    
    new_analysis_id = re_reviewed["latest_analysis_id"]
    assert new_analysis_id != latest_analysis_id, "Did not launch a new analysis run"
    print(f"Re-review enqueued. New Analysis Run ID: {new_analysis_id}")
    
    # Poll re-review completion
    print("Waiting for re-review completion...")
    completed = False
    for i in range(15):
        status_code, analysis = make_request("GET", f"/analysis/{new_analysis_id}", token=token)
        if analysis["status"] == "completed":
            completed = True
            break
        elif analysis["status"] == "failed":
            raise RuntimeError("Re-review analysis failed.")
        time.sleep(1)
        
    assert completed, "Re-review failed to complete."
    print("Re-review analysis completed successfully!")

    # Verify timeline is now updated to show both runs
    status_code, updated_pr = make_request("GET", f"/pull-requests/{pr_id}", token=token)
    assert status_code == 200
    timeline_ids = [a["id"] for a in updated_pr["analyses"]]
    assert latest_analysis_id in timeline_ids, "Original run disappeared from timeline"
    assert new_analysis_id in timeline_ids, "New run missing from timeline"
    print(f"Timeline updated. Runs list: {timeline_ids}")

    print("\n" + "=" * 80)
    print("ALL PULL REQUEST INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        run_tests()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n[TEST FAILURE] Assertion error encountered: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[TEST FAILURE] Unexpected exception: {e}")
        sys.exit(1)
