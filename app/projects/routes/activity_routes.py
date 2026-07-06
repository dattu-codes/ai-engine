from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List

from app.auth.database.connection import get_db
from app.auth.dependencies import get_current_user
from app.auth.models.auth_models import User
from app.projects.models.project_models import ActivityLog, Project
from app.projects.services.permission_service import PermissionService

activity_router = APIRouter(tags=["Activities"])

@activity_router.get("/workspaces/{id}/activities")
def get_workspace_activities(
    id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    activity_type: Optional[str] = None,
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Permission check: must be member of workspace
    role = PermissionService.get_user_role(db, current_user.id, id)
    if not role:
        raise HTTPException(status_code=403, detail="Not authorized to view activities for this workspace.")

    query = db.query(ActivityLog).filter(ActivityLog.workspace_id == id)

    if search:
        query = query.filter(ActivityLog.description.ilike(f"%{search}%"))
    if activity_type:
        query = query.filter(ActivityLog.activity_type == activity_type)
    if user_id:
        query = query.filter(ActivityLog.user_id == user_id)
    if start_date:
        try:
            dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            query = query.filter(ActivityLog.created_at >= dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use ISO format.")
    if end_date:
        try:
            dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            query = query.filter(ActivityLog.created_at <= dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use ISO format.")

    # Sort descending by default
    query = query.order_by(ActivityLog.created_at.desc())
    
    total = query.count()
    logs = query.limit(limit).offset(offset).all()

    result = []
    for log in logs:
        user_obj = db.query(User).filter(User.id == log.user_id).first() if log.user_id else None
        result.append({
            "id": log.id,
            "workspace_id": log.workspace_id,
            "project_id": log.project_id,
            "user_id": log.user_id,
            "username": user_obj.username if user_obj else "System",
            "activity_type": log.activity_type,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "description": log.description,
            "metadata_json": log.metadata_json,
            "created_at": log.created_at.isoformat()
        })

    return {
        "total": total,
        "activities": result
    }

@activity_router.get("/projects/{id}/activities")
def get_project_activities(
    id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    activity_type: Optional[str] = None,
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Permission check: must have view access to project
    if not PermissionService.can_view_project(db, current_user.id, id):
        raise HTTPException(status_code=403, detail="Not authorized to view activities for this project.")

    query = db.query(ActivityLog).filter(ActivityLog.project_id == id)

    if search:
        query = query.filter(ActivityLog.description.ilike(f"%{search}%"))
    if activity_type:
        query = query.filter(ActivityLog.activity_type == activity_type)
    if user_id:
        query = query.filter(ActivityLog.user_id == user_id)
    if start_date:
        try:
            dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            query = query.filter(ActivityLog.created_at >= dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use ISO format.")
    if end_date:
        try:
            dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            query = query.filter(ActivityLog.created_at <= dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use ISO format.")

    # Sort descending by default
    query = query.order_by(ActivityLog.created_at.desc())
    
    total = query.count()
    logs = query.limit(limit).offset(offset).all()

    result = []
    for log in logs:
        user_obj = db.query(User).filter(User.id == log.user_id).first() if log.user_id else None
        result.append({
            "id": log.id,
            "workspace_id": log.workspace_id,
            "project_id": log.project_id,
            "user_id": log.user_id,
            "username": user_obj.username if user_obj else "System",
            "activity_type": log.activity_type,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "description": log.description,
            "metadata_json": log.metadata_json,
            "created_at": log.created_at.isoformat()
        })

    return {
        "total": total,
        "activities": result
    }
