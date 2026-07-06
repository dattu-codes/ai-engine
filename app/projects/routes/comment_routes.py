from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List

from app.auth.database.connection import get_db
from app.auth.dependencies import get_current_user
from app.auth.models.auth_models import User
from app.projects.services.comment_service import CommentService

comment_router = APIRouter(tags=["Comments"])

# Pydantic Schemas
class CommentCreateRequest(BaseModel):
    comment: str
    parent_comment_id: Optional[int] = None

class CommentUpdateRequest(BaseModel):
    comment: str


# Endpoints
@comment_router.post("/findings/{id}/comments", status_code=201)
def add_comment(
    id: int,
    req: CommentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    comment = CommentService.add_comment(db, current_user.id, id, req.comment, req.parent_comment_id)
    return {
        "id": comment.id,
        "finding_id": comment.finding_id,
        "user_id": comment.user_id,
        "comment": comment.comment,
        "created_at": comment.created_at.isoformat() if comment.created_at else None
    }

@comment_router.get("/findings/{id}/comments")
def get_comments(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return CommentService.get_comments_for_finding(db, id)

@comment_router.patch("/comments/{id}")
def edit_comment(
    id: int,
    req: CommentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    comment = CommentService.edit_comment(db, current_user.id, id, req.comment)
    return {
        "id": comment.id,
        "finding_id": comment.finding_id,
        "user_id": comment.user_id,
        "comment": comment.comment,
        "created_at": comment.created_at.isoformat() if comment.created_at else None
    }

@comment_router.delete("/comments/{id}")
def delete_comment(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    CommentService.delete_comment(db, current_user.id, id)
    return {"message": "Comment deleted successfully."}
