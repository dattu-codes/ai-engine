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


def test_app_environment_treats_non_development_as_production_fail_closed():
    """Verify that any environment value other than explicit 'development' fails closed as production."""
    non_dev_envs = ["staging", "prod", "testing", "sandbox", "", "unknown_custom_env"]

    orig_env = os.environ.get("APP_ENVIRONMENT")
    orig_jwt = os.environ.get("JWT_SECRET")

    try:
        os.environ.pop("JWT_SECRET", None)

        for env_val in non_dev_envs:
            os.environ["APP_ENVIRONMENT"] = env_val
            # Settings.load_from_env must refuse to generate insecure dev secret and raise ValueError
            with pytest.raises(ValueError) as exc_info:
                Settings.load_from_env()
            assert "JWT_SECRET must be explicitly set" in str(exc_info.value), f"Failed to fail closed for env='{env_val}'"

        # Explicit 'development' should succeed and generate dev fallback secret
        os.environ["APP_ENVIRONMENT"] = "development"
        dev_settings = Settings.load_from_env()
        assert dev_settings.is_development is True
        assert dev_settings.is_production is False
        assert len(dev_settings.JWT_SECRET) >= 32

        # Also verify startup_validator treats non-development as production
        orig_app_env = settings.APP_ENVIRONMENT
        orig_app_jwt = settings.JWT_SECRET
        try:
            settings.JWT_SECRET = ""
            for env_val in ["staging", "prod", "qa", ""]:
                settings.APP_ENVIRONMENT = env_val
                assert settings.is_production is True
                with pytest.raises(SystemExit) as exc_info:
                    run_startup_validation()
                assert "JWT_SECRET" in str(exc_info.value)
        finally:
            settings.APP_ENVIRONMENT = orig_app_env
            settings.JWT_SECRET = orig_app_jwt

    finally:
        if orig_env is not None:
            os.environ["APP_ENVIRONMENT"] = orig_env
        else:
            os.environ.pop("APP_ENVIRONMENT", None)
        if orig_jwt is not None:
            os.environ["JWT_SECRET"] = orig_jwt
        else:
            os.environ.pop("JWT_SECRET", None)


def test_production_startup_allows_missing_redis_without_abort():
    """Verify missing Redis in production logs warning and runs degraded without aborting (no SystemExit)."""
    orig_env = settings.APP_ENVIRONMENT
    orig_jwt = settings.JWT_SECRET
    orig_token_key = settings.TOKEN_ENCRYPTION_KEY
    orig_redis_url = settings.REDIS_URL

    try:
        settings.APP_ENVIRONMENT = "production"
        settings.JWT_SECRET = "production-super-secure-jwt-secret-key-32chars"
        settings.TOKEN_ENCRYPTION_KEY = "WeJ9DI7Ijt8TNFNRnCtH5juEPp5oRjIgfGlpVCWAWFE="
        # Point to unreachable redis endpoint
        settings.REDIS_URL = "redis://127.0.0.1:65534/0"

        # Must NOT raise SystemExit
        report = run_startup_validation()
        assert "Degraded" in report["redis"] or "Unhealthy" in report["redis"]
        # Fatal keys were present, so status should not abort startup
    finally:
        settings.APP_ENVIRONMENT = orig_env
        settings.JWT_SECRET = orig_jwt
        settings.TOKEN_ENCRYPTION_KEY = orig_token_key
        settings.REDIS_URL = orig_redis_url


