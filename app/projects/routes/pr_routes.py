import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.auth.database.connection import get_db
from app.auth.dependencies import get_current_user
from app.auth.models.auth_models import User
from app.projects.models.project_models import Project, Analysis, Report, PullRequest
from app.projects.repositories.project_repository import ProjectRepository
from app.projects.services.github_pr_service import GitHubPRService
from app.projects.services.incremental_review_service import IncrementalReviewService
from app.projects.services.pr_summary_service import PRSummaryService
from app.projects.services.git_service import GitService

pr_router = APIRouter(tags=["Pull Requests"])


# --- Schemas ---

class PRReviewRequest(BaseModel):
    pull_request_number: int = Field(..., description="GitHub Pull Request Number")


class PRAnalysisItem(BaseModel):
    id: int
    status: str
    created_at: datetime
    score: Optional[int] = None

    class Config:
        from_attributes = True


class PullRequestResponse(BaseModel):
    id: int
    project_id: int
    github_pr_number: int
    title: str
    author: str
    base_branch: str
    head_branch: str
    status: str
    files_changed: int
    additions: int
    deletions: int
    commits: int
    latest_analysis_id: Optional[int] = None
    pr_files_json: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    analyses: List[PRAnalysisItem] = []

    class Config:
        from_attributes = True


class PRSummaryResponse(BaseModel):
    score: int
    summary: str
    severity_distribution: Dict[str, int]
    risk_assessment: str
    processing_metrics: Dict[str, Any]
    statistics: Dict[str, int]


# --- Endpoints ---

