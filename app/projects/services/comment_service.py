from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime
import re
from typing import Optional, List, Dict, Any

from app.projects.models.project_models import FindingComment, ReviewFinding, Project
from app.auth.models.auth_models import User
from app.projects.services.activity_service import ActivityService
from app.projects.services.permission_service import PermissionService

class CommentService:
    @staticmethod
    def add_comment(
        db: Session,
        user_id: int,
        finding_id: int,
        comment_text: str,
        parent_comment_id: Optional[int] = None
    ) -> FindingComment:
        finding = db.query(ReviewFinding).filter(ReviewFinding.id == finding_id).first()
        if not finding:
            raise HTTPException(status_code=404, detail="Review finding not found.")

        # Permissions check
        if not PermissionService.can_view_project(db, user_id, finding.project_id):
            raise HTTPException(status_code=403, detail="Not authorized to comment on this project's findings.")

        # Check parent comment if provided
        if parent_comment_id:
            parent = db.query(FindingComment).filter(
                FindingComment.id == parent_comment_id,
                FindingComment.finding_id == finding_id
            ).first()
            if not parent:
                raise HTTPException(status_code=404, detail="Parent comment not found in this finding discussion.")

        # Parse mentions e.g. @username
        mentions = re.findall(r"@(\w+)", comment_text)
        mentioned_users = []
        for m in mentions:
            user = db.query(User).filter(User.username == m).first()
            if user:
                mentioned_users.append(user.username)

        comment = FindingComment(
            finding_id=finding_id,
            user_id=user_id,
            parent_comment_id=parent_comment_id,
            comment=comment_text
        )
        db.add(comment)
        db.commit()

        # Log Activity
        project = db.query(Project).filter(Project.id == finding.project_id).first()
        user_obj = db.query(User).filter(User.id == user_id).first()
        username = user_obj.username if user_obj else "User"
        
        ActivityService.log_activity(
            db=db,
            workspace_id=project.workspace_id if project else None,
            project_id=finding.project_id,
            user_id=user_id,
            activity_type="Comment Added",
            entity_type="comment",
            entity_id=comment.id,
            description=f"{username} commented on finding #{finding_id}: '{comment_text[:60]}...'",
            metadata_json={"mentions": mentioned_users}
        )

        return comment

    @staticmethod
    def edit_comment(db: Session, user_id: int, comment_id: int, new_text: str) -> FindingComment:
        comment = db.query(FindingComment).filter(FindingComment.id == comment_id).first()
        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found.")

        if comment.user_id != user_id:
            raise HTTPException(status_code=403, detail="You can only edit your own comments.")

        comment.comment = new_text
        comment.updated_at = datetime.utcnow()
        db.commit()
        return comment

    @staticmethod
    def delete_comment(db: Session, operator_id: int, comment_id: int):
        comment = db.query(FindingComment).filter(FindingComment.id == comment_id).first()
        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found.")

        finding = db.query(ReviewFinding).filter(ReviewFinding.id == comment.finding_id).first()
        project = db.query(Project).filter(Project.id == finding.project_id).first() if finding else None

        # Operator must be Owner of comment OR Owner/Admin of workspace
        is_owner = comment.user_id == operator_id
        is_workspace_admin = False
        if project and project.workspace_id:
            role = PermissionService.get_user_role(db, operator_id, project.workspace_id)
            is_workspace_admin = role in ["Owner", "Admin"]

        if not (is_owner or is_workspace_admin):
            raise HTTPException(status_code=403, detail="Not authorized to delete this comment.")

        db.delete(comment)
        db.commit()

    @staticmethod
    def get_comments_for_finding(db: Session, finding_id: int) -> List[Dict[str, Any]]:
        comments = db.query(FindingComment).filter(FindingComment.finding_id == finding_id).order_by(FindingComment.created_at.asc()).all()
        result = []
        for c in comments:
            user = db.query(User).filter(User.id == c.user_id).first()
            result.append({
                "id": c.id,
                "finding_id": c.finding_id,
                "user_id": c.user_id,
                "username": user.username if user else "Unknown User",
                "parent_comment_id": c.parent_comment_id,
                "comment": c.comment,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat()
            })
        return result
