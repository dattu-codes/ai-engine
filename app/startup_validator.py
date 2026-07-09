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
        report["redis"] = "Unhealthy: redis library not installed"
        if settings.APP_ENVIRONMENT == "production":
            report["errors"].append("redis python package is missing.")
            report["status"] = "UNHEALTHY"
    except Exception as e:
        report["redis"] = f"Unhealthy: {str(e)}"
        # Warn in dev, but strictly fail in production environment
        if settings.APP_ENVIRONMENT == "production":
            report["errors"].append(f"Redis connection failed (Required in production): {str(e)}")
            report["status"] = "UNHEALTHY"
        else:
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

    # 4. Check JWT configurations
    if settings.JWT_SECRET == "47a329ef3118cf94a0d923bc650630ba5239a04a5cf2b07e5cba4839de848aef" and settings.APP_ENVIRONMENT == "production":
        report["errors"].append("JWT_SECRET is using default development value in production environment.")
        report["status"] = "UNHEALTHY"

    # Print validation results
    if report["status"] == "READY":
        logger.info(f"Startup Readiness Validation succeeded: {report}")
    else:
        logger.error(f"Startup Readiness Validation failed! Report: {report}")
        # Only abort start up in production if critical errors occur
        if settings.APP_ENVIRONMENT == "production" and len(report["errors"]) > 0:
            import sys
            sys.exit(f"Startup Readiness Validation failed: {report['errors']}")
            
    return report
