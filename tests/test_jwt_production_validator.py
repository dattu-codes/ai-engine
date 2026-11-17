import os
import inspect
import pytest
from app.config import settings, Settings
from app.startup_validator import run_startup_validation
import app.startup_validator as sv_module
import app.projects.services.diagnostics_service as ds_module

def test_startup_fails_in_production_if_jwt_secret_missing():
    """Verify startup validation fails with SystemExit in production if JWT_SECRET is missing."""
    orig_env = settings.APP_ENVIRONMENT
    orig_jwt = settings.JWT_SECRET
    orig_token_key = settings.TOKEN_ENCRYPTION_KEY

    settings.APP_ENVIRONMENT = "production"
    settings.JWT_SECRET = ""
    settings.TOKEN_ENCRYPTION_KEY = "WeJ9DI7Ijt8TNFNRnCtH5juEPp5oRjIgfGlpVCWAWFE="

    try:
        with pytest.raises(SystemExit) as exc_info:
            run_startup_validation()
        assert "JWT_SECRET" in str(exc_info.value)
    finally:
        settings.APP_ENVIRONMENT = orig_env
        settings.JWT_SECRET = orig_jwt
        settings.TOKEN_ENCRYPTION_KEY = orig_token_key


def test_startup_fails_in_production_if_jwt_secret_under_32_chars():
    """Verify startup validation fails with SystemExit in production if JWT_SECRET is under 32 characters."""
    orig_env = settings.APP_ENVIRONMENT
    orig_jwt = settings.JWT_SECRET
    orig_token_key = settings.TOKEN_ENCRYPTION_KEY

    settings.APP_ENVIRONMENT = "production"
    settings.JWT_SECRET = "short_key_under_32_chars"
    settings.TOKEN_ENCRYPTION_KEY = "WeJ9DI7Ijt8TNFNRnCtH5juEPp5oRjIgfGlpVCWAWFE="

    try:
        with pytest.raises(SystemExit) as exc_info:
            run_startup_validation()
        assert "JWT_SECRET" in str(exc_info.value)
    finally:
        settings.APP_ENVIRONMENT = orig_env
        settings.JWT_SECRET = orig_jwt
        settings.TOKEN_ENCRYPTION_KEY = orig_token_key


def test_no_hardcoded_jwt_secret_literals_in_validator_and_diagnostics():
    """Verify neither startup_validator nor diagnostics_service contain hardcoded JWT secret literals."""
    sv_source = inspect.getsource(sv_module)
    ds_source = inspect.getsource(ds_module)

    # The legacy hardcoded literal strings
    banned_literals = [
        "47a329ef3118cf94a0d923bc650630ba5239a04a5cf2b07e5cba4839de848aef",
        "DEFAULT_DEV_JWT_SECRET",
        "secret-key-32chars"
    ]

    for literal in banned_literals:
        assert literal not in sv_source, f"Found hardcoded literal '{literal}' in startup_validator.py"
        assert literal not in ds_source, f"Found hardcoded literal '{literal}' in diagnostics_service.py"
