import threading
from datetime import datetime, timedelta
from typing import Dict, List
from fastapi import HTTPException, status
from app.auth.config.settings import settings

class LoginRateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        # Maps "username:ip" to list of timestamps of failed logins
        self._failed_attempts: Dict[str, List[datetime]] = {}

    def check_rate_limit(self, username: str, ip_address: str):
        key = f"{username}:{ip_address}"
        now = datetime.utcnow()
        window_ago = now - timedelta(seconds=settings.RATE_LIMIT_WINDOW_SECONDS)

        with self._lock:
            if key not in self._failed_attempts:
                return

            # Keep only attempts in the last window
            self._failed_attempts[key] = [
                t for t in self._failed_attempts[key] if t > window_ago
            ]

            # Enforce 5 failed attempts per window limit (60s default)
            if len(self._failed_attempts[key]) >= 5:
                oldest_attempt = min(self._failed_attempts[key])
                remaining_seconds = max(1, int((oldest_attempt + timedelta(seconds=settings.RATE_LIMIT_WINDOW_SECONDS) - now).total_seconds()))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many failed login attempts. Please try again after {remaining_seconds} seconds.",
                    headers={"Retry-After": str(remaining_seconds)}
                )

    def record_failed_attempt(self, username: str, ip_address: str):
        key = f"{username}:{ip_address}"
        now = datetime.utcnow()

        with self._lock:
            if key not in self._failed_attempts:
                self._failed_attempts[key] = []
            self._failed_attempts[key].append(now)

    def clear_attempts(self, username: str, ip_address: str):
        key = f"{username}:{ip_address}"
        with self._lock:
            if key in self._failed_attempts:
                del self._failed_attempts[key]

# Singleton instance
rate_limiter = LoginRateLimiter()
