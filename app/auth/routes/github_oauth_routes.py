import urllib.parse
import urllib.request
import json
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List

from app.auth.database.connection import get_db
from app.auth.models.auth_models import User
from app.auth.dependencies import get_current_user
from app.auth.services.auth_service import AuthService
from app.config import settings

router = APIRouter(prefix="/auth/github", tags=["GitHub OAuth"])

# Simulated in-memory database of mock GitHub repositories for offline/test mode
MOCK_GITHUB_REPOS = [
    {"name": "ai-engine-demo", "owner": "insights_tester", "url": "https://github.com/insights_tester/ai-engine-demo", "private": False, "description": "AI Engine demo repo"},
    {"name": "go-rest-api", "owner": "insights_tester", "url": "https://github.com/insights_tester/go-rest-api", "private": True, "description": "Go REST api service"},
    {"name": "antigravity-app", "owner": "insights_tester", "url": "https://github.com/insights_tester/antigravity-app", "private": False, "description": "Antigravity landing UI webapp"}
]

@router.get("/login")
def github_login(mock: bool = Query(False)):
    """Redirects user to GitHub's OAuth authorize page or triggers mock callback."""
    if not settings.GITHUB_CLIENT_ID or mock:
        # Trigger mock redirect straight to callback
        return RedirectResponse(url="/auth/github/callback?code=mock_oauth_code&state=mock_state")
        
    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "scope": "user,repo",
        "state": "oauth_state_123"
    }
    url = "https://github.com/login/oauth/authorize?" + urllib.parse.urlencode(params)
    return RedirectResponse(url=url)

@router.get("/callback")
def github_callback(code: str, state: Optional[str] = None, db: Session = Depends(get_db)):
    """Handles GitHub redirect, exchanges code for access token, signs in or creates user."""
    # 1. Exchange OAuth code for GitHub token
    github_token = "mock_github_access_token"
    github_user_data = {
        "id": 999999,
        "login": "mock_github_user",
        "name": "Mock GitHub User"
    }
    
    is_mock = code == "mock_oauth_code" or not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET
    
    if not is_mock:
        try:
            # Live GitHub API exchange
            token_url = "https://github.com/login/oauth/access_token"
            data = urllib.parse.urlencode({
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code
            }).encode("utf-8")
            
            req = urllib.request.Request(token_url, data=data, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req) as resp:
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
            with urllib.request.urlopen(req_user) as resp_user:
                github_user_data = json.loads(resp_user.read().decode("utf-8"))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"GitHub authentication error: {str(e)}")

    # 2. Check if a user with this github_id exists
    git_id = str(github_user_data["id"])
    user = db.query(User).filter(User.github_id == git_id).first()
    
    if not user:
        # Create a new SaaS user automatically
        username = github_user_data["login"]
        # Make sure username is unique in database
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            username = f"{username}_{git_id[:4]}"
            
        user = User(
            username=username,
            hashed_password=AuthService.hash_password("oauth_disabled_password"),
            role="developer",
            github_id=git_id,
            github_username=github_user_data["login"],
            github_token=github_token,
            github_connected=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Update token
        user.github_token = github_token
        user.github_connected = True
        db.commit()

    # 3. Create access/refresh tokens for AI Engine session
    access_token, refresh_token, _, _ = AuthService.create_jwt_pair(user.id, user.role)
    
    # Redirect back to index.html dashboard, passing tokens in URL hash so frontend can ingest them
    redirect_url = f"/dashboard#access_token={access_token}&refresh_token={refresh_token}&username={user.username}&role={user.role}"
    return RedirectResponse(url=redirect_url)

@router.post("/connect")
def connect_github(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Connects a logged-in user to mock GitHub account."""
    current_user.github_id = "mock_" + str(current_user.id)
    current_user.github_username = current_user.username
    current_user.github_token = "mock_token_" + str(current_user.id)
    current_user.github_connected = True
    db.commit()
    return {"status": "connected", "github_username": current_user.github_username}

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
    """Lists repositories from connected GitHub account."""
    if not current_user.github_connected:
        raise HTTPException(status_code=400, detail="GitHub account not connected")
        
    # Return mock repos list for validation
    return MOCK_GITHUB_REPOS

@router.get("/install")
def github_app_install():
    """Mock GitHub App installation callback endpoint."""
    return {"status": "installed", "message": "GitHub App installed successfully on selected repositories."}
