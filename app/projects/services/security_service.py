import os
import re
import logging
from fastapi import HTTPException, status
from app.config import settings

logger = logging.getLogger("security_service")

class SecurityService:
    @staticmethod
    def validate_safe_path(base_dir: str, target_path: str) -> str:
        """Validates that a path is safe and does not escape the base directory (path traversal check)."""
        abs_base = os.path.abspath(base_dir)
        abs_target = os.path.abspath(os.path.join(base_dir, target_path))
        if not abs_target.startswith(abs_base):
            logger.warning(f"Path traversal attempt detected! base_dir={base_dir}, target_path={target_path}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security validation failed: Path traversal detected."
            )
        return abs_target

    @staticmethod
    def is_safe_filename(filename: str) -> bool:
        """Checks if a filename has allowed characters and extension."""
        if not filename or len(filename) > 255:
            return False
        # Match alphanumeric characters, hyphens, underscores, dots and spaces
        pattern = r'^[\w\-. ]+$'
        return bool(re.match(pattern, filename))

    @staticmethod
    def is_allowed_extension(filename: str) -> bool:
        """Whitelist of safe coding extension suffixes."""
        allowed_suffixes = {
            ".py", ".java", ".js", ".ts", ".jsx", ".tsx",
            ".json", ".yml", ".yaml", ".txt", ".md", ".gitignore",
            ".html", ".css"
        }
        _, ext = os.path.splitext(filename.lower())
        return ext in allowed_suffixes

    @staticmethod
    def check_zip_bomb(file_size_bytes: int, max_size_bytes: int = 50 * 1024 * 1024) -> bool:
        """Checks if an uploaded zip file exceeds size limits to prevent ZIP bombs."""
        if file_size_bytes > max_size_bytes:
            logger.warning(f"File size {file_size_bytes} exceeds limits ({max_size_bytes})")
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Upload rejected: File exceeds the maximum limit of {max_size_bytes // (1024*1024)}MB."
            )
        return True

    @staticmethod
    def check_rate_limit(client_ip: str, limit: int = 60, window: int = 60) -> bool:
        """Performs sliding-window rate limiting per client IP using Redis."""
        try:
            from app.projects.services.redis_service import redis_service
            if redis_service.is_mock:
                return True
                
            key = f"rate_limit:{client_ip}"
            current_count = redis_service.client.get(key)
            if current_count and int(current_count) >= limit:
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                return False
                
            pipe = redis_service.client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window)
            pipe.execute()
            return True
        except Exception as e:
            logger.error(f"Rate limiting check failed: {e}")
            return True # Allow request on redis exception to avoid service lockouts
