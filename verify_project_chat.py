import os
import sys
import json
import time
import io
import zipfile
from typing import Tuple, Optional

# In-memory test client runner
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from test_client_helper import make_request, make_multipart_request, client


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
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    resp = client.post(f"/projects/{project_id}/chat", json={"message": message}, headers=headers)
    full_text = ""
    for line in resp.iter_lines():
        line_str = line.strip()
        if not line_str:
            continue
        if line_str.startswith("data: "):
            payload = line_str[6:].strip()
            if payload == "[DONE]":
                break
            try:
                chunk_data = json.loads(payload)
                if "text" in chunk_data:
                    full_text += chunk_data["text"]
            except Exception:
                pass
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
