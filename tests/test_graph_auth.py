import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth.database.connection import get_db
from app.auth.models.auth_models import User
from app.auth.services.auth_service import AuthService

client = TestClient(app)

@pytest.fixture
def db_session():
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def auth_headers(db_session):
    """Create a verified test user and return Authorization Bearer headers."""
    unique_username = f"graph_user_{uuid.uuid4().hex[:8]}"
    hashed_pwd = AuthService.hash_password("SecurePass123!")
    user = User(
        username=unique_username,
        hashed_password=hashed_pwd,
        role="developer",
        is_active=True,
        is_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    access_token, _, _, _ = AuthService.create_jwt_pair(user.id, user.role)
    headers = {"Authorization": f"Bearer {access_token}"}
    
    yield headers

    # Cleanup
    try:
        db_session.delete(user)
        db_session.commit()
    except Exception:
        db_session.rollback()


def test_graph_create_unauthenticated_returns_401():
    """Verify unauthenticated requests to /graph/create are rejected with 401."""
    # 1. No Authorization header
    res1 = client.post("/graph/create", json={"preset": "code_review"})
    assert res1.status_code == 401, f"Expected 401 without auth, got {res1.status_code}: {res1.text}"

    # 2. Invalid Bearer token
    res2 = client.post(
        "/graph/create",
        json={"preset": "code_review"},
        headers={"Authorization": "Bearer invalid_token_12345"}
    )
    assert res2.status_code == 401, f"Expected 401 with bad token, got {res2.status_code}: {res2.text}"


def test_graph_run_unauthenticated_returns_401():
    """Verify unauthenticated requests to /graph/run are rejected with 401."""
    # 1. No Authorization header
    res1 = client.post("/graph/run", json={"graph_id": "dummy-id", "initial_state": {}})
    assert res1.status_code == 401, f"Expected 401 without auth, got {res1.status_code}: {res1.text}"

    # 2. Invalid Bearer token
    res2 = client.post(
        "/graph/run",
        json={"graph_id": "dummy-id", "initial_state": {}},
        headers={"Authorization": "Bearer invalid_token_12345"}
    )
    assert res2.status_code == 401, f"Expected 401 with bad token, got {res2.status_code}: {res2.text}"


def test_graph_state_unauthenticated_returns_401():
    """Verify unauthenticated requests to /graph/state/{run_id} are rejected with 401."""
    # 1. No Authorization header
    res1 = client.get("/graph/state/dummy-run-id")
    assert res1.status_code == 401, f"Expected 401 without auth, got {res1.status_code}: {res1.text}"

    # 2. Invalid Bearer token
    res2 = client.get(
        "/graph/state/dummy-run-id",
        headers={"Authorization": "Bearer invalid_token_12345"}
    )
    assert res2.status_code == 401, f"Expected 401 with bad token, got {res2.status_code}: {res2.text}"


def test_graph_workflow_authenticated_succeeds(auth_headers):
    """Verify authenticated user can create graph, run workflow, and poll state."""
    # 1. /graph/create with valid auth
    create_res = client.post("/graph/create", json={"preset": "code_review"}, headers=auth_headers)
    assert create_res.status_code == 200, f"Expected 200, got {create_res.status_code}: {create_res.text}"
    graph_id = create_res.json().get("graph_id")
    assert graph_id, "Response did not contain graph_id"

    # 2. /graph/run with valid auth
    run_res = client.post(
        "/graph/run",
        json={
            "graph_id": graph_id,
            "initial_state": {
                "code": "def hello(): pass",
                "api_key": "",
                "threshold": 70,
                "model": "rule-based"
            }
        },
        headers=auth_headers
    )
    assert run_res.status_code == 200, f"Expected 200, got {run_res.status_code}: {run_res.text}"
    run_id = run_res.json().get("run_id")
    assert run_id, "Response did not contain run_id"

    # 3. /graph/state/{run_id} with valid auth
    state_res = client.get(f"/graph/state/{run_id}", headers=auth_headers)
    assert state_res.status_code == 200, f"Expected 200, got {state_res.status_code}: {state_res.text}"
    data = state_res.json()
    assert data["run_id"] == run_id
    assert "status" in data
    assert "logs" in data
    assert "state" in data


def test_graph_state_returns_404_for_other_user(auth_headers, db_session):
    """Verify that graph run state returns 404 when accessed by a different user."""
    # User 1 creates graph and runs workflow
    create_res = client.post("/graph/create", json={"preset": "code_review"}, headers=auth_headers)
    graph_id = create_res.json()["graph_id"]
    
    run_res = client.post(
        "/graph/run",
        json={"graph_id": graph_id, "initial_state": {"code": "x = 1"}},
        headers=auth_headers
    )
    run_id = run_res.json()["run_id"]

    # User 1 can access it
    owner_res = client.get(f"/graph/state/{run_id}", headers=auth_headers)
    assert owner_res.status_code == 200

    # Create User 2
    user2 = User(
        username=f"user2_{uuid.uuid4().hex[:8]}",
        hashed_password=AuthService.hash_password("Pass123!"),
        role="developer",
        is_active=True,
        is_verified=True
    )
    db_session.add(user2)
    db_session.commit()
    db_session.refresh(user2)

    try:
        user2_token, _, _, _ = AuthService.create_jwt_pair(user2.id, user2.role)
        user2_headers = {"Authorization": f"Bearer {user2_token}"}

        # User 2 attempts to fetch User 1's run state -> MUST return 404
        other_res = client.get(f"/graph/state/{run_id}", headers=user2_headers)
        assert other_res.status_code == 404, f"Expected 404 for other user, got {other_res.status_code}: {other_res.text}"
    finally:
        db_session.delete(user2)
        db_session.commit()


def test_graph_create_rejects_unknown_node_type(auth_headers):
    """Verify /graph/create rejects unknown node types or invalid presets with 400."""
    # 1. Unknown preset
    res1 = client.post("/graph/create", json={"preset": "arbitrary_eval_preset"}, headers=auth_headers)
    assert res1.status_code == 400, f"Expected 400 for unknown preset, got {res1.status_code}: {res1.text}"

    # 2. Unknown node type in graph_def dict
    bad_graph_def = {
        "nodes": {
            "extract": {"type": "extract"},
            "malicious_eval": {"type": "os_exec"}
        },
        "edges": {"extract": "malicious_eval"},
        "start": "extract"
    }
    res2 = client.post("/graph/create", json={"graph_def": bad_graph_def}, headers=auth_headers)
    assert res2.status_code == 400, f"Expected 400 for unknown node type, got {res2.status_code}: {res2.text}"
    assert "Unknown node type" in res2.text

    # 3. Known allowlisted node types succeed
    valid_graph_def = {
        "nodes": {
            "stub": {"type": "stub"}
        },
        "edges": {"stub": None},
        "start": "stub"
    }
    res3 = client.post("/graph/create", json={"graph_def": valid_graph_def}, headers=auth_headers)
    assert res3.status_code == 200, f"Expected 200 for valid graph_def, got {res3.status_code}: {res3.text}"
    assert "graph_id" in res3.json()
