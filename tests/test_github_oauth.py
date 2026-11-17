import os
import urllib.parse
import secrets
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.auth.database.connection import get_db, Base, engine
from app.auth.models.auth_models import User, OAuthState, OAuthExchangeCode
from app.auth.services.auth_service import AuthService
from app.auth.services.token_encryption_service import encrypt_token, decrypt_token
from app.startup_validator import run_startup_validation

client = TestClient(app)

@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


def test_missing_state_rejected():
    """Verify callback without state returns 400 Bad Request."""
    res1 = client.get("/auth/github/callback?code=some_code")
    assert res1.status_code == 400, f"Expected 400 for missing state, got {res1.status_code}: {res1.text}"
    assert "state" in res1.text.lower()

    res2 = client.get("/auth/github/callback?code=some_code&state=")
    assert res2.status_code == 400, f"Expected 400 for empty state, got {res2.status_code}: {res2.text}"
    assert "state" in res2.text.lower()


def test_bad_state_rejected(db_session):
    """Verify callback with an unrecognized, forged, or expired state returns 400."""
    res = client.get("/auth/github/callback?code=some_code&state=forged_state_xyz")
    assert res.status_code == 400, f"Expected 400 for bad state, got {res.status_code}: {res.text}"
    assert "invalid or expired oauth state" in res.text.lower()


def test_no_mock_login_possible_when_oauth_unconfigured():
    """Verify no mock login fallback exists; unconfigured credentials fail closed with 503."""
    orig_cid = settings.GITHUB_CLIENT_ID
    orig_secret = settings.GITHUB_CLIENT_SECRET
    settings.GITHUB_CLIENT_ID = ""
    settings.GITHUB_CLIENT_SECRET = ""
    try:
        # 1. /login without credentials -> 503
        res_login = client.get("/auth/github/login", follow_redirects=False)
        assert res_login.status_code == 503, f"Expected 503 when unconfigured, got {res_login.status_code}"

        # 2. /login?mock=true must NOT bypass or produce mock callback
        res_mock = client.get("/auth/github/login?mock=true", follow_redirects=False)
        assert res_mock.status_code == 503, f"Expected 503 for mock attempt, got {res_mock.status_code}"

        # 3. /callback with mock code must NOT produce mock identity
        res_cb = client.get("/auth/github/callback?code=mock_oauth_code&state=some_state", follow_redirects=False)
        assert res_cb.status_code in (400, 503), f"Expected fail-closed (400/503), got {res_cb.status_code}"
    finally:
        settings.GITHUB_CLIENT_ID = orig_cid
        settings.GITHUB_CLIENT_SECRET = orig_secret


def test_github_connect_mock_endpoint_deleted():
    """Verify /github/connect mock token endpoint has been permanently deleted."""
    res = client.post("/auth/github/connect")
    assert res.status_code == 404, f"Expected 404 (deleted endpoint), got {res.status_code}: {res.text}"


def test_oauth_login_generates_random_state_in_db_and_minimal_scope(db_session):
    """Verify login sets a cryptographically random state in DB, uses minimal scope, and sets cookie."""
    orig_cid = settings.GITHUB_CLIENT_ID
    orig_secret = settings.GITHUB_CLIENT_SECRET
    settings.GITHUB_CLIENT_ID = "gh_test_client_id_123"
    settings.GITHUB_CLIENT_SECRET = "gh_test_client_secret_456"
    try:
        res1 = client.get("/auth/github/login", follow_redirects=False)
        assert res1.status_code == 307
        loc1 = res1.headers["location"]
        parsed1 = urllib.parse.urlparse(loc1)
        params1 = urllib.parse.parse_qs(parsed1.query)

        # Check minimal scope ('read:user')
        assert params1["scope"][0] == "read:user"
        state1 = params1["state"][0]
        assert len(state1) >= 32, "State should be a secure random token of at least 32 chars"
        
        # Verify state is saved in DB (cross-worker persistence)
        rec1 = db_session.query(OAuthState).filter(OAuthState.state == state1).first()
        assert rec1 is not None, "OAuth state must be saved in DB"
        assert rec1.expires_at > datetime.utcnow()

        # Second request must produce a DIFFERENT random state
        res2 = client.get("/auth/github/login", follow_redirects=False)
        assert res2.status_code == 307
        loc2 = res2.headers["location"]
        params2 = urllib.parse.parse_qs(urllib.parse.urlparse(loc2).query)
        state2 = params2["state"][0]
        assert state1 != state2, "State must be random per-request"
        rec2 = db_session.query(OAuthState).filter(OAuthState.state == state2).first()
        assert rec2 is not None
    finally:
        settings.GITHUB_CLIENT_ID = orig_cid
        settings.GITHUB_CLIENT_SECRET = orig_secret


def test_no_tokens_in_url_hash_and_db_backed_one_time_exchange(db_session):
    """Verify one-time exchange code mechanism works from DB and cannot be replayed."""
    test_code = "one_time_test_code_db_xyz"
    fake_access = "test_access_token_abc"
    fake_refresh = "test_refresh_token_def"

    # Insert exchange code in DB
    code_record = OAuthExchangeCode(
        code=test_code,
        access_token=fake_access,
        refresh_token=fake_refresh,
        expires_at=datetime.utcnow() + timedelta(seconds=60)
    )
    db_session.add(code_record)
    db_session.commit()

    # 1. Exchange succeeds first time
    res = client.post("/auth/github/exchange", json={"code": test_code})
    assert res.status_code == 200
    data = res.json()
    assert data["access_token"] == fake_access
    assert data["refresh_token"] == fake_refresh

    # 2. Verify record deleted from DB immediately
    db_check = db_session.query(OAuthExchangeCode).filter(OAuthExchangeCode.code == test_code).first()
    assert db_check is None, "Exchange code must be deleted from DB after single use"

    # 3. Replay fails (one-time use)
    res_replay = client.post("/auth/github/exchange", json={"code": test_code})
    assert res_replay.status_code == 400
    assert "invalid or expired" in res_replay.text.lower()


