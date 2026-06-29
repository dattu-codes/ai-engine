from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.database.connection import get_db
from app.auth.models.auth_models import User, RefreshToken, UserSession
from app.auth.schemas.auth_schemas import (
    UserSignupRequest, UserLoginRequest, TokenResponse,
    TokenRefreshRequest, UserProfileResponse, ForgotPasswordRequest,
    ResetPasswordRequest, VerifyEmailRequest
)
from app.auth.services.auth_service import AuthService
from app.auth.services.rate_limiter import rate_limiter
from app.auth.dependencies import get_current_user, require_admin_role

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

@auth_router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=UserProfileResponse)
def signup(req: UserSignupRequest, db: Session = Depends(get_db)):
    """User signup endpoint. Registers a new account with a hashed password."""
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == req.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already registered"
        )
        
    # Hash the password and save
    hashed = AuthService.hash_password(req.password)
    user = User(
        username=req.username,
        hashed_password=hashed,
        role=req.role or "user"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@auth_router.post("/login", response_model=TokenResponse)
def login(req: UserLoginRequest, request: Request, db: Session = Depends(get_db)):
    """User login endpoint. Authenticates credentials, logs the session, and issues tokens."""
    ip_addr = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    # 1. Enforce IP/Username failed attempts rate limiting (5 attempts per minute max)
    rate_limiter.check_rate_limit(req.username, ip_addr)

    # Load the user
    user = db.query(User).filter(User.username == req.username).first()
    if not user:
        rate_limiter.record_failed_attempt(req.username, ip_addr)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # 2. Check for Account Lock (10 failed attempts -> 15 min lock)
    now = datetime.utcnow()
    if user.locked_until and user.locked_until > now:
        remaining = int((user.locked_until - now).total_seconds() / 60)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account is temporarily locked. Try again in {remaining} minute(s)."
        )

    # 3. Verify Password
    if not AuthService.verify_password(req.password, user.hashed_password):
        # Increment failed attempts
        user.failed_login_attempts += 1
        rate_limiter.record_failed_attempt(req.username, ip_addr)
        
        # Hard lock trigger (10 failed attempts locks for 15 minutes)
        if user.failed_login_attempts >= 10:
            user.locked_until = now + timedelta(minutes=15)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account locked for 15 minutes due to too many failed logins."
            )
            
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # 4. Success: Clear lock metrics
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = now
    user.last_active = now
    rate_limiter.clear_attempts(req.username, ip_addr)

    # 5. Issue JWT pair
    access_token, refresh_token, access_exp, refresh_exp = AuthService.create_jwt_pair(user.id, user.role)

    # 6. Save hashed refresh token to DB
    hashed_rt = AuthService.hash_token(refresh_token)
    db_token = RefreshToken(
        user_id=user.id,
        token_hash=hashed_rt,
        expires_at=refresh_exp,
        user_agent=user_agent,
        ip_address=ip_addr
    )
    db.add(db_token)

    # 7. Create audit log UserSession
    session_log = UserSession(
        user_id=user.id,
        user_agent=user_agent,
        ip_address=ip_addr,
        login_time=now
    )
    db.add(session_log)
    
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=int(settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    )


@auth_router.post("/refresh", response_model=TokenResponse)
def refresh(req: TokenRefreshRequest, request: Request, db: Session = Depends(get_db)):
    """Refreshes and rotates tokens. Prevents token reuse through automatic chain revocation."""
    ip_addr = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    # Decode token payload
    payload = AuthService.decode_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    hashed_rt = AuthService.hash_token(req.refresh_token)
    db_token = db.query(RefreshToken).filter(RefreshToken.token_hash == hashed_rt).first()

    # Token Reuse Detection (Security Breach check)
    if not db_token or db_token.revoked_at is not None:
        if db_token and db_token.revoked_at is not None:
            # Token was already used/revoked! Revoke all tokens in this user's family
            db.query(RefreshToken).filter(
                RefreshToken.user_id == db_token.user_id
            ).update({"revoked_at": datetime.utcnow()})
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Security breach detected: Refresh token has already been reused."
        )

    # Check expiry
    if db_token.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired"
        )

    # Rotate tokens: create new pair
    user_id = int(payload["sub"])
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token is inactive or not found"
        )

    access_token, new_refresh_token, access_exp, refresh_exp = AuthService.create_jwt_pair(user.id, user.role)
    new_hashed_rt = AuthService.hash_token(new_refresh_token)

    # Save new token
    new_db_token = RefreshToken(
        user_id=user.id,
        token_hash=new_hashed_rt,
        expires_at=refresh_exp,
        user_agent=user_agent,
        ip_address=ip_addr
    )
    db.add(new_db_token)
    db.flush()

    # Invalidate and replace old token (rotation)
    db_token.revoked_at = datetime.utcnow()
    db_token.replaced_by_token_id = new_db_token.id
    
    # Update last active time for audit
    user.last_active = datetime.utcnow()
    
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=int(settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    )


@auth_router.post("/logout")
def logout(req: TokenRefreshRequest, db: Session = Depends(get_db)):
    """Revokes the specific refresh token session and logs out the user."""
    hashed_rt = AuthService.hash_token(req.refresh_token)
    db_token = db.query(RefreshToken).filter(RefreshToken.token_hash == hashed_rt).first()
    
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token not found or already logged out"
        )
        
    db_token.revoked_at = datetime.utcnow()
    
    # Log out audit sessions
    session = db.query(UserSession).filter(
        UserSession.user_id == db_token.user_id,
        UserSession.logout_time == None
    ).order_by(UserSession.login_time.desc()).first()
    
    if session:
        session.logout_time = datetime.utcnow()
        
    db.commit()
    return {"detail": "Logged out successfully"}


@auth_router.get("/profile", response_model=UserProfileResponse)
def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Protected profile route returning user details."""
    current_user.last_active = datetime.utcnow()
    db.commit()
    return current_user


@auth_router.get("/admin")
def get_admin_dashboard(current_user: User = Depends(require_admin_role)):
    """Protected admin dashboard route requiring admin role authorization."""
    return {
        "detail": f"Welcome to the admin zone, {current_user.username}!",
        "role": current_user.role,
        "is_admin": True
    }


# --- Preparation Route Stubs (Placeholder logic for future release) ---

@auth_router.post("/verify-email")
def verify_email(req: VerifyEmailRequest):
    """Stub endpoint for email verification."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Email verification feature is not fully set up yet. Token accepted."
    )


@auth_router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    """Stub endpoint to initiate forgot password email."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Forgot password verification system not fully set up yet. Username accepted."
    )


@auth_router.post("/reset-password")
def reset_password(req: ResetPasswordRequest):
    """Stub endpoint to reset password using token."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Reset password system not fully set up yet. Token and password accepted."
    )
