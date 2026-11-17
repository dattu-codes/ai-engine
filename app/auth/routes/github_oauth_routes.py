import urllib.parse
import urllib.request
import json
import secrets
from datetime import datetime, timedelta
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.auth.database.connection import get_db
from app.auth.models.auth_models import User, OAuthState, OAuthExchangeCode
from app.auth.dependencies import get_current_user
from app.auth.services.auth_service import AuthService
from app.auth.services.token_encryption_service import encrypt_token, decrypt_token, GitHubTokenDecryptionError
from app.config import settings

router = APIRouter(prefix="/auth/github", tags=["GitHub OAuth"])


class ExchangeCodeRequest(BaseModel):
    code: str


@router.get("/login")
def github_login(db: Session = Depends(get_db)):
    """
    Redirects user to GitHub's OAuth authorize page with a cryptographically secure random state.
    Uses minimal scope ('read:user'). State is persisted in DB to work across multiple workers.
    Fails closed if OAuth credentials are not configured.
    """
    if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured")

    state = secrets.token_urlsafe(32)
    # Store state in DB with 5-minute TTL to work across all server worker processes
    state_record = OAuthState(
        state=state,
        expires_at=datetime.utcnow() + timedelta(seconds=300)
    )
    db.add(state_record)
    db.commit()

    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "scope": "read:user",
        "state": state
    }
    url = "https://github.com/login/oauth/authorize?" + urllib.parse.urlencode(params)

    redirect = RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    redirect.set_cookie(
        key="github_oauth_state",
        value=state,
        httponly=True,
        samesite="lax",
        max_age=300
    )
    return redirect


@router.get("/callback")
def github_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Handles GitHub redirect, verifies random CSRF state via DB, exchanges code for token,
    encrypts the token with Fernet before DB persistence, and issues a DB-backed short-lived
    one-time exchange code and httpOnly session cookies. Fails closed with no mock fallbacks.
    """
    # 1. State verification (fail closed on missing or invalid/expired state)
    if not state or not state.strip():
        raise HTTPException(status_code=400, detail="Missing OAuth state")

    oauth_state = db.query(OAuthState).filter(OAuthState.state == state).first()
    cookie_state = request.cookies.get("github_oauth_state")

    is_valid_state = False
    if oauth_state and oauth_state.expires_at >= datetime.utcnow():
        is_valid_state = True
    elif cookie_state and cookie_state == state:
        is_valid_state = True

    if not is_valid_state:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    # One-time use: remove state record from DB
    if oauth_state:
        db.delete(oauth_state)
        db.commit()

    if not code or not code.strip():
        raise HTTPException(status_code=400, detail="Missing OAuth authorization code")

    # 2. Enforce configured OAuth credentials
    if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured")

    # 3. Live GitHub API exchange (no mock fallbacks)
    try:
        token_url = "https://github.com/login/oauth/access_token"
        data = urllib.parse.urlencode({
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "code": code
        }).encode("utf-8")

        req = urllib.request.Request(token_url, data=data, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            github_token = resp_data.get("access_token")

        if not github_token:
            raise HTTPException(status_code=400, detail="Failed to retrieve access token from GitHub")

        # Fetch profile
        user_url = "https://api.github.com/user"
        req_user = urllib.request.Request(user_url, headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/json",
            "User-Agent": "AI-Engine-SaaS"
        })
        with urllib.request.urlopen(req_user, timeout=10) as resp_user:
            github_user_data = json.loads(resp_user.read().decode("utf-8"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"GitHub authentication error: {str(e)}")

    git_id = str(github_user_data.get("id"))
    if not git_id or git_id == "None":
        raise HTTPException(status_code=400, detail="Invalid GitHub profile data received")

    # 4. Encrypt GitHub token using Fernet before storing in DB (never plaintext)
    encrypted_github_token = encrypt_token(github_token)

    user = db.query(User).filter(User.github_id == git_id).first()
    if not user:
        username = github_user_data.get("login") or f"gh_{git_id}"
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            username = f"{username}_{git_id[:4]}"

        user = User(
            username=username,
            hashed_password=AuthService.hash_password("oauth_disabled_password"),
            role="developer",
            github_id=git_id,
            github_username=github_user_data.get("login"),
            github_token=encrypted_github_token,
            github_connected=True,
            is_active=True,
            is_verified=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.github_token = encrypted_github_token
        user.github_connected = True
        user.github_username = github_user_data.get("login")
        db.commit()

    # 5. Create access/refresh tokens for AI Engine session
    access_token, refresh_token, _, _ = AuthService.create_jwt_pair(user.id, user.role)

    # 6. Store one-time exchange code in DB (cross-worker support, 60s TTL)
    exchange_code = secrets.token_urlsafe(32)
    code_record = OAuthExchangeCode(
        code=exchange_code,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(seconds=60)
    )
    db.add(code_record)
    db.commit()

    # Redirect to /dashboard?code={exchange_code} (NO tokens in URL hash!)
    redirect_url = f"/dashboard?code={exchange_code}"
    redirect_resp = RedirectResponse(url=redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    redirect_resp.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        max_age=900
    )
    redirect_resp.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        max_age=7 * 86400
    )
    redirect_resp.delete_cookie("github_oauth_state")
    return redirect_resp


@router.post("/exchange")
def exchange_code_for_tokens(req: ExchangeCodeRequest, db: Session = Depends(get_db)):
    """Exchanges a short-lived one-time code for access and refresh tokens from DB."""
    code_record = db.query(OAuthExchangeCode).filter(OAuthExchangeCode.code == req.code).first()
    if not code_record or code_record.expires_at < datetime.utcnow():
        if code_record:
            db.delete(code_record)
            db.commit()
        raise HTTPException(status_code=400, detail="Invalid or expired exchange code")

    access_token = code_record.access_token
    refresh_token = code_record.refresh_token

    # Delete immediately upon use (enforces one-time consumption)
    db.delete(code_record)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/disconnect")
def disconnect_github(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Disconnects GitHub integration."""
    current_user.github_id = None
    current_user.github_username = None
    current_user.github_token = None
    current_user.github_connected = False
    db.commit()
    return {"status": "disconnected"}


@router.get("/repositories")
def get_repositories(current_user: User = Depends(get_current_user)):
    """Lists repositories from connected GitHub account using decrypted token."""
    if not current_user.github_connected or not current_user.github_token:
        raise HTTPException(status_code=400, detail="GitHub account not connected")

    try:
        token = decrypt_token(current_user.github_token)
    except GitHubTokenDecryptionError:
        raise HTTPException(
            status_code=400,
            detail="Stored GitHub token is invalid or unencrypted. Please reconnect your GitHub account."
        )

    url = "https://api.github.com/user/repos?per_page=100&sort=updated"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "AI-Engine-SaaS"
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []


@router.get("/install")
def github_app_install():
    """GitHub App installation callback endpoint."""
    return {"status": "installed", "message": "GitHub App installed successfully on selected repositories."}
