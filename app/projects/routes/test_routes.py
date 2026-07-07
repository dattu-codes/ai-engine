import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.auth.database.connection import get_db
from app.auth.dependencies import get_current_user
from app.auth.models.auth_models import User
from app.projects.repositories.project_repository import ProjectRepository
from app.projects.models.project_models import TestExecution, FixExecution
from app.projects.services.test_generation_service import TestGenerationService
from app.projects.services.test_runner_service import TestRunnerService
from app.projects.services.coverage_service import CoverageService
from app.projects.services.permission_service import PermissionService

class TestExecutionResponse(BaseModel):
    id: int
    project_id: int
    version_id: Optional[int] = None
    fix_execution_id: Optional[int] = None
    language: Optional[str] = None
    framework: Optional[str] = None
    test_type: Optional[str] = None
    generated_tests_json: Optional[str] = None
    execution_log: Optional[str] = None
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    coverage_percentage: float
    execution_time: Optional[float] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

test_router = APIRouter(tags=["AI Test Center"])

@test_router.post("/fixes/{id}/generate-tests", response_model=TestExecutionResponse)
async def generate_tests(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generates dynamic regression and unit test suite targeting the applied fix.
    """
    fix_exec = db.query(FixExecution).filter(FixExecution.id == id).first()
    if not fix_exec:
        raise HTTPException(status_code=404, detail="Fix execution not found")

    if not PermissionService.can_run_analysis(db, current_user.id, fix_exec.project_id):
        raise HTTPException(status_code=403, detail="Viewer role cannot generate test suites.")

    try:
        api_key = current_user.api_key if hasattr(current_user, "api_key") else None
        test_exec = await TestGenerationService.generate_tests(db, id, api_key=api_key)
        return test_exec
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@test_router.post("/tests/{id}/execute", response_model=TestExecutionResponse)
async def execute_tests(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Executes the generated test suite and compiles detailed test execution logs.
    """
    test_exec = db.query(TestExecution).filter(TestExecution.id == id).first()
    if not test_exec:
        raise HTTPException(status_code=404, detail="Test execution not found")

    if not PermissionService.can_run_analysis(db, current_user.id, test_exec.project_id):
        raise HTTPException(status_code=403, detail="Not authorized to run tests on this project.")

    try:
        updated = await TestRunnerService.execute_tests(db, id)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@test_router.get("/tests/{id}", response_model=TestExecutionResponse)
def get_test_execution(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves details and raw run logs for a specific test run.
    """
    test_exec = db.query(TestExecution).filter(TestExecution.id == id).first()
    if not test_exec:
        raise HTTPException(status_code=404, detail="Test execution not found")

    if not PermissionService.can_view_project(db, current_user.id, test_exec.project_id):
        raise HTTPException(status_code=403, detail="Not authorized to view details.")

    return test_exec

@test_router.get("/tests/{id}/coverage")
def get_test_coverage(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves detailed line, branch, function, and patch line coverage details.
    """
    test_exec = db.query(TestExecution).filter(TestExecution.id == id).first()
    if not test_exec:
        raise HTTPException(status_code=404, detail="Test execution not found")

    if not PermissionService.can_view_project(db, current_user.id, test_exec.project_id):
        raise HTTPException(status_code=403, detail="Not authorized.")

    # Re-run coverage calculation for reporting
    from app.projects.models.project_models import ProjectVersionFile
    vfs = db.query(ProjectVersionFile).filter(ProjectVersionFile.version_id == test_exec.version_id).all()
    
    modified_files = []
    if test_exec.fix_execution and test_exec.fix_execution.files_modified:
        try:
            modified_files = json.loads(test_exec.fix_execution.files_modified)
        except Exception:
            pass
            
    coverage_data = CoverageService.calculate_coverage(vfs, modified_files, test_exec.language)
    return coverage_data

@test_router.get("/projects/{project_id}/tests", response_model=List[TestExecutionResponse])
def get_project_tests(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves the execution history of all test suite runs for a project.
    """
    project = ProjectRepository.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or access denied")

    history = db.query(TestExecution).filter(TestExecution.project_id == project_id).order_by(TestExecution.created_at.desc()).all()
    return history
