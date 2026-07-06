from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import Optional

from app.projects.models.project_models import WorkspaceMember, Project

class PermissionService:
    @staticmethod
    def get_user_role(db: Session, user_id: int, workspace_id: int) -> Optional[str]:
        member = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id
        ).first()
        return member.role if member else None

    @staticmethod
    def get_user_role_by_project(db: Session, user_id: int, project_id: int) -> Optional[str]:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return None
        if not project.workspace_id:
            # Backwards compatibility: creator gets Owner permissions
            return "Owner" if project.user_id == user_id else None
        return PermissionService.get_user_role(db, user_id, project.workspace_id)

    @staticmethod
    def can_view_project(db: Session, user_id: int, project_id: int) -> bool:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return False
        if not project.workspace_id:
            return project.user_id == user_id
        role = PermissionService.get_user_role(db, user_id, project.workspace_id)
        return role in ["Owner", "Admin", "Developer", "Viewer"]

    @staticmethod
    def can_run_analysis(db: Session, user_id: int, project_id: int) -> bool:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return False
        if not project.workspace_id:
            return project.user_id == user_id
        role = PermissionService.get_user_role(db, user_id, project.workspace_id)
        return role in ["Owner", "Admin", "Developer"]

    @staticmethod
    def can_manage_workspace(db: Session, user_id: int, workspace_id: int) -> bool:
        role = PermissionService.get_user_role(db, user_id, workspace_id)
        return role in ["Owner", "Admin"]

    @staticmethod
    def can_manage_members(db: Session, user_id: int, workspace_id: int) -> bool:
        role = PermissionService.get_user_role(db, user_id, workspace_id)
        return role in ["Owner", "Admin"]

    @staticmethod
    def can_assign_findings(db: Session, user_id: int, project_id: int) -> bool:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return False
        if not project.workspace_id:
            return project.user_id == user_id
        role = PermissionService.get_user_role(db, user_id, project.workspace_id)
        return role in ["Owner", "Admin", "Developer"]

    @staticmethod
    def can_apply_fix(db: Session, user_id: int, project_id: int) -> bool:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return False
        if not project.workspace_id:
            return project.user_id == user_id
        role = PermissionService.get_user_role(db, user_id, project.workspace_id)
        return role in ["Owner", "Admin", "Developer"]

    @staticmethod
    def can_restore_version(db: Session, user_id: int, project_id: int) -> bool:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return False
        if not project.workspace_id:
            return project.user_id == user_id
        role = PermissionService.get_user_role(db, user_id, project.workspace_id)
        return role in ["Owner", "Admin", "Developer"]

    @staticmethod
    def can_review_pull_request(db: Session, user_id: int, project_id: int) -> bool:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return False
        if not project.workspace_id:
            return project.user_id == user_id
        role = PermissionService.get_user_role(db, user_id, project.workspace_id)
        return role in ["Owner", "Admin", "Developer"]

    @staticmethod
    def can_access_chat(db: Session, user_id: int, project_id: int) -> bool:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return False
        if not project.workspace_id:
            return project.user_id == user_id
        role = PermissionService.get_user_role(db, user_id, project.workspace_id)
        return role in ["Owner", "Admin", "Developer", "Viewer"]

    @staticmethod
    def can_use_chat(db: Session, user_id: int, project_id: int) -> bool:
        return PermissionService.can_access_chat(db, user_id, project_id)
