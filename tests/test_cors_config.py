import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings

client = TestClient(app)

def test_cors_origins_never_includes_wildcard():
    """Verify get_cors_origins() never includes '*' when allow_credentials is True."""
    orig_origins = settings.ALLOWED_ORIGINS
    try:
        # Test 1: Default configuration
        origins = settings.get_cors_origins()
        assert "*" not in origins
        assert "http://localhost:8000" in origins

        # Test 2: If ALLOWED_ORIGINS contains "*", it must be stripped
        settings.ALLOWED_ORIGINS = "*,http://localhost:3000,https://app.aiengine.dev"
        clean = settings.get_cors_origins()
        assert "*" not in clean
        assert "http://localhost:3000" in clean
        assert "https://app.aiengine.dev" in clean

        # Test 3: If only "*" is provided, safe explicit fallback is used
        settings.ALLOWED_ORIGINS = "*"
        fallback = settings.get_cors_origins()
        assert "*" not in fallback
        assert len(fallback) > 0
    finally:
        settings.ALLOWED_ORIGINS = orig_origins


def test_cors_preflight_allowed_origin():
    """Verify CORS preflight from allowed origin returns exact origin and allow_credentials=true."""
    headers = {
        "Origin": "http://localhost:8000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Authorization,Content-Type"
    }
    resp = client.options("/auth/login", headers=headers)
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:8000"
    assert resp.headers.get("access-control-allow-credentials") == "true"
    # NEVER wildcard with credentials
    assert resp.headers.get("access-control-allow-origin") != "*"


def test_cors_preflight_disallowed_origin_rejected():
    """Verify CORS preflight from untrusted origin is rejected and never given wildcard allow."""
    headers = {
        "Origin": "http://untrusted-malicious-site.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Authorization"
    }
    resp = client.options("/auth/login", headers=headers)
    # Untrusted origin should NOT get access-control-allow-origin matching their origin or wildcard
    allow_origin = resp.headers.get("access-control-allow-origin")
    assert allow_origin != "http://untrusted-malicious-site.com"
    assert allow_origin != "*"
