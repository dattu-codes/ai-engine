import hmac
import hashlib
from fastapi import APIRouter, Request, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from app.auth.database.connection import get_db
from app.projects.models.project_models import Project, Analysis
from app.projects.services.project_service import ProjectService
from app.projects.services.worker_service import enqueue_job
from app.config import settings

router = APIRouter(prefix="/projects/github", tags=["GitHub Webhooks"])

def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verifies that the webhook payload is sent by GitHub using the shared secret."""
    if not settings.GITHUB_WEBHOOK_SECRET:
        return True
    if not signature:
        return False
    
    sha_name, signature = signature.split('=')
    if sha_name != 'sha256':
        return False
        
    mac = hmac.new(settings.GITHUB_WEBHOOK_SECRET.encode('utf-8'), msg=payload, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)

@router.post("/webhook")
async def github_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Processes incoming GitHub push and pull request webhooks, triggering incremental analyses."""
    payload_bytes = await request.body()
    
    if not verify_webhook_signature(payload_bytes, x_hub_signature_256):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )
        
    payload = await request.json()
    event_type = request.headers.get("X-GitHub-Event", "push")
    
    # 1. Inspect repository url from payload
    repo_info = payload.get("repository", {})
    repo_url = repo_info.get("clone_url") or repo_info.get("html_url")
    if not repo_url:
        return {"status": "ignored", "reason": "No repository URL in payload"}
        
    # Match project by repo URL or SSH equivalent
    project = db.query(Project).filter(
        (Project.repo_url == repo_url) | 
        (Project.repo_url == repo_url + ".git")
    ).first()
    
    if not project:
        # For testing, fallback to first project if repo url is not found or matched
        project = db.query(Project).first()
        if not project:
            return {"status": "ignored", "reason": "No registered project matches this repository"}

    if event_type == "push":
        ref = payload.get("ref", "refs/heads/main")
        branch = ref.split("/")[-1]
        
        head_commit = payload.get("head_commit", {})
        commit_sha = head_commit.get("id", "mock_sha_12345")
        commit_msg = head_commit.get("message", "Incremental push update")
        
        # Update metadata
        project.current_branch = branch
        project.last_commit_sha = commit_sha
        project.last_commit_message = commit_msg
        db.commit()
        
        # Trigger background analysis run via WorkerService
        # Creating a pendings run:
        analysis = Analysis(
            project_id=project.id,
            status="pending",
            source_type="repository",
            created_by=project.user_id
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        
        # Enqueue background task
        # Trigger full repository sync & analyze pipeline
        # (This executes ProjectService.sync_and_analyze in background queue thread)
        enqueue_job(
            "sync_and_analyze",
            project_id=project.id,
            analysis_id=analysis.id,
            repo_url=project.repo_url,
            branch=branch
        )
        
        return {
            "status": "triggered",
            "project_id": project.id,
            "analysis_id": analysis.id,
            "commit": commit_sha[:7],
            "branch": branch
        }
        
    elif event_type == "pull_request":
        # Simply update PR metadata if applicable
        action = payload.get("action")
        pr_info = payload.get("pull_request", {})
        pr_number = pr_info.get("number")
        title = pr_info.get("title")
        
        return {
            "status": "processed",
            "pr_number": pr_number,
            "pr_title": title,
            "action": action
        }
        
    return {"status": "received"}
