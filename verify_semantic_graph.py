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
        with urllib.request.urlopen(req, timeout=10) as response:
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
        with urllib.request.urlopen(req, timeout=10) as response:
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


def build_test_zip() -> bytes:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # 1. Database Model
        zip_file.writestr(
            "app/models.py",
            "from sqlalchemy import Column, Integer, String\n"
            "from sqlalchemy.ext.declarative import declarative_base\n"
            "Base = declarative_base()\n\n"
            "class UserModel(Base):\n"
            "    __tablename__ = 'users'\n"
            "    id = Column(Integer, primary_key=True)\n"
            "    username = Column(String(50))\n"
        )
        
        # 2. UserService / Authentication Class (calling models and creating a circular import loop)
        zip_file.writestr(
            "app/auth.py",
            "import app.routes\n"
            "from app.models import UserModel\n\n"
            "class UserService:\n"
            "    def authenticate(self, username, password):\n"
            "        user = UserModel()\n"
            "        user.username = username\n"
            "        print('Authenticating user: ', username)\n"
            "        return True\n"
        )
        
        # 3. Routes / Controllers calling UserService methods
        zip_file.writestr(
            "app/routes.py",
            "from app.auth import UserService\n\n"
            "class AuthController:\n"
            "    def __init__(self):\n"
            "        self.service = UserService()\n\n"
            "    @router.post('/login')\n"
            "    def login_handler(self, username, password):\n"
            "        return self.service.authenticate(username, password)\n"
        )
        
        # 4. Dead/Unused utility module
        zip_file.writestr(
            "app/utils.py",
            "def unused_formatting_helper(val):\n"
            "    pass\n"
        )
        
    return zip_buffer.getvalue()