def test_stored_github_token_encrypt_decrypt_roundtrip_and_not_plaintext(db_session):
    """
    Verify that GitHub tokens are encrypted with Fernet, stored as ciphertext in DB (not plaintext),
    and successfully round-trip (encrypt -> store -> decrypt == original).
    """
    raw_token = "ghp_secure_github_token_1234567890abcdef"
    encrypted = encrypt_token(raw_token)

    # Must be Fernet ciphertext (starts with gAAAAA), definitely not plaintext
    assert encrypted != raw_token
    assert encrypted.startswith("gAAAAA")

    # Store in User model
    test_username = f"enc_user_{secrets.token_hex(4)}"
    user = User(
        username=test_username,
        hashed_password=AuthService.hash_password("Pass123!"),
        role="developer",
        github_id="gh_12345678",
        github_username="gh_enc_tester",
        github_token=encrypted,
        github_connected=True,
        is_active=True,
        is_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    try:
        # Verify raw DB value is encrypted ciphertext
        persisted_user = db_session.query(User).filter(User.username == test_username).first()
        assert persisted_user.github_token == encrypted
        assert raw_token not in persisted_user.github_token

        # Decrypt roundtrip
        decrypted = decrypt_token(persisted_user.github_token)
        assert decrypted == raw_token, "Decrypted token must exactly match original plaintext token"
    finally:
        db_session.delete(user)
        db_session.commit()


def test_startup_fails_in_production_if_token_encryption_key_missing():
    """Verify startup validation fails closed in production when TOKEN_ENCRYPTION_KEY is missing or invalid."""
    orig_env = settings.APP_ENVIRONMENT
    orig_key = settings.TOKEN_ENCRYPTION_KEY
    orig_jwt = settings.JWT_SECRET

    settings.APP_ENVIRONMENT = "production"
    settings.JWT_SECRET = "a" * 32  # valid 32-char JWT secret to isolate token key test
    settings.TOKEN_ENCRYPTION_KEY = ""

    try:
        with pytest.raises(SystemExit) as exc_info:
            run_startup_validation()
        assert "TOKEN_ENCRYPTION_KEY" in str(exc_info.value)
    finally:
        settings.APP_ENVIRONMENT = orig_env
        settings.TOKEN_ENCRYPTION_KEY = orig_key
        settings.JWT_SECRET = orig_jwt


def test_dev_fernet_key_dynamically_generated_and_not_hardcoded_default():
    """Verify that in development mode, when TOKEN_ENCRYPTION_KEY is unset, a dynamic key is generated rather than hardcoded."""
    from app.config import Settings
    orig_env = os.environ.get("APP_ENVIRONMENT")
    orig_key = os.environ.get("TOKEN_ENCRYPTION_KEY")

    os.environ["APP_ENVIRONMENT"] = "development"
    if "TOKEN_ENCRYPTION_KEY" in os.environ:
        del os.environ["TOKEN_ENCRYPTION_KEY"]

    try:
        s1 = Settings.load_from_env()
        s2 = Settings.load_from_env()

        # Both keys must be valid Fernet keys
        assert len(s1.TOKEN_ENCRYPTION_KEY) == 44
        assert len(s2.TOKEN_ENCRYPTION_KEY) == 44

        # They are generated dynamically on demand, not a shared static hardcoded default
        assert s1.TOKEN_ENCRYPTION_KEY != s2.TOKEN_ENCRYPTION_KEY
    finally:
        if orig_env is not None:
            os.environ["APP_ENVIRONMENT"] = orig_env
        else:
            os.environ.pop("APP_ENVIRONMENT", None)
        if orig_key is not None:
            os.environ["TOKEN_ENCRYPTION_KEY"] = orig_key
        else:
            os.environ.pop("TOKEN_ENCRYPTION_KEY", None)


def test_decrypt_failure_on_old_plaintext_token_returns_reconnect_github_not_500(db_session):
    """Verify that attempting to decrypt an old, corrupted or plaintext token returns 400 with 'reconnect GitHub' and never crashes with 500."""
    legacy_username = f"legacy_gh_{secrets.token_hex(4)}"
    user = User(
        username=legacy_username,
        hashed_password=AuthService.hash_password("Pass123!"),
        role="developer",
        github_id="gh_legacy_123",
        github_username="legacy_user",
        github_token="ghp_plaintext_old_token_not_fernet_encrypted",
        github_connected=True,
        is_active=True,
        is_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    try:
        access_token, _, _, _ = AuthService.create_jwt_pair(user.id, user.role)
        headers = {"Authorization": f"Bearer {access_token}"}

        resp = client.get("/auth/github/repositories", headers=headers)
        # MUST NOT BE 500!
        assert resp.status_code == 400, f"Expected 400 for legacy plaintext token, got {resp.status_code}"
        assert "reconnect your github account" in resp.json()["detail"].lower()
    finally:
        db_session.delete(user)
        db_session.commit()
