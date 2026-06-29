from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.auth.database.connection import get_db
from app.auth.models.auth_models import User
from app.auth.services.auth_service import AuthService

# Use HTTPBearer for clean Swagger Authorization using Bearer prefix
security_scheme = HTTPBearer(auto_error=True)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Dependency to load the current logged-in user from the JWT access token."""
    token = credentials.credentials
    payload = AuthService.decode_token(token)
    
    # Validate payload format and token type
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Load user from database
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )
        
    return user


def require_authenticated_user(current_user: User = Depends(get_current_user)) -> User:
    """Helper alias dependency to guarantee user authentication."""
    return current_user


def require_admin_role(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to ensure the current authenticated user has an 'admin' role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required to access this resource"
        )
    return current_user
