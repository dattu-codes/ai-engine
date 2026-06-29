from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field

from app.auth.database.connection import get_db
from app.auth.dependencies import get_current_user
from app.auth.models.auth_models import User
from app.projects.models.project_models import Project, Analysis, AnalysisFile, Report
from app.projects.schemas.project_schemas import (
    ProjectCreate, ProjectRename, ProjectResponse, ProjectDetailsResponse,
    AnalysisResponse, FileMetadataResponse, ReportResponse
)
from app.projects.services.project_service import ProjectService
from app.projects.repositories.project_repository import ProjectRepository

project_router = APIRouter(prefix="/projects", tags=["Project Management"])


class RepositoryLinkRequest(BaseModel):
    repo_url: str = Field(..., description="HTTPS Git Repository URL")


@project_router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectResponse)
def create_project(req: ProjectCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Creates a new project for the authenticated user."""
    return ProjectService.create_project(db, current_user.id, req.name)


@project_router.get("", response_model=List[ProjectResponse])
def list_projects(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Lists all projects belonging to the authenticated user."""
    return ProjectService.get_projects(db, current_user.id)


@project_router.get("/{id}", response_model=ProjectDetailsResponse)
def get_project(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieves project details, file counts, and languages used in the latest run."""
    return ProjectService.get_project_details(db, id, current_user.id)


@project_router.put("/{id}", response_model=ProjectResponse)
def rename_project(id: int, req: ProjectRename, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Renames an existing user project."""
    return ProjectService.rename_project(db, id, current_user.id, req.name)


@project_router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Deletes a project and all associated analyses, files, and reports."""
    ProjectService.delete_project(db, id, current_user.id)
    return None


@project_router.post("/{id}/upload", response_model=AnalysisResponse)
async def upload_source(
    id: int,
    file: Optional[UploadFile] = File(None),
    pasted_filename: Optional[str] = Form(None),
    pasted_content: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Accepts source code ingestion for a project.
    Can ingest a ZIP archive containing files, OR a single pasted code snippet with its target filename.
    """
    if file:
        zip_bytes = await file.read()
        return ProjectService.upload_project_zip(db, id, current_user.id, zip_bytes)
    elif pasted_filename and pasted_content:
        return ProjectService.paste_project_code(db, id, current_user.id, pasted_filename, pasted_content)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either upload a ZIP file or provide pasted_filename and pasted_content."
        )


@project_router.post("/{id}/repository", response_model=AnalysisResponse)
def link_repository(id: int, req: RepositoryLinkRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Saves a Git repository URL linkage metadata (architecture placeholder)."""
    return ProjectService.save_project_repository(db, id, current_user.id, req.repo_url)


@project_router.get("/{id}/files", response_model=List[FileMetadataResponse])
def get_project_files(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Lists files associated with the latest completed analysis run in the project."""
    # Verify project ownership first
    project = ProjectRepository.get_project(db, id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    latest_analysis = ProjectRepository.get_latest_analysis(db, id)
    if not latest_analysis:
        return []

    return ProjectRepository.get_analysis_files(db, latest_analysis.id)


@project_router.get("/{id}/history", response_model=List[AnalysisResponse])
def get_project_history(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieves all historical analysis runs for this project."""
    # Verify project ownership first
    project = ProjectRepository.get_project(db, id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    return ProjectRepository.get_project_analyses(db, id)


@project_router.get("/{id}/report", response_model=Optional[ReportResponse])
def get_project_latest_report(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieves the quality report associated with the latest completed analysis run."""
    project = ProjectRepository.get_project(db, id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    latest_analysis = ProjectRepository.get_latest_analysis(db, id)
    if not latest_analysis:
        return None

    return ProjectRepository.get_latest_report(db, latest_analysis.id)
