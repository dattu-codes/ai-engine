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
        
    req_body = json.dumps(data).encode("utf-8") if data is not None else None
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


def create_codebase_a_zip() -> bytes:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("app/auth.py", """
def check_session(token):
    # Session handling credentials
    eval("arbitrary_string")
    pass
""")
        zf.writestr("app/db.py", """
# Database config helper
def get_db_connection():
    return "sqlite:///auth.db"
""")
    return zip_buffer.getvalue()


def create_codebase_b_zip() -> bytes:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("app/math.py", """
def calculate_sum(a, b):
    # Core mathematical operations
    return a + b
""")
    return zip_buffer.getvalue()


def read_sse_stream(project_id: int, message: str, token: str) -> str:
    url = f"{BASE_URL}/projects/{project_id}/chat"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    data = json.dumps({"message": message}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    
    full_text = ""
    has_done = False
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            for line in response:
                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue
                if line_str.startswith("data: "):
                    payload = line_str[6:].strip()
                    if payload == "[DONE]":
                        has_done = True
                        break
                    try:
                        chunk_data = json.loads(payload)
                        if "text" in chunk_data:
                            full_text += chunk_data["text"]
                    except Exception:
                        pass
    except Exception as e:
        print(f"Streaming failed: {e}")
        raise e
        
    return full_text


def run_tests():
    print("================================================================================")
    print("STARTING INTEGRATION TEST SUITE: INTELLECTUAL AI PROJECT CHAT")
    print("================================================================================")

    # STEP 1: Registration and Login
    print("\n[STEP 1] Registering and authenticating new test developer user...")
    timestamp = int(time.time())
    username = f"chat_dev_{timestamp}"
    password = "secure_chat_pass_123"
    
    st, _ = make_request("POST", "/auth/signup", {"username": username, "password": password, "role": "user"})
    assert st == 201, "Failed to register test developer user"
    
    st, token_res = make_request("POST", "/auth/login", {"username": username, "password": password})
    assert st == 200, "Failed to log in"
    token = token_res.get("access_token")
    assert token is not None, "Bearer token not found in response payload"
    print("Registration and authentication completed successfully!")

    # STEP 2: Project A allocation and baseline creation
    print("\n[STEP 2] Creating Project A container & ingesting Auth codebase ZIP...")
    st, proj_a = make_request("POST", "/projects", {"name": "Security Authentication Service"}, token=token)
    assert st == 201, "Failed to create Project A"
    proj_a_id = proj_a["id"]
    
    zip_a_data = create_codebase_a_zip()
    st, upload_res = make_multipart_request(
        f"/projects/{proj_a_id}/upload", 
        {}, 
        {"file": ("auth_service.zip", zip_a_data)}, 
        token=token
    )
    assert st == 200, "Ingestion of codebase ZIP A failed"
    print(f"Project A initialized with Node ID: {proj_a_id}")

    # STEP 3: Run review analysis on Project A
    print("\n[STEP 3] Running analysis on Project A baseline...")
    st, analysis_res = make_request("POST", f"/analysis/{proj_a_id}/run", {}, token=token)
    assert st == 201, "Failed to trigger analysis on Project A"
    analysis_id = analysis_res["id"]
    
    # Wait for analysis completion
    for _ in range(10):
        st, check_res = make_request("GET", f"/analysis/{analysis_id}", token=token)
        if check_res.get("status") == "completed":
            break
        time.sleep(1)
    print("Project A review analysis completed successfully!")

    # STEP 4: Test Streaming Project Chat (SSE response validation)
    print("\n[STEP 4] Executing Project Chat stream query to Project A...")
    question_a = "Explain the session mechanism and function names in auth.py"
    response_a = read_sse_stream(proj_a_id, question_a, token)
    print(f"Streamed Response:\n{response_a}")
    
    assert "check_session" in response_a or "auth.py" in response_a, "Response text should describe security structures"
    print("Streaming SSE chat query assertion passed!")

    # STEP 5: Verify persistent history and citations for Project A
    print("\n[STEP 5] Retrieving Chat History for Project A to verify database persistence & citations...")
    st, history_res = make_request("GET", f"/projects/{proj_a_id}/chat/history", token=token)
    assert st == 200, "Failed to fetch chat history"
    assert len(history_res) == 2, f"Expected 2 messages in history, got {len(history_res)}"
    
    user_msg = history_res[0]
    assistant_msg = history_res[1]
    
    assert user_msg["role"] == "user"
    assert user_msg["content"] == question_a
    
    assert assistant_msg["role"] == "assistant"
    # Verify citations are correctly extracted and persisted in DB
    ref_files = assistant_msg.get("referenced_files", [])
    ref_funcs = assistant_msg.get("referenced_functions", [])
    
    print(f"Citations extracted - Files: {ref_files}, Functions: {ref_funcs}")
    assert "app/auth.py" in ref_files, "Citations should include 'app/auth.py'"
    assert "check_session" in ref_funcs, "Citations should include 'check_session'"
    print("Database persistence and references citations validation passed successfully!")

    # STEP 6: Project B creation and isolation verification
    print("\n[STEP 6] Allocating Project B container and uploading Math codebase...")
    st, proj_b = make_request("POST", "/projects", {"name": "Mathematical Calculation Engine"}, token=token)
    assert st == 201, "Failed to create Project B"
    proj_b_id = proj_b["id"]
    
    zip_b_data = create_codebase_b_zip()
    st, upload_res_b = make_multipart_request(
        f"/projects/{proj_b_id}/upload", 
        {}, 
        {"file": ("math_engine.zip", zip_b_data)}, 
        token=token
    )
    assert st == 200, "Ingestion of codebase ZIP B failed"
    
    # Run analysis for Project B
    st, analysis_res_b = make_request("POST", f"/analysis/{proj_b_id}/run", {}, token=token)
    assert st == 201
    for _ in range(10):
        st, check_res_b = make_request("GET", f"/analysis/{analysis_res_b['id']}", token=token)
        if check_res_b.get("status") == "completed":
            break
        time.sleep(1)
    print(f"Project B initialized with Node ID: {proj_b_id}")

    # STEP 7: Assert Project isolation
    print("\n[STEP 7] Verifying Project Isolation (asserting histories & context do not cross-talk)...")
    
    # Assert Project B history is empty initially
    st, hist_b = make_request("GET", f"/projects/{proj_b_id}/chat/history", token=token)
    assert len(hist_b) == 0, "Project B chat history should be empty initially"
    
    # Send a query to Project B
    question_b = "Tell me about mathematics inside math.py"
    response_b = read_sse_stream(proj_b_id, question_b, token)
    print(f"Project B Streamed Response:\n{response_b}")
    
    assert "calculate_sum" in response_b or "math.py" in response_b, "Response should cite Math module structures"
    
    # Fetch Project B history and check citations
    st, hist_b = make_request("GET", f"/projects/{proj_b_id}/chat/history", token=token)
    assert len(hist_b) == 2, "Project B history should contain 2 messages"
    assert "app/math.py" in hist_b[1]["referenced_files"], "Project B citations should include app/math.py"
    assert "app/auth.py" not in hist_b[1]["referenced_files"], "Project B citations must not contain Project A files"
    
    # Re-verify Project A history is unaffected
    st, hist_a = make_request("GET", f"/projects/{proj_a_id}/chat/history", token=token)
    assert len(hist_a) == 2, "Project A history should remain exactly 2 messages"
    assert "app/auth.py" in hist_a[1]["referenced_files"]
    print("Project isolation and context separation verification passed successfully!")

    # STEP 8: Clear conversation history
    print("\n[STEP 8] Clearing conversation history for Project B...")
    st, clear_res = make_request("DELETE", f"/projects/{proj_b_id}/chat/history", token=token)
    assert st == 200
    
    st, hist_b_cleared = make_request("GET", f"/projects/{proj_b_id}/chat/history", token=token)
    assert len(hist_b_cleared) == 0, "Project B history should be empty after clear operation"
    
    st, hist_a_final = make_request("GET", f"/projects/{proj_a_id}/chat/history", token=token)
    assert len(hist_a_final) == 2, "Project A history should remain intact after Project B clear"
    print("History clear action and Project A conservation verified successfully!")

    print("\n================================================================================")
    print("ALL PROJECT CHAT INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("================================================================================")


if __name__ == "__main__":
    try:
        run_tests()
    except AssertionError as e:
        print(f"\nTEST SUITE CRITICAL FAILURE: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nTEST SUITE UNEXPECTED ERROR: {e}")
        sys.exit(1)
