from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.auth.database.connection import get_db
from app.auth.dependencies import get_current_user
from app.auth.models.auth_models import User
from app.projects.models.project_models import Project, Analysis, Report
from app.projects.repositories.project_repository import ProjectRepository
from app.projects.services.analysis_service import AnalysisService

analysis_router = APIRouter(prefix="/analysis", tags=["AI Review Analysis"])


class RunAnalysisRequest(BaseModel):
    api_key: Optional[str] = Field(None, description="Optional Gemini API Key. If empty, local simulator is run.")


class AnalysisStatusResponse(BaseModel):
    id: int
    project_id: int
    status: str
    source_type: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None
    model_used: Optional[str] = None
    
    # Intelligent review pipeline fields (v1.5)
    modules_reviewed: Optional[str] = None
    files_reviewed: Optional[int] = None
    total_files: Optional[int] = None
    skipped_files: Optional[int] = None
    coverage_percentage: Optional[float] = None
    skipped_reasons_json: Optional[str] = None
    ai_calls: Optional[int] = None
    overall_confidence: Optional[float] = None
    pipeline_stages: Optional[str] = None

    class Config:
        from_attributes = True


class ReportDetailsResponse(BaseModel):
    id: int
    analysis_id: int
    score: int
    summary: str
    details_json: str
    created_at: datetime

    class Config:
        from_attributes = True


@analysis_router.post("/{project_id}/run", status_code=status.HTTP_201_CREATED, response_model=AnalysisStatusResponse)
async def run_project_analysis(
    project_id: int,
    req: RunAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Triggers an asynchronous AI review analysis on the latest ingested project files.
    """
    analysis = AnalysisService.start_analysis(
        db, 
        project_id=project_id, 
        user_id=current_user.id, 
        api_key=req.api_key
    )
    return analysis


@analysis_router.get("/{analysis_id}", response_model=AnalysisStatusResponse)
def get_analysis_status(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves the status of an ongoing or completed analysis run.
    """
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")

    # Verify project ownership
    project = ProjectRepository.get_project(db, analysis.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")

    return analysis


@analysis_router.get("/{analysis_id}/report", response_model=ReportDetailsResponse)
def get_analysis_report(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves the final review report associated with a completed analysis run.
    """
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")

    # Verify project ownership
    project = ProjectRepository.get_project(db, analysis.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")

    report = db.query(Report).filter(Report.analysis_id == analysis_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Report is not ready yet. Please check analysis run status."
        )

    return report
