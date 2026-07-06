import json
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.projects.models.project_models import ChatMessage

class ConversationService:
    @staticmethod
    def get_history(db: Session, project_id: int) -> List[ChatMessage]:
        """
        Retrieves full project chat history sorted chronologically.
        """
        return db.query(ChatMessage).filter(
            ChatMessage.project_id == project_id
        ).order_by(ChatMessage.created_at.asc()).all()

    @staticmethod
    def get_context_history(db: Session, project_id: int, limit: int = 8) -> List[ChatMessage]:
        """
        Retrieves the last N messages chronologically to populate conversation context for LLM.
        """
        # Fetch last N records ordered desc, then reverse to order chronologically
        recent_messages = db.query(ChatMessage).filter(
            ChatMessage.project_id == project_id
        ).order_by(ChatMessage.created_at.desc()).limit(limit).all()
        
        return list(reversed(recent_messages))

    @staticmethod
    def add_message(
        db: Session,
        project_id: int,
        role: str,
        content: str,
        referenced_files: Optional[List[str]] = None,
        referenced_classes: Optional[List[str]] = None,
        referenced_functions: Optional[List[str]] = None,
        referenced_reports: Optional[List[int]] = None,
        referenced_version: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> ChatMessage:
        """
        Saves a user or assistant message to the database with citations.
        """
        msg = ChatMessage(
            project_id=project_id,
            role=role,
            content=content,
            referenced_files=json.dumps(referenced_files or []),
            referenced_classes=json.dumps(referenced_classes or []),
            referenced_functions=json.dumps(referenced_functions or []),
            referenced_reports=json.dumps(referenced_reports or []),
            referenced_version=referenced_version,
            user_id=user_id
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def clear_history(db: Session, project_id: int) -> None:
        """
        Deletes all chat messages for a project.
        """
        db.query(ChatMessage).filter(ChatMessage.project_id == project_id).delete()
        db.commit()
