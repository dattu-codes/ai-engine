import uuid
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.main import app
from app.config import settings
from app.auth.services.rate_limiter import LoginRateLimiter

client = TestClient(app)

def test_rate_limit_window_defaults_to_60_seconds():
    """Verify that login rate limit window is configured to 60 seconds."""
    assert settings.RATE_LIMIT_WINDOW_SECONDS == 60


def test_rate_limiter_lockout_message_and_retry_after_matches_window():
    """Verify rate limiter raises 429 after 5 failed attempts with detail matching window and Retry-After header."""
    limiter = LoginRateLimiter()
    username = f"rate_user_{uuid.uuid4().hex[:8]}"
    ip = "192.168.1.100"

    # 4 failed attempts should pass without raising
    for _ in range(4):
        limiter.record_failed_attempt(username, ip)
        limiter.check_rate_limit(username, ip)

    # 5th failed attempt triggers rate limit
    limiter.record_failed_attempt(username, ip)
    with pytest.raises(HTTPException) as exc_info:
        limiter.check_rate_limit(username, ip)

    exc = exc_info.value
    assert exc.status_code == 429
    assert "Too many failed login attempts" in exc.detail
    assert "seconds" in exc.detail
    
    # Lockout message matches real window
    assert "Retry-After" in exc.headers
    retry_after = int(exc.headers["Retry-After"])
    assert 1 <= retry_after <= 60
    assert f"after {retry_after} seconds" in exc.detail


def test_login_endpoint_enforces_rate_limit_with_429():
    """Verify POST /auth/login returns 429 with lockout message after repeated invalid attempts."""
    test_username = f"lockout_user_{uuid.uuid4().hex[:8]}"
    
    # 5 bad logins -> 401
    for _ in range(5):
        resp = client.post("/auth/login", json={"username": test_username, "password": "wrong_password"})
        assert resp.status_code == 401

    # 6th attempt -> 429
    resp_blocked = client.post("/auth/login", json={"username": test_username, "password": "wrong_password"})
    assert resp_blocked.status_code == 429
    assert "Too many failed login attempts" in resp_blocked.json()["detail"]
    assert "seconds" in resp_blocked.json()["detail"]
    assert "Retry-After" in resp_blocked.headers
