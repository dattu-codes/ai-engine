import os
import logging
from app.config import settings

logger = logging.getLogger("startup_validator")

def run_startup_validation():
    report = {
        "status": "READY",
        "database": "Healthy",
        "redis": "Healthy",
        "storage": "Healthy",
        "workers": "Healthy",
        "environment": settings.APP_ENVIRONMENT,
        "version": "2.6.0",
        "errors": []
    }
    
    is_prod = settings.APP_ENVIRONMENT.strip().lower() != "development"

    # 1. Check Database connection
    try:
        from app.auth.database.connection import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        report["database"] = f"Unhealthy: {str(e)}"
        report["errors"].append(f"Database connection failed: {str(e)}")
        report["status"] = "UNHEALTHY"

    # 2. Check Redis connection
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        r.ping()
    except ImportError:
        report["redis"] = "Degraded: redis library not installed (in-memory fallback)"
        logger.warning("Redis library not installed, background tasks and caching will fallback to in-memory mock.")
    except Exception as e:
        report["redis"] = f"Degraded: {str(e)} (in-memory fallback)"
        logger.warning(f"Redis is offline, background tasks and caching will fallback: {str(e)}")

    # 3. Check upload directory write permissions
    try:
        upload_path = settings.UPLOAD_DIRECTORY
        os.makedirs(upload_path, exist_ok=True)
        test_file = os.path.join(upload_path, ".write_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
    except Exception as e:
        report["storage"] = f"Unhealthy: {str(e)}"
        report["errors"].append(f"Upload directory '{settings.UPLOAD_DIRECTORY}' is not writable: {str(e)}")
        report["status"] = "UNHEALTHY"

    # 4. Check JWT and Token Encryption configurations in production (Fatal checks)
    fatal_errors = []
    if is_prod:
        if not settings.JWT_SECRET or len(settings.JWT_SECRET.strip()) < 32:
            fatal_errors.append("JWT_SECRET must be an explicit, secure key of at least 32 characters in production.")
            report["errors"].append("JWT_SECRET must be an explicit, secure key of at least 32 characters in production.")
            report["status"] = "UNHEALTHY"

        if not settings.TOKEN_ENCRYPTION_KEY or not settings.TOKEN_ENCRYPTION_KEY.strip():
            fatal_errors.append("TOKEN_ENCRYPTION_KEY must be explicitly set in production.")
            report["errors"].append("TOKEN_ENCRYPTION_KEY must be explicitly set in production.")
            report["status"] = "UNHEALTHY"
        else:
            try:
                from cryptography.fernet import Fernet
                Fernet(settings.TOKEN_ENCRYPTION_KEY.encode("utf-8"))
            except Exception as e:
                fatal_errors.append(f"TOKEN_ENCRYPTION_KEY is invalid for Fernet: {str(e)}")
                report["errors"].append(f"TOKEN_ENCRYPTION_KEY is invalid for Fernet: {str(e)}")
                report["status"] = "UNHEALTHY"

    # Print validation results
    if report["status"] == "READY":
        logger.info(f"Startup Readiness Validation succeeded: {report}")
    else:
        logger.error(f"Startup Readiness Validation report: {report}")
        # Only abort startup in production if fatal security keys are missing/invalid
        if is_prod and len(fatal_errors) > 0:
            import sys
            sys.exit(f"Startup Readiness Validation failed: {fatal_errors}")
            
    return report
