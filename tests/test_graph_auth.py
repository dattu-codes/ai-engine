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
