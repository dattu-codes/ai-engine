import os
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from app.auth.database.connection import get_db
from app.config import settings
from app.projects.services.redis_service import redis_service
from app.projects.models.project_models import Project, Analysis, FixExecution, TestExecution

health_router = APIRouter(tags=["observability"])

@health_router.get("/health")
def get_health(db: Session = Depends(get_db)):
    health_status = {
        "status": "Healthy",
        "database": "Healthy",
        "redis": "Healthy",
        "storage": "Healthy",
        "version": "2.6.0"
    }
    
    # 1. Test database engine connectivity
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        health_status["database"] = f"Unhealthy: {str(e)}"
        health_status["status"] = "Unhealthy"
        
    # 2. Test Redis pool connectivity
    if getattr(redis_service, "is_mock", False):
        health_status["redis"] = "Degraded"
    else:
        try:
            redis_service.client.ping()
            health_status["redis"] = "Healthy"
        except Exception as e:
            health_status["redis"] = f"Unhealthy: {str(e)}"
            # Warn in dev mode, but flag system Unhealthy in production
            if settings.APP_ENVIRONMENT == "production":
                health_status["status"] = "Unhealthy"
            
    # 3. Test local storage directory permissions
    try:
        os_path = settings.UPLOAD_DIRECTORY
        if not os.path.exists(os_path):
            os.makedirs(os_path, exist_ok=True)
    except Exception as e:
        health_status["storage"] = f"Unhealthy: {str(e)}"
        health_status["status"] = "Unhealthy"
        
    return health_status

@health_router.get("/ready")
def get_ready(db: Session = Depends(get_db)):
    health = get_health(db)
    if health["status"] == "Healthy":
        return {"status": "READY"}
    return {"status": "NOT_READY", "details": health}

@health_router.get("/metrics")
def get_metrics(db: Session = Depends(get_db)):
    # Query database totals
    total_projects = db.query(Project).count()
    total_analyses = db.query(Analysis).count()
    total_fixes = db.query(FixExecution).count()
    total_tests = db.query(TestExecution).count()
    
    # Query queue size and workers telemetry from Redis
    queue_size = 0
    active_workers = 1
    total_jobs_run = 0
    total_jobs_failed = 0
    
    try:
        queue_size = redis_service.client.llen("task_queue") or 0
        active_workers = int(redis_service.client.get("metrics:active_workers") or 1)
        total_jobs_run = int(redis_service.client.get("metrics:total_jobs_run") or 0)
        total_jobs_failed = int(redis_service.client.get("metrics:total_jobs_failed") or 0)
    except Exception:
        pass
        
    total_jobs = total_jobs_run + total_jobs_failed
    
    # Calculate real average processing time from completed analyses
    avg_dur = db.query(func.avg(Analysis.duration)).filter(Analysis.status == "completed").scalar()
    avg_latency = round(float(avg_dur), 2) if avg_dur is not None else "N/A"

    # Calculate real failure rate from analyses or jobs
    failed_analyses = db.query(Analysis).filter(Analysis.status == "failed").count()
    if total_analyses > 0:
        failure_rate = f"{(failed_analyses / total_analyses * 100):.1f}%"
    elif total_jobs > 0:
        failure_rate = f"{(total_jobs_failed / total_jobs * 100):.1f}%"
    else:
        failure_rate = "0.0%"

    try:
        cache_hits = int(redis_service.client.get("metrics:cache_hits") or 0)
        cache_misses = int(redis_service.client.get("metrics:cache_misses") or 0)
    except Exception:
        cache_hits = 0
        cache_misses = 0
    
    return {
        "projects": total_projects,
        "analyses": total_analyses,
        "fixes": total_fixes,
        "tests": total_tests,
        "queue_size": queue_size,
        "active_workers": active_workers,
        "average_processing_time": avg_latency,
        "failure_rate": failure_rate,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses
    }

from app.projects.services.diagnostics_service import DiagnosticsService

@health_router.get("/diagnostics")
def get_diagnostics(db: Session = Depends(get_db)):
    return DiagnosticsService.run_diagnostics(db)

