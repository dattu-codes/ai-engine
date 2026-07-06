from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.auth.database.connection import get_db
from app.auth.dependencies import get_current_user
from app.auth.models.auth_models import User
from app.projects.repositories.project_repository import ProjectRepository
from app.projects.models.project_models import ReviewFinding
from app.projects.services.review_finding_service import ReviewFindingService
from app.projects.services.permission_service import PermissionService

# Define Pydantic request / response schemas
class StatusUpdateRequest(BaseModel):
    status: str

class AssignRequest(BaseModel):
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None

class IgnoreRequest(BaseModel):
    reason: Optional[str] = None

class ReviewFindingResponse(BaseModel):
    id: int
    project_id: int
    analysis_id: Optional[int] = None
    resolved_in_version_id: Optional[int] = None
    file_path: str
    line_number: int
    category: str
    severity: str
    title: str
    description: str
    recommendation: str
    confidence: float
    status: str
    assigned_to: Optional[str] = None
    assigned_by: Optional[int] = None
    assigned_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    ignored_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True

finding_router = APIRouter(tags=["Review Findings"])

@finding_router.get("/projects/{project_id}/findings", response_model=List[ReviewFindingResponse])
def get_project_findings(
    project_id: int,
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = ProjectRepository.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    query = db.query(ReviewFinding).filter(ReviewFinding.project_id == project_id)
    if status:
        query = query.filter(ReviewFinding.status == status)
    if severity:
        query = query.filter(ReviewFinding.severity == severity.lower())
    if category:
        query = query.filter(ReviewFinding.category == category)
        
    return query.order_by(ReviewFinding.id.asc()).all()


@finding_router.get("/findings/{finding_id}", response_model=ReviewFindingResponse)
def get_finding_by_id(
    finding_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    finding = db.query(ReviewFinding).filter(ReviewFinding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
        
    # Check project ownership
    project = ProjectRepository.get_project(db, finding.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized to access this finding")
        
    return finding


@finding_router.patch("/findings/{finding_id}/status", response_model=ReviewFindingResponse)
def update_status(
    finding_id: int,
    req: StatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    finding = db.query(ReviewFinding).filter(ReviewFinding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    
    project = ProjectRepository.get_project(db, finding.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized to update this finding")
        
    if not PermissionService.can_assign_findings(db, current_user.id, finding.project_id):
        raise HTTPException(status_code=403, detail="Viewer role cannot update finding status.")
        
    try:
        updated = ReviewFindingService.update_finding_status(db, finding_id, req.status, current_user.id)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@finding_router.patch("/findings/{finding_id}/assign", response_model=ReviewFindingResponse)
def assign_finding(
    finding_id: int,
    req: AssignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    finding = db.query(ReviewFinding).filter(ReviewFinding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    
    project = ProjectRepository.get_project(db, finding.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized to assign this finding")
        
    if not PermissionService.can_assign_findings(db, current_user.id, finding.project_id):
        raise HTTPException(status_code=403, detail="Viewer role cannot assign findings.")
        
    return ReviewFindingService.assign_finding(db, finding_id, req.assigned_to, current_user.id, req.due_date)


@finding_router.patch("/findings/{finding_id}/ignore", response_model=ReviewFindingResponse)
def ignore_finding(
    finding_id: int,
    req: IgnoreRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    finding = db.query(ReviewFinding).filter(ReviewFinding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    
    project = ProjectRepository.get_project(db, finding.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized to ignore this finding")
        
    if not PermissionService.can_assign_findings(db, current_user.id, finding.project_id):
        raise HTTPException(status_code=403, detail="Viewer role cannot ignore findings.")
        
    return ReviewFindingService.ignore_finding(db, finding_id, req.reason, current_user.id)


@finding_router.patch("/findings/{finding_id}/reopen", response_model=ReviewFindingResponse)
def reopen_finding(
    finding_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    finding = db.query(ReviewFinding).filter(ReviewFinding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    
    project = ProjectRepository.get_project(db, finding.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized to reopen this finding")
        
    if not PermissionService.can_assign_findings(db, current_user.id, finding.project_id):
        raise HTTPException(status_code=403, detail="Viewer role cannot reopen findings.")
        
    return ReviewFindingService.reopen_finding(db, finding_id, current_user.id)


@finding_router.get("/projects/{project_id}/findings/history")
def get_project_findings_history(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = ProjectRepository.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    return ReviewFindingService.get_findings_history(db, project_id)