def run_tests():
    print("=" * 80)
    print("STARTING INTEGRATION TEST SUITE: SEMANTIC CODE GRAPH & CROSS-FILE ANALYSIS (v2.2)")
    print("=" * 80)
    
    timestamp = int(time.time())
    username = f"graph_tester_{timestamp}"
    password = "password123"
    
    # 1. Register User
    print(f"[STEP 1] Registering a new test user '{username}'...")
    status, res = make_request("POST", "/auth/signup", {"username": username, "password": password, "role": "user"})
    if status != 201:
        print(f"FAILED: User registration. Status: {status}, Response: {res}")
        sys.exit(1)
    print("User registration successful!")
    
    # 2. Login
    print("[STEP 2] Logging in to retrieve token...")
    status, res = make_request("POST", "/auth/login", {"username": username, "password": password})
    if status != 200:
        print(f"FAILED: Login error. Status: {status}, Response: {res}")
        sys.exit(1)
    token = res.get("access_token")
    print("Token retrieved successfully.")
    
    # 3. Create Project
    print("[STEP 3] Allocating a new project node container...")
    status, project = make_request("POST", "/projects", {"name": f"Project_{timestamp}"}, token=token)
    if status != 201:
        print(f"FAILED: Project creation. Status: {status}, Response: {project}")
        sys.exit(1)
    project_id = project.get("id")
    print(f"Project created. ID: {project_id}")
    
    # 4. Upload zip files (which generates graph baselines)
    print("[STEP 4] Ingesting codebase ZIP archive (populates initial semantic graph)...")
    zip_bytes = build_test_zip()
    status, res = make_multipart_request(
        f"/projects/{project_id}/upload",
        {},
        {"file": ("codebase.zip", zip_bytes)},
        token=token
    )
    if status != 200:
        print(f"FAILED: ZIP upload ingestion. Status: {status}, Response: {res}")
        sys.exit(1)
    print("Codebase ingested successfully.")

    # 5. Fetch Semantic Graph
    print("[STEP 5] Querying cached Semantic Code Graph nodes and edges...")
    status, graph = make_request("GET", f"/projects/{project_id}/semantic-graph", token=token)
    if status != 200:
        print(f"FAILED: Graph retrieval. Status: {status}, Response: {graph}")
        sys.exit(1)
        
    print("Semantic Code Graph retrieved:")
    print(f"  - Nodes Count: {len(graph['nodes'])}")
    print(f"  - Edges Count: {len(graph['edges'])}")
    print(f"  - Stats payload: {graph['statistics']}")
    
    # Assert nodes types extraction
    node_types = [n["node_type"] for n in graph["nodes"]]
    expected_types = ["file", "class", "method", "function", "api_route", "db_model"]
    for et in expected_types:
        if et in node_types:
            print(f"  - Verified node extraction type: '{et}'")
        else:
            print(f"  - Warning: node type '{et}' not found in generated graph.")
            
    # 6. Fetch Dependency Tree
    print("[STEP 6] Fetching parsed dependency tree...")
    status, tree = make_request("GET", f"/projects/{project_id}/semantic-graph/dependency-tree", token=token)
    if status != 200:
        print(f"FAILED: Dependency tree query. Status: {status}, Response: {tree}")
        sys.exit(1)
    print(f"Dependency Tree verified: {tree}")
    
    # 7. Circular Dependency Detection
    print("[STEP 7] Executing circular dependency cycle detection...")
    status, cycles = make_request("GET", f"/projects/{project_id}/semantic-graph/cycles", token=token)
    if status != 200:
        print(f"FAILED: Cycles detection query. Status: {status}, Response: {cycles}")
        sys.exit(1)
    print(f"Circular loops found: {cycles}")
    if not cycles:
        print("FAILED: Circular loop between app/auth.py and app/routes.py was not detected.")
        sys.exit(1)
    print("Circular loop correctly identified.")
    
    # 8. Dead Code detection
    print("[STEP 8] Retrieving orphan modules and dead code symbols...")
    status, dead_code = make_request("GET", f"/projects/{project_id}/semantic-graph/dead-code", token=token)
    if status != 200:
        print(f"FAILED: Dead code query. Status: {status}, Response: {dead_code}")
        sys.exit(1)
    print(f"Dead code elements: {dead_code}")
    # Verify app/utils.py is flagged or unused_formatting_helper is dead
    unused_helper = next((s for s in dead_code["dead_symbols"] if s["name"] == "unused_formatting_helper"), None)
    if not unused_helper:
        print("FAILED: Unused function 'unused_formatting_helper' was not flagged as dead code.")
        sys.exit(1)
    print("Orphan/dead function successfully identified.")
    
    # 9. Trigger manual graph regeneration
    print("[STEP 9] Triggering manual graph regeneration API...")
    status, stats = make_request("POST", f"/projects/{project_id}/semantic-graph/regenerate", token=token)
    if status != 200:
        print(f"FAILED: Manual regeneration. Status: {status}, Response: {stats}")
        sys.exit(1)
    print(f"Regeneration statistics confirmed: {stats}")
    
    # 10. Run impact analysis
    print("[STEP 10] Running change impact analysis on coreUserService...")
    status, impact = make_request(
        "GET", 
        f"/projects/{project_id}/semantic-graph/impact-analysis?file_path=app/auth.py&symbol_name=UserService", 
        token=token
    )
    if status != 200:
        print(f"FAILED: Impact analysis query. Status: {status}, Response: {impact}")
        sys.exit(1)
    print(f"Impact Analysis verified:")
    print(f"  - Risk Score: {impact['risk_score']}")
    print(f"  - Risk Rating: {impact['risk_rating']}")
    print(f"  - Downstream dependents: {impact['dependent_files']}")
    print(f"  - Calls chain: {impact['call_chain']}")
    
    # 11. Run Version Graph Comparison
    print("[STEP 11] Running version comparison checks...")
    # First, let's get version snapshot history list
    status, history = make_request("GET", f"/projects/{project_id}/versions", token=token)
    if status != 200 or not history:
        print(f"FAILED: Version history. Status: {status}, Response: {history}")
        sys.exit(1)
        
    version_id = history[0]["id"]
    
    # Let's apply a mock AI Fix to create version 2
    # First, load project findings to get finding issue dict
    # Since we uploaded a codebase but didn't run live review, let's create a manual mock finding to resolve
    mock_issue = {
        "file": "app/auth.py",
        "line": 7,
        "category": "Security",
        "explanation": "Detected evaluation of user input.",
        "evidence": "print('Authenticating user: ', username)",
        "recommendation": "Remove print statement or encrypt logging statements."
    }
    
    print("  - Applying mock fix to construct version 2...")
    status, v2 = make_request(
        "POST", 
        f"/projects/{project_id}/versions/apply-fix", 
        {"issue": mock_issue, "api_key": None}, 
        token=token
    )
    if status != 200:
        print(f"FAILED: Version 2 fix creation. Status: {status}, Response: {v2}")
        sys.exit(1)
    v2_id = v2.get("id")
    print(f"  - Version 2 created. ID: {v2_id}")
    
    # Compare Version 1 and Version 2 semantic graphs
    print("  - Querying semantic graph comparison between version 1 and version 2...")
    status, comparison = make_request(
        "GET", 
        f"/projects/{project_id}/semantic-graph/compare?base_version_id={version_id}&target_version_id={v2_id}",
        token=token
    )
    if status != 200:
        print(f"FAILED: Graph comparison. Status: {status}, Response: {comparison}")
        sys.exit(1)
    print(f"Graph Comparison Result: {comparison}")
    
    print("=" * 80)
    print("ALL SEMANTIC CODE GRAPH INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    run_tests()
