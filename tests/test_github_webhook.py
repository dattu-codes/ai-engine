import hmac
import hashlib
import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.auth.database.connection import get_db, Base, engine
from app.auth.models.auth_models import User
from app.projects.models.project_models import Project

client = TestClient(app)

@pytest.fixture
def db_session():
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()

def test_webhook_fails_closed_when_secret_empty():
    """Verify webhook rejects requests with 401 when GITHUB_WEBHOOK_SECRET is empty/missing."""
    original_secret = settings.GITHUB_WEBHOOK_SECRET
    settings.GITHUB_WEBHOOK_SECRET = ""
    try:
        payload = {"ref": "refs/heads/main", "repository": {"clone_url": "https://github.com/org/repo"}}
        
        # Unsigned request
        resp1 = client.post("/projects/github/webhook", json=payload)
        assert resp1.status_code == 401, f"Expected 401 when secret is empty, got {resp1.status_code}"
        
        # Even with a purported signature header, it must fail closed
        resp2 = client.post(
            "/projects/github/webhook",
            json=payload,
            headers={"X-Hub-Signature-256": "sha256=d3adb33f"}
        )
        assert resp2.status_code == 401, f"Expected 401 when secret is empty, got {resp2.status_code}"
    finally:
        settings.GITHUB_WEBHOOK_SECRET = original_secret

def test_webhook_handles_malformed_signatures_without_crashing():
    """Verify malformed, corrupted, or non-sha256 signatures return 401 and never cause 500 crashes."""
    original_secret = settings.GITHUB_WEBHOOK_SECRET
    settings.GITHUB_WEBHOOK_SECRET = "secure_test_secret_key"
    try:
        payload = {"ref": "refs/heads/main", "repository": {"clone_url": "https://github.com/org/repo"}}
        raw_body = json.dumps(payload).encode("utf-8")

        malformed_headers = [
            None,                                           # Missing header
            "",                                             # Empty string
            "sha256",                                       # Missing = separator
            "sha1=abcdef",                                  # Insecure/wrong algorithm
            "md5=abcdef",                                   # Unsupported algorithm
            "sha256=",                                      # Empty value after =
            "sha256=invalid-non-hex-characters!@#$%",       # Non-hex characters
            "sha256=12345",                                 # Truncated hash
            "=sha256",                                      # Missing prefix
            "sha256=0000000000000000000000000000000000000000000000000000000000000000"  # Valid format, wrong signature
        ]

        for sig in malformed_headers:
            headers = {"Content-Type": "application/json"}
            if sig is not None:
                headers["X-Hub-Signature-256"] = sig

            resp = client.post("/projects/github/webhook", content=raw_body, headers=headers)
            assert resp.status_code == 401, f"Malformed signature '{sig}' resulted in status {resp.status_code}, expected 401"
    finally:
        settings.GITHUB_WEBHOOK_SECRET = original_secret

def test_webhook_no_fallback_to_project_first(db_session):
    """Verify unmatched repository URL returns ignored status and does NOT fall back to Project.first()."""
    original_secret = settings.GITHUB_WEBHOOK_SECRET
    test_secret = "webhook_secret_strict_match"
    settings.GITHUB_WEBHOOK_SECRET = test_secret
    
    # Ensure at least one project exists in DB
    existing_project = db_session.query(Project).first()
    if not existing_project:
        user = db_session.query(User).first()
        existing_project = Project(name="Primary Project", repo_url="https://github.com/primary/project.git", user_id=user.id if user else 1)
        db_session.add(existing_project)
        db_session.commit()
        db_session.refresh(existing_project)

    try:
        # Send webhook for an UNREGISTERED repository URL
        payload = {
            "ref": "refs/heads/main",
            "repository": {"clone_url": "https://github.com/unregistered-owner/completely-different-repo"}
        }
        raw_body = json.dumps(payload).encode("utf-8")
        sig = hmac.new(test_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

        resp = client.post(
            "/projects/github/webhook",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": f"sha256={sig}"
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ignored"
        assert "No registered project matches" in data.get("reason", "")
        # Crucial: must NOT have triggered on the existing project
        assert "project_id" not in data, "Webhook executed analysis on unrelated project via Project.first() fallback!"
    finally:
        settings.GITHUB_WEBHOOK_SECRET = original_secret

def test_webhook_valid_signature_accepted(db_session):
    """Verify that a correctly signed webhook for a registered project triggers analysis."""
    original_secret = settings.GITHUB_WEBHOOK_SECRET
    test_secret = "webhook_valid_secret"
    settings.GITHUB_WEBHOOK_SECRET = test_secret
    
    # Create a registered test project
    repo_url = "https://github.com/test-org/webhook-verified-repo"
    user = db_session.query(User).first()
    user_id = user.id if user else 1
    proj = Project(name="Webhook Verified Proj", repo_url=repo_url, user_id=user_id)
    db_session.add(proj)
    db_session.commit()
    db_session.refresh(proj)

    try:
        payload = {
            "ref": "refs/heads/main",
            "head_commit": {"id": "abcdef1234567890", "message": "Verify signature commit"},
            "repository": {"clone_url": repo_url}
        }
        raw_body = json.dumps(payload).encode("utf-8")
        sig = hmac.new(test_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

        resp = client.post(
            "/projects/github/webhook",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": f"sha256={sig}"
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "triggered"
        assert data.get("project_id") == proj.id
    finally:
        settings.GITHUB_WEBHOOK_SECRET = original_secret
        db_session.delete(proj)
        db_session.commit()
