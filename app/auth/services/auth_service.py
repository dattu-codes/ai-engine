import bcrypt
import jwt
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
from app.auth.config.settings import settings

class AuthService:
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """Verify a bcrypt hashed password."""
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"),
                hashed_password.encode("utf-8")
            )
        except Exception:
            return False

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token string using SHA-256 for secure storage."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def create_jwt_pair(cls, user_id: int, role: str) -> Tuple[str, str, datetime, datetime]:
        """
        Generate a JWT Access Token (15 mins) and a Refresh Token (7 days).
        Returns:
            (access_token_string, refresh_token_string, access_expires_at, refresh_expires_at)
        """
        now = datetime.utcnow()
        
        # Access Token Expiry
        access_expires = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_claims = {
            "sub": str(user_id),
            "role": role,
            "exp": access_expires,
            "iat": now,
            "type": "access",
            "jti": str(uuid.uuid4())
        }
        
        # Refresh Token Expiry
        refresh_expires = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        refresh_claims = {
            "sub": str(user_id),
            "exp": refresh_expires,
            "iat": now,
            "type": "refresh",
            "jti": str(uuid.uuid4())
        }
        
        # Encode tokens
        access_token = jwt.encode(
            access_claims,
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM
        )
        refresh_token = jwt.encode(
            refresh_claims,
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM
        )
        
        return access_token, refresh_token, access_expires, refresh_expires

    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        """Decode and validate a JWT. Returns payload claims or None if invalid/expired."""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None
