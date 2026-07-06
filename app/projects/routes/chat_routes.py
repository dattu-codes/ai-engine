import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from app.auth.database.connection import get_db
from app.auth.dependencies import get_current_user
from app.auth.models.auth_models import User
from app.projects.repositories.project_repository import ProjectRepository
from app.projects.schemas.project_schemas import ChatRequest, ChatMessageResponse
from app.projects.services.conversation_service import ConversationService
from app.projects.services.project_chat_service import ProjectChatService
from app.projects.services.permission_service import PermissionService

chat_router = APIRouter(prefix="/projects/{project_id}/chat", tags=["Project Chat"])


@chat_router.post("")
async def run_chat(
    project_id: int,
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initiates a chat session query and streams the response back via Server-Sent Events.
    """
    project = ProjectRepository.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied"
        )

    if not PermissionService.can_use_chat(db, current_user.id, project_id):
        raise HTTPException(status_code=403, detail="Viewer role cannot send chat messages.")

    # Return the stream content using project chat service
    generator = ProjectChatService.chat_stream(
        db=db,
        project_id=project_id,
        user_query=request.message,
        api_key=request.api_key,
        user_id=current_user.id
    )

    return StreamingResponse(generator, media_type="text/event-stream")


@chat_router.get("/history", response_model=List[ChatMessageResponse])
def get_chat_history(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves the persisted conversation history for the project.
    """
    project = ProjectRepository.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied"
        )

    messages = ConversationService.get_history(db, project_id)
    
    # Manually map string JSON arrays stored in SQLite columns to Python lists
    result = []
    for msg in messages:
        try:
            ref_files = json.loads(msg.referenced_files) if msg.referenced_files else []
        except Exception:
            ref_files = []

        try:
            ref_classes = json.loads(msg.referenced_classes) if msg.referenced_classes else []
        except Exception:
            ref_classes = []

        try:
            ref_functions = json.loads(msg.referenced_functions) if msg.referenced_functions else []
        except Exception:
            ref_functions = []

        try:
            ref_reports = json.loads(msg.referenced_reports) if msg.referenced_reports else []
        except Exception:
            ref_reports = []

        result.append(ChatMessageResponse(
            id=msg.id,
            project_id=msg.project_id,
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at,
            referenced_files=ref_files,
            referenced_classes=ref_classes,
            referenced_functions=ref_functions,
            referenced_reports=ref_reports,
            referenced_version=msg.referenced_version
        ))

    return result


@chat_router.delete("/history")
def clear_chat_history(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Clears all chat history for the project.
    """
    project = ProjectRepository.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied"
        )

    ConversationService.clear_history(db, project_id)
    return {"message": "Chat history cleared successfully"}
