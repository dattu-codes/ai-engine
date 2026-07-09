import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.auth.database.connection import get_db
from app.auth.dependencies import get_current_user
from app.auth.models.auth_models import User
from app.projects.models.project_models import Project, RepositoryInsight, RepositoryInsightHistory
from app.projects.services.repository_insights_service import RepositoryInsightsService
from app.projects.repositories.project_repository import ProjectRepository

insights_router = APIRouter(prefix="/projects", tags=["Repository Insights"])

def _get_or_create_insight(db: Session, project_id: int, user_id: int) -> RepositoryInsight:
    # 1. Fetch project with ownership verification
    project = ProjectRepository.get_project(db, project_id, user_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        
    insight = db.query(RepositoryInsight).filter(RepositoryInsight.project_id == project_id).first()
    if not insight:
        try:
            insight = RepositoryInsightsService.generate_insight(db, project_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate repository insights: {str(e)}"
            )
    return insight

@insights_router.get("/{id}/repository-insights")
def get_insights(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieves full repository assessment scores, technical debt status, and maturity metrics."""
    insight = _get_or_create_insight(db, id, current_user.id)
    return {
        "project_id": insight.project_id,
        "repository_score": insight.repository_score,
        "architecture_score": insight.architecture_score,
        "security_score": insight.security_score,
        "testing_score": insight.testing_score,
        "deployment_score": insight.deployment_score,
        "maintainability_score": insight.maintainability_score,
        "documentation_score": insight.documentation_score,
        "technical_debt_score": insight.technical_debt_score,
        "engineering_maturity": insight.engineering_maturity,
        "strengths": json.loads(insight.strengths_json),
        "weaknesses": json.loads(insight.weaknesses_json),
        "roadmap": json.loads(insight.roadmap_json),
        "summary": insight.summary,
        "created_at": insight.created_at,
        "updated_at": insight.updated_at
    }

@insights_router.get("/{id}/repository-score")
def get_repository_score(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieves the overall repository quality score (0-100)."""
    insight = _get_or_create_insight(db, id, current_user.id)
    return {"repository_score": insight.repository_score}

@insights_router.get("/{id}/repository-roadmap")
def get_repository_roadmap(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieves the prioritized engineering evolution roadmap recommendations."""
    insight = _get_or_create_insight(db, id, current_user.id)
    return json.loads(insight.roadmap_json)

@insights_router.get("/{id}/repository-strengths")
def get_repository_strengths(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieves list of key strengths identified in the codebase architecture."""
    insight = _get_or_create_insight(db, id, current_user.id)
    return json.loads(insight.strengths_json)

@insights_router.get("/{id}/repository-weaknesses")
def get_repository_weaknesses(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieves list of engineering weaknesses detected in the codebase."""
    insight = _get_or_create_insight(db, id, current_user.id)
    return json.loads(insight.weaknesses_json)

@insights_router.get("/{id}/repository-history")
def get_repository_history(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieves the historical trend of repository scores across completed code analyses."""
    project = ProjectRepository.get_project(db, id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        
    history = db.query(RepositoryInsightHistory).filter(
        RepositoryInsightHistory.project_id == id
    ).order_by(RepositoryInsightHistory.version_number.asc()).all()
    
    return [
        {
            "id": h.id,
            "version_number": h.version_number,
            "repository_score": h.repository_score,
            "created_at": h.created_at
        }
        for h in history
    ]

@insights_router.get("/{id}/engineering-maturity")
def get_engineering_maturity(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieves the engineering maturity stage of the repository."""
    insight = _get_or_create_insight(db, id, current_user.id)
    return {"engineering_maturity": insight.engineering_maturity}

@insights_router.get("/{id}/technical-debt")
def get_technical_debt(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieves the technical debt rating (Very Low to Critical) of the project."""
    insight = _get_or_create_insight(db, id, current_user.id)
    return {"technical_debt_score": insight.technical_debt_score}
