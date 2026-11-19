from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, List

from app.auth.database.connection import get_db
from app.auth.dependencies import get_current_user
from app.auth.models.auth_models import User
from app.projects.models.project_models import Project, Analysis, AnalysisFile, ActivityLog
from app.projects.services.redis_service import redis_service

router = APIRouter(prefix="/admin", tags=["Admin Portal"])

def require_admin(current_user: User = Depends(get_current_user)):
    """Verifies that the caller has admin permissions."""
    if current_user.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to access this portal"
        )
    return current_user

@router.get("/stats", dependencies=[Depends(require_admin)])
def get_system_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Exposes infrastructure health, daemon worker queues, and diagnostics errors list."""
    # Count totals
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    verified_users = db.query(User).filter(User.is_verified == True).count()
    github_users = db.query(User).filter(User.github_connected == True).count()
    
    # Active background worker telemetry
    active_workers = 1
    try:
        active_workers = int(redis_service.client.get("metrics:active_workers") or 1)
        queue_size = redis_service.client.llen("task_queue") or 0
    except Exception:
        queue_size = 0
        
    # Storage usage metrics
    total_files = db.query(AnalysisFile).count()
    # Compute size of all stored source files
    try:
        storage_sum = db.query(func.coalesce(func.sum(AnalysisFile.size), 0)).scalar()
        total_storage_bytes = int(storage_sum) if storage_sum is not None else 0
    except Exception:
        total_storage_bytes = "N/A"

    # System status flags
    db_status = "Healthy"
    if getattr(redis_service, "is_mock", False):
        redis_status = "Degraded"
    else:
        try:
            redis_service.client.ping()
            redis_status = "Healthy"
        except Exception:
            redis_status = "Degraded"
        
    # Real system activity/diagnostic logs
    recent_logs = db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(20).all()
    diagnostic_logs = [
        {
            "timestamp": log.created_at.isoformat() if log.created_at else "N/A",
            "level": "INFO",
            "message": f"[{log.activity_type}] {log.description}"
        }
        for log in recent_logs
    ]

    return {
        "total_users": total_users,
        "active_users": active_users,
        "verified_users": verified_users,
        "github_connected_users": github_users,
        "active_workers": active_workers,
        "queue_size": queue_size,
        "total_files": total_files,
        "storage_utilized_bytes": total_storage_bytes,
        "integrations": {
            "database": db_status,
            "redis": redis_status
        },
        "errors_list": diagnostic_logs
    }

@router.get("/users", dependencies=[Depends(require_admin)])
def list_users(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Lists users registered on the platform."""
    users = db.query(User).order_by(User.id.asc()).all()
    results = []
    for u in users:
        results.append({
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "github_connected": u.github_connected,
            "created_at": u.created_at.isoformat()
        })
    return results

@router.post("/users/{id}/toggle-status", dependencies=[Depends(require_admin)])
def toggle_user_active_status(id: int, db: Session = Depends(get_db)):
    """Enables or suspends a user's account state."""
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Toggle active status
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    
    status_label = "active" if user.is_active else "suspended"
    return {"status": "success", "message": f"User {user.username} is now {status_label}."}

# Help function for SQLAlchemy sum query
from sqlalchemy import func
