import threading
from datetime import datetime, timedelta
from typing import Dict, List
from fastapi import HTTPException, status

class LoginRateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        # Maps "username:ip" to list of timestamps of failed logins
        self._failed_attempts: Dict[str, List[datetime]] = {}

    def check_rate_limit(self, username: str, ip_address: str):
        key = f"{username}:{ip_address}"
        now = datetime.utcnow()
        one_minute_ago = now - timedelta(minutes=1)

        with self._lock:
            if key not in self._failed_attempts:
                return

            # Keep only attempts in the last 60 seconds
            self._failed_attempts[key] = [
                t for t in self._failed_attempts[key] if t > one_minute_ago
            ]

            # Enforce 5 failed attempts per minute limit
            if len(self._failed_attempts[key]) >= 5:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many failed login attempts. Please try again after a minute."
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
