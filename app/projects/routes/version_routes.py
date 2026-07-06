from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.auth.database.connection import get_db
from app.auth.dependencies import get_current_user
from app.auth.models.auth_models import User
from app.projects.repositories.project_repository import ProjectRepository
from app.projects.models.project_models import ProjectVersion, ProjectVersionFile, Analysis, AnalysisFile
from app.projects.schemas.project_schemas import ProjectVersionResponse, VersionComparisonResponse, ApplyFixRequest
from app.projects.services.version_service import VersionService
from app.projects.services.comparison_service import ComparisonService
from app.projects.services.snapshot_service import SnapshotService
from app.projects.services.analysis_service import AnalysisService
from app.projects.services.permission_service import PermissionService

version_router = APIRouter(prefix="/projects/{project_id}/versions", tags=["Project Versioning"])


@version_router.get("", response_model=List[ProjectVersionResponse])
def list_versions(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves the chronological version history list for the project.
    """
    project = ProjectRepository.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    return VersionService.get_version_history(db, project_id)


@version_router.post("/{version_id}/restore", response_model=ProjectVersionResponse)
async def restore_version(
    project_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Restores project files back to a previous version snapshot, creating a new head version.
    """
    project = ProjectRepository.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if not PermissionService.can_restore_version(db, current_user.id, project_id):
        raise HTTPException(status_code=403, detail="Viewer role cannot restore versions.")

    try:
        new_version = VersionService.restore_version(db, project_id, version_id, current_user.id)
        
        # Replicate version files to a new Analysis run so we can run review on it
        analysis = ProjectRepository.create_analysis(
            db,
            project_id=project_id,
            source_type="restore",
            status="completed"
        )
        analysis.created_by = current_user.id
        
        vf_files = db.query(ProjectVersionFile).filter(ProjectVersionFile.version_id == new_version.id).all()
        for vf in vf_files:
            ProjectRepository.create_analysis_file(
                db=db,
                analysis_id=analysis.id,
                filename=vf.filename,
                extension=vf.extension,
                size=vf.size,
                language=vf.language,
                file_hash=vf.hash,
                content=vf.content
            )
            
        new_version.source_analysis_id = analysis.id
        db.commit()
        db.refresh(new_version)
        
        # Trigger background analysis report generation for the restored code state
        AnalysisService.start_analysis(db, project_id, current_user.id)
        
        return new_version
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@version_router.get("/{version_id}/download")
def download_version(
    project_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Downloads the project files at the specified version snapshot as a ZIP archive.
    """
    project = ProjectRepository.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    version = db.query(ProjectVersion).filter(
        ProjectVersion.id == version_id,
        ProjectVersion.project_id == project_id
    ).first()
    
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version snapshot not found")

    files = db.query(ProjectVersionFile).filter(ProjectVersionFile.version_id == version.id).all()
    zip_bytes = SnapshotService.create_zip_archive(files)

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=project_{project_id}_v{version.version_number}.zip",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )


@version_router.get("/compare/details", response_model=VersionComparisonResponse)
def compare_versions(
    project_id: int,
    v1_id: int = Query(..., description="Older project version ID"),
    v2_id: int = Query(..., description="Newer project version ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Compares two project version snapshots, returning diffs, file deltas, and fixed issue listings.
    """
    project = ProjectRepository.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        comparison = ComparisonService.compare_versions(db, v1_id, v2_id)
        return comparison
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@version_router.post("/apply-fix", response_model=ProjectVersionResponse)
async def apply_ai_fix(
    project_id: int,
    req: ApplyFixRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Applies a code modification to fix a finding, creates a new version, and schedules a review analysis.
    """
    project = ProjectRepository.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if not PermissionService.can_apply_fix(db, current_user.id, project_id):
        raise HTTPException(status_code=403, detail="Viewer role cannot apply AI fixes.")

    try:
        # Apply the fix and create a new head version snapshot
        new_version = await VersionService.apply_fix_and_create_version(
            db=db,
            project_id=project_id,
            issue=req.issue,
            api_key=req.api_key,
            user_id=current_user.id
        )

        # Replicate version files to a completed Analysis so the review pipeline has access to them
        analysis = ProjectRepository.create_analysis(
            db,
            project_id=project_id,
            source_type="fix_applied",
            status="completed"
        )
        analysis.created_by = current_user.id
        
        vf_files = db.query(ProjectVersionFile).filter(ProjectVersionFile.version_id == new_version.id).all()
        for vf in vf_files:
            ProjectRepository.create_analysis_file(
                db=db,
                analysis_id=analysis.id,
                filename=vf.filename,
                extension=vf.extension,
                size=vf.size,
                language=vf.language,
                file_hash=vf.hash,
                content=vf.content
            )

        new_version.source_analysis_id = analysis.id
        db.commit()
        db.refresh(new_version)

        # Trigger analysis review on the newly modified version files
        review_analysis = AnalysisService.start_analysis(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
            api_key=req.api_key
        )

        # Associate version to the running review analysis
        new_version.source_analysis_id = review_analysis.id
        db.commit()
        db.refresh(new_version)

        return new_version
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
