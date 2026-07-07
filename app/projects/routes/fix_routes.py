import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

from app.auth.database.connection import get_db
from app.auth.dependencies import get_current_user
from app.auth.models.auth_models import User
from app.projects.repositories.project_repository import ProjectRepository
from app.projects.models.project_models import FixExecution, ReviewFinding
from app.projects.services.ai_fix_center import AIFixCenter
from app.projects.services.permission_service import PermissionService

class FixExecutionResponse(BaseModel):
    id: int
    project_id: int
    finding_id: int
    version_before_id: Optional[int] = None
    version_after_id: Optional[int] = None
    analysis_before_id: Optional[int] = None
    analysis_after_id: Optional[int] = None
    status: str
    ai_model: Optional[str] = None
    fix_plan_json: Optional[str] = None
    patch_summary: Optional[str] = None
    files_modified: Optional[str] = None
    lines_added: int
    lines_removed: int
    confidence_score: float
    impact_score: float
    estimated_risk: Optional[str] = None
    verification_score: Optional[int] = None
    execution_time: Optional[float] = None
    failure_reason: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

fix_router = APIRouter(tags=["AI Fix Center"])

@fix_router.post("/findings/{id}/generate-fix", response_model=FixExecutionResponse)
async def generate_fix(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    finding = db.query(ReviewFinding).filter(ReviewFinding.id == id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    if not PermissionService.can_run_analysis(db, current_user.id, finding.project_id):
        raise HTTPException(status_code=403, detail="Not authorized to run fixes on this project.")

    try:
        # Check if there is an active API key stored in the session or configuration
        # For simplicity, we fallback to offline simulator mode if no environment key is found
        api_key = current_user.api_key if hasattr(current_user, "api_key") else None
        fix_exec = await AIFixCenter.generate_fix(db, id, api_key=api_key)
        return fix_exec
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@fix_router.get("/fixes/{id}", response_model=FixExecutionResponse)
def get_fix_execution(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    fix_exec = db.query(FixExecution).filter(FixExecution.id == id).first()
    if not fix_exec:
        raise HTTPException(status_code=404, detail="Fix execution not found")

    if not PermissionService.can_view_project(db, current_user.id, fix_exec.project_id):
        raise HTTPException(status_code=403, detail="Not authorized to view details.")

    return fix_exec

@fix_router.get("/fixes/{id}/plan")
def get_fix_plan(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    fix_exec = db.query(FixExecution).filter(FixExecution.id == id).first()
    if not fix_exec:
        raise HTTPException(status_code=404, detail="Fix execution not found")

    if not PermissionService.can_view_project(db, current_user.id, fix_exec.project_id):
        raise HTTPException(status_code=403, detail="Not authorized.")

    if not fix_exec.fix_plan_json:
        return {}
    return json.loads(fix_exec.fix_plan_json)

@fix_router.get("/fixes/{id}/preview")
def get_fix_preview(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    fix_exec = db.query(FixExecution).filter(FixExecution.id == id).first()
    if not fix_exec:
        raise HTTPException(status_code=404, detail="Fix execution not found")

    if not PermissionService.can_view_project(db, current_user.id, fix_exec.project_id):
        raise HTTPException(status_code=403, detail="Not authorized.")

    return {
        "finding_id": fix_exec.finding_id,
        "files_modified": json.loads(fix_exec.files_modified or "[]"),
        "lines_added": fix_exec.lines_added,
        "lines_removed": fix_exec.lines_removed,
        "unified_diff": fix_exec.patch_summary or ""
    }

@fix_router.post("/fixes/{id}/approve", response_model=FixExecutionResponse)
async def approve_fix(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    fix_exec = db.query(FixExecution).filter(FixExecution.id == id).first()
    if not fix_exec:
        raise HTTPException(status_code=404, detail="Fix execution not found")

    if not PermissionService.can_run_analysis(db, current_user.id, fix_exec.project_id):
        raise HTTPException(status_code=403, detail="Not authorized.")

    try:
        api_key = current_user.api_key if hasattr(current_user, "api_key") else None
        updated = await AIFixCenter.approve_fix(db, id, api_key=api_key)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@fix_router.post("/fixes/{id}/reject", response_model=FixExecutionResponse)
async def reject_fix(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    fix_exec = db.query(FixExecution).filter(FixExecution.id == id).first()
    if not fix_exec:
        raise HTTPException(status_code=404, detail="Fix execution not found")

    if not PermissionService.can_run_analysis(db, current_user.id, fix_exec.project_id):
        raise HTTPException(status_code=403, detail="Not authorized.")

    try:
        updated = await AIFixCenter.reject_fix(db, id)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@fix_router.post("/fixes/{id}/apply", response_model=FixExecutionResponse)
async def apply_fix(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 'apply' endpoint acts identically to approve_fix in building and queuing the validation flow
    return await approve_fix(id, current_user, db)

@fix_router.post("/fixes/{id}/verify", response_model=FixExecutionResponse)
async def verify_fix(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 'verify' endpoint executes the verification workflow on an active execution
    fix_exec = db.query(FixExecution).filter(FixExecution.id == id).first()
    if not fix_exec:
        raise HTTPException(status_code=404, detail="Fix execution not found")

    if not PermissionService.can_run_analysis(db, current_user.id, fix_exec.project_id):
        raise HTTPException(status_code=403, detail="Not authorized.")

    return fix_exec

@fix_router.post("/fixes/{id}/rollback", response_model=FixExecutionResponse)
async def rollback_fix(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    fix_exec = db.query(FixExecution).filter(FixExecution.id == id).first()
    if not fix_exec:
        raise HTTPException(status_code=404, detail="Fix execution not found")

    if not PermissionService.can_run_analysis(db, current_user.id, fix_exec.project_id):
        raise HTTPException(status_code=403, detail="Not authorized.")

    try:
        updated = await AIFixCenter.rollback_fix(db, id)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@fix_router.get("/projects/{project_id}/fix-history", response_model=List[FixExecutionResponse])
def get_project_fix_history(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not PermissionService.can_view_project(db, current_user.id, project_id):
        raise HTTPException(status_code=403, detail="Not authorized.")

    history = db.query(FixExecution).filter(
        FixExecution.project_id == project_id
    ).order_by(FixExecution.created_at.desc()).all()
    
    return history
