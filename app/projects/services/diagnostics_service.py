import os
import time
import logging
from sqlalchemy import text
from app.config import settings
from app.projects.services.redis_service import redis_service

logger = logging.getLogger("diagnostics_service")

class DiagnosticsService:
    @staticmethod
    def run_diagnostics(db) -> dict:
        report = {
            "timestamp": time.time(),
            "status": "PASS",
            "checks": {},
            "warnings": [],
            "recommendations": []
        }
        
        # 1. Database Connectivity & Latency Check
        try:
            start_time = time.time()
            db.execute(text("SELECT 1"))
            latency = (time.time() - start_time) * 1000  # ms
            report["checks"]["database"] = {
                "status": "Healthy",
                "latency_ms": f"{latency:.2f}ms",
                "provider": "PostgreSQL" if not settings.DATABASE_URL.startswith("sqlite") else "SQLite"
            }
        except Exception as e:
            report["checks"]["database"] = {"status": "Unhealthy", "error": str(e)}
            report["status"] = "FAIL"
            report["warnings"].append(f"Database connectivity check failed: {e}")
            
        # 2. Redis Caching & Queue Pool Latency Check
        try:
            start_time = time.time()
            redis_service.client.ping()
            latency = (time.time() - start_time) * 1000  # ms
            report["checks"]["redis"] = {
                "status": "Healthy",
                "latency_ms": f"{latency:.2f}ms",
                "is_mock_fallback": redis_service.is_mock
            }
            if redis_service.is_mock:
                report["warnings"].append("Redis cache is using in-memory mock fallback.")
                report["recommendations"].append("Deploy a live Redis server instance to support multi-process queue scaling.")
        except Exception as e:
            report["checks"]["redis"] = {"status": "Unhealthy", "error": str(e)}
            report["warnings"].append(f"Redis cache connection failed: {e}")
            if settings.APP_ENVIRONMENT == "production":
                report["status"] = "FAIL"

        # 3. Storage Permissions Check
        try:
            upload_dir = settings.UPLOAD_DIRECTORY
            is_writable = os.access(upload_dir, os.W_OK) if os.path.exists(upload_dir) else True
            report["checks"]["storage"] = {
                "status": "Healthy" if is_writable else "Unhealthy",
                "provider": settings.STORAGE_PROVIDER,
                "upload_directory": upload_dir,
                "writable": is_writable
            }
            if not is_writable:
                report["status"] = "FAIL"
                report["warnings"].append(f"Upload directory '{upload_dir}' has no write permissions.")
        except Exception as e:
            report["checks"]["storage"] = {"status": "Unhealthy", "error": str(e)}
            report["status"] = "FAIL"

        # 4. Critical Security & Key Checks
        if settings.JWT_SECRET == "47a329ef3118cf94a0d923bc650630ba5239a04a5cf2b07e5cba4839de848aef":
            report["warnings"].append("JWT_SECRET is set to the default development value.")
            if settings.APP_ENVIRONMENT == "production":
                report["status"] = "FAIL"
                report["recommendations"].append("Configure a secure, high-entropy JWT_SECRET in production.")
                
        if not settings.GEMINI_API_KEY:
            report["warnings"].append("GEMINI_API_KEY is empty. The application will fall back to offline simulator mode.")
            report["recommendations"].append("Provide a GEMINI_API_KEY to enable live code review scanning.")

        # Update final aggregated status
        if len(report["warnings"]) > 0 and report["status"] == "PASS":
            report["status"] = "WARN"
            
        return report
