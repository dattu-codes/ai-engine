import secrets
import hashlib
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from app.auth.database.connection import get_db
from app.auth.models.auth_models import User, ApiKey
from app.auth.dependencies import get_current_user
from app.projects.models.project_models import Project, Analysis, ReviewFinding, RepositoryInsight
from app.projects.repositories.project_repository import ProjectRepository
from app.projects.services.analysis_service import AnalysisService

router = APIRouter(prefix="/api/v1", tags=["Public REST API v1"])
key_router = APIRouter(prefix="/auth/api-key", tags=["API Key Management"])

# Dependency to authenticate using X-API-KEY header
def get_api_key_user(
    x_api_key: str = Header(..., alias="X-API-KEY"),
    db: Session = Depends(get_db)
) -> User:
    """Authenticates public API requests using X-API-KEY header."""
    key_hash = hashlib.sha256(x_api_key.strip().encode("utf-8")).hexdigest()
    api_key_rec = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active == True
    ).first()
    
    if not api_key_rec:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or deactivated API Key"
        )
        
    if api_key_rec.expires_at and api_key_rec.expires_at < datetime.utcnow():
        api_key_rec.is_active = False
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key has expired"
        )
        
    user = db.query(User).filter(User.id == api_key_rec.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive or disabled"
        )
    return user

# API Key Management Router (for logged-in UI dashboard users)
@key_router.post("")
def create_api_key(
    name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generates a new API Key for the user. Returns raw key once."""
    raw_key = "ae_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    
    api_key_rec = ApiKey(
        user_id=current_user.id,
        key_hash=key_hash,
        name=name,
        expires_at=datetime.utcnow() + timedelta(days=365) # 1 year validity
    )
    db.add(api_key_rec)
    db.commit()
    db.refresh(api_key_rec)
    
    return {
        "id": api_key_rec.id,
        "name": api_key_rec.name,
        "api_key": raw_key, # Exposed only once
        "expires_at": api_key_rec.expires_at.isoformat()
    }

@key_router.get("")
def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists current user's active API keys."""
    keys = db.query(ApiKey).filter(
        ApiKey.user_id == current_user.id,
        ApiKey.is_active == True
    ).all()
    return [
        {
            "id": k.id,
            "name": k.name,
            "created_at": k.created_at.isoformat(),
            "expires_at": k.expires_at.isoformat() if k.expires_at else None
        }
        for k in keys
    ]

@key_router.delete("/{id}")
def delete_api_key(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revokes / deactivates an API key."""
    key = db.query(ApiKey).filter(
        ApiKey.id == id,
        ApiKey.user_id == current_user.id
    ).first()
    
    if not key:
        raise HTTPException(status_code=404, detail="API Key not found")
        
    key.is_active = False
    db.commit()
    return {"status": "success", "message": "API key revoked."}

# Public REST API v1 Router
@router.get("/projects")
def list_v1_projects(
    user: User = Depends(get_api_key_user),
    db: Session = Depends(get_db)
):
    """List all projects associated with the authenticated account."""
    projects = db.query(Project).filter(Project.user_id == user.id).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "repo_url": p.repo_url,
            "project_type": p.project_type,
            "total_lines": p.total_lines,
            "created_at": p.created_at.isoformat()
        }
        for p in projects
    ]

@router.post("/projects")
def create_v1_project(
    name: str,
    repo_url: Optional[str] = None,
    user: User = Depends(get_api_key_user),
    db: Session = Depends(get_db)
):
    """Create a new project via API."""
    # Apply billing limits checks
    from app.billing.services.billing_service import BillingService
    BillingService.check_billing_limit(db, user, "projects")
    
    project = Project(
        user_id=user.id,
        name=name,
        repo_url=repo_url
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    
    return {
        "id": project.id,
        "name": project.name,
        "repo_url": project.repo_url,
        "created_at": project.created_at.isoformat()
    }

@router.post("/projects/{id}/analyses")
def run_v1_analysis(
    id: int,
    user: User = Depends(get_api_key_user),
    db: Session = Depends(get_db)
):
    """Triggers an asynchronous code review analysis for a project."""
    # Ownership check
    project = db.query(Project).filter(Project.id == id, Project.user_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    analysis = AnalysisService.start_analysis(db, project_id=id, user_id=user.id, api_key=None)
    return {
        "analysis_id": analysis.id,
        "status": analysis.status,
        "created_at": analysis.created_at.isoformat()
    }

@router.get("/projects/{id}/findings")
def get_v1_findings(
    id: int,
    user: User = Depends(get_api_key_user),
    db: Session = Depends(get_db)
):
    """Retrieves all static review findings of a project."""
    project = db.query(Project).filter(Project.id == id, Project.user_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    findings = db.query(ReviewFinding).filter(ReviewFinding.project_id == id).all()
    return [
        {
            "id": f.id,
            "file_path": f.file_path,
            "line_number": f.line_number,
            "category": f.category,
            "severity": f.severity,
            "title": f.title,
            "description": f.description,
            "recommendation": f.recommendation
        }
        for f in findings
    ]

@router.get("/projects/{id}/insights")
def get_v1_insights(
    id: int,
    user: User = Depends(get_api_key_user),
    db: Session = Depends(get_db)
):
    """Retrieves latest calculated repository insights scores."""
    project = db.query(Project).filter(Project.id == id, Project.user_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    insight = db.query(RepositoryInsight).filter(RepositoryInsight.project_id == id).first()
    if not insight:
        raise HTTPException(status_code=404, detail="Repository insights not computed yet")
        
    import json
    return {
        "repository_score": insight.repository_score,
        "architecture_score": insight.architecture_score,
        "security_score": insight.security_score,
        "testing_score": insight.testing_score,
        "deployment_score": insight.deployment_score,
        "maintainability_score": insight.maintainability_score,
        "documentation_score": insight.documentation_score,
        "technical_debt": insight.technical_debt_score,
        "maturity_level": insight.engineering_maturity
    }