@pr_router.post("/projects/{id}/pull-requests/review", status_code=status.HTTP_201_CREATED, response_model=PullRequestResponse)
async def trigger_pull_request_review(
    id: int,
    req: PRReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually triggers an incremental review for the specified Pull Request number.
    """
    # 1. Verify project exists and belongs to current user
    project = ProjectRepository.get_project(db, id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # 2. Extract repo owner and name
    owner, repo = "mock-owner", "mock-repo"
    if project.repo_url:
        is_valid, extracted_owner, extracted_repo = GitService.validate_url(project.repo_url)
        if is_valid:
            owner, repo = extracted_owner, extracted_repo

    # 3. Fetch details and files list with patches from GitHub (or mock)
    try:
        pr_details = GitHubPRService.fetch_pr_details(owner, repo, req.pull_request_number)
        pr_files = GitHubPRService.fetch_pr_files(owner, repo, req.pull_request_number)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API integration failed: {str(e)}"
        )

    # 4. Check if PullRequest record already exists
    pr = db.query(PullRequest).filter(
        PullRequest.project_id == id,
        PullRequest.github_pr_number == req.pull_request_number
    ).first()

    if not pr:
        pr = PullRequest(
            project_id=id,
            github_pr_number=req.pull_request_number,
            title=pr_details["title"],
            author=pr_details["author"],
            base_branch=pr_details["base_branch"],
            head_branch=pr_details["head_branch"],
            status=pr_details["status"],
            files_changed=pr_details["files_changed"],
            additions=pr_details["additions"],
            deletions=pr_details["deletions"],
            commits=pr_details["commits"],
            pr_files_json=json.dumps(pr_files)
        )
        db.add(pr)
    else:
        pr.title = pr_details["title"]
        pr.author = pr_details["author"]
        pr.base_branch = pr_details["base_branch"]
        pr.head_branch = pr_details["head_branch"]
        pr.status = pr_details["status"]
        pr.files_changed = pr_details["files_changed"]
        pr.additions = pr_details["additions"]
        pr.deletions = pr_details["deletions"]
        pr.commits = pr_details["commits"]
        pr.pr_files_json = json.dumps(pr_files)
        pr.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(pr)

    # 5. Start the incremental review
    analysis = await IncrementalReviewService.start_pr_review(
        db=db,
        project_id=id,
        pr_id=pr.id,
        changed_files=pr_files
    )
    
    pr.latest_analysis_id = analysis.id
    db.commit()
    db.refresh(pr)

    return pr


@pr_router.get("/projects/{id}/pull-requests", response_model=List[PullRequestResponse])
def get_project_pull_requests(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves all registered Pull Requests for a project.
    """
    project = ProjectRepository.get_project(db, id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    prs = db.query(PullRequest).filter(PullRequest.project_id == id).order_by(PullRequest.github_pr_number.desc()).all()
    return prs


@pr_router.get("/pull-requests/{id}", response_model=PullRequestResponse)
def get_pull_request_details(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves metadata details for a single Pull Request.
    """
    pr = db.query(PullRequest).filter(PullRequest.id == id).first()
    if not pr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pull Request not found")

    # Verify project ownership
    project = ProjectRepository.get_project(db, pr.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pull Request not found")

    return pr


@pr_router.get("/pull-requests/{id}/summary", response_model=PRSummaryResponse)
def get_pull_request_summary(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves calculated scores and statistics for the Pull Request.
    """
    pr = db.query(PullRequest).filter(PullRequest.id == id).first()
    if not pr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pull Request not found")

    # Verify project ownership
    project = ProjectRepository.get_project(db, pr.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pull Request not found")

    if not pr.latest_analysis_id:
        return {
            "score": 0,
            "summary": "Review analysis has not been triggered yet.",
            "severity_distribution": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "risk_assessment": "low",
            "processing_metrics": {"duration": 0.0, "ai_calls": 0},
            "statistics": {"files_count": 0, "lines_count": 0}
        }

    return PRSummaryService.generate_summary(db, pr.latest_analysis_id)


@pr_router.get("/pull-requests/{id}/findings", response_model=List[Dict[str, Any]])
def get_pull_request_findings(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves the list of issues detected during the latest Pull Request analysis.
    """
    pr = db.query(PullRequest).filter(PullRequest.id == id).first()
    if not pr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pull Request not found")

    # Verify project ownership
    project = ProjectRepository.get_project(db, pr.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pull Request not found")

    if not pr.latest_analysis_id:
        return []

    report = db.query(Report).filter(Report.analysis_id == pr.latest_analysis_id).first()
    if not report or not report.details_json:
        return []

    try:
        details = json.loads(report.details_json)
        return details.get("issues", [])
    except Exception:
        return []


@pr_router.post("/pull-requests/{id}/refresh", response_model=PullRequestResponse)
def refresh_pull_request_metadata(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Refreshes the PR metadata dynamically from the GitHub REST API.
    """
    pr = db.query(PullRequest).filter(PullRequest.id == id).first()
    if not pr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pull Request not found")

    project = ProjectRepository.get_project(db, pr.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pull Request not found")

    owner, repo = "mock-owner", "mock-repo"
    if project.repo_url:
        is_valid, extracted_owner, extracted_repo = GitService.validate_url(project.repo_url)
        if is_valid:
            owner, repo = extracted_owner, extracted_repo

    try:
        pr_details = GitHubPRService.fetch_pr_details(owner, repo, pr.github_pr_number)
        pr_files = GitHubPRService.fetch_pr_files(owner, repo, pr.github_pr_number)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API refresh failed: {str(e)}"
        )

    pr.title = pr_details["title"]
    pr.author = pr_details["author"]
    pr.base_branch = pr_details["base_branch"]
    pr.head_branch = pr_details["head_branch"]
    pr.status = pr_details["status"]
    pr.files_changed = pr_details["files_changed"]
    pr.additions = pr_details["additions"]
    pr.deletions = pr_details["deletions"]
    pr.commits = pr_details["commits"]
    pr.pr_files_json = json.dumps(pr_files)
    pr.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(pr)
    return pr


@pr_router.post("/pull-requests/{id}/review-again", response_model=PullRequestResponse)
async def re_review_pull_request(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Triggers a new Analysis review run on cached PR files while keeping history intact.
    """
    pr = db.query(PullRequest).filter(PullRequest.id == id).first()
    if not pr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pull Request not found")

    project = ProjectRepository.get_project(db, pr.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pull Request not found")

    if not pr.pr_files_json:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files cached. Please trigger standard review or refresh first."
        )

    pr_files = json.loads(pr.pr_files_json)

    # Start incremental review, creating a new Analysis
    analysis = await IncrementalReviewService.start_pr_review(
        db=db,
        project_id=pr.project_id,
        pr_id=pr.id,
        changed_files=pr_files
    )

    pr.latest_analysis_id = analysis.id
    db.commit()
    db.refresh(pr)

    return pr
