from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.projects.models.project_models import Workspace, WorkspaceMember, Project, ReviewFinding, Analysis
from app.auth.models.auth_models import User
from app.projects.services.activity_service import ActivityService

class WorkspaceService:
    @staticmethod
    def create_workspace(db: Session, user_id: int, name: str, description: Optional[str] = None) -> Workspace:
        workspace = Workspace(name=name, description=description)
        db.add(workspace)
        db.flush()  # populate ID

        # Make creator Owner
        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user_id,
            role="Owner",
            invited_by=user_id
        )
        db.add(member)
        db.commit()

        # Log Activity
        ActivityService.log_activity(
            db=db,
            workspace_id=workspace.id,
            project_id=None,
            user_id=user_id,
            activity_type="Workspace Created",
            entity_type="workspace",
            entity_id=workspace.id,
            description=f"Workspace '{name}' was created.",
            metadata_json=None
        )

        return workspace

    @staticmethod
    def get_user_workspaces(db: Session, user_id: int) -> List[Workspace]:
        # Return workspaces where the user is a member
        memberships = db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user_id).all()
        workspace_ids = [m.workspace_id for m in memberships]
        return db.query(Workspace).filter(Workspace.id.in_(workspace_ids)).all()

    @staticmethod
    def get_workspace_by_id(db: Session, workspace_id: int) -> Optional[Workspace]:
        return db.query(Workspace).filter(Workspace.id == workspace_id).first()

    @staticmethod
    def update_workspace(db: Session, user_id: int, workspace_id: int, name: Optional[str] = None, description: Optional[str] = None) -> Workspace:
        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found.")

        if name is not None:
            workspace.name = name
        if description is not None:
            workspace.description = description
        
        workspace.updated_at = datetime.utcnow()
        db.commit()

        # Log Activity
        ActivityService.log_activity(
            db=db,
            workspace_id=workspace_id,
            project_id=None,
            user_id=user_id,
            activity_type="Workspace Updated",
            entity_type="workspace",
            entity_id=workspace_id,
            description=f"Workspace properties were updated.",
            metadata_json=None
        )
        return workspace

    @staticmethod
    def delete_workspace(db: Session, user_id: int, workspace_id: int):
        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found.")

        # Log Activity first before delete cascade
        ActivityService.log_activity(
            db=db,
            workspace_id=workspace_id,
            project_id=None,
            user_id=user_id,
            activity_type="Workspace Deleted",
            entity_type="workspace",
            entity_id=workspace_id,
            description=f"Workspace '{workspace.name}' was deleted.",
            metadata_json=None
        )

        db.delete(workspace)
        db.commit()

    @staticmethod
    def invite_member(db: Session, inviter_id: int, workspace_id: int, username: str, role: str) -> WorkspaceMember:
        if role not in ["Owner", "Admin", "Developer", "Viewer"]:
            raise HTTPException(status_code=400, detail="Invalid member role.")

        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"User '{username}' not found.")

        # Check existing membership
        existing = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="User is already a member of this workspace.")

        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user.id,
            role=role,
            invited_by=inviter_id
        )
        db.add(member)
        db.commit()

        # Log Activity
        ActivityService.log_activity(
            db=db,
            workspace_id=workspace_id,
            project_id=None,
            user_id=inviter_id,
            activity_type="Member Invited",
            entity_type="workspace_member",
            entity_id=member.id,
            description=f"User '{username}' was added to the workspace as {role}.",
            metadata_json={"invited_user": username, "role": role}
        )
        return member

    @staticmethod
    def get_workspace_members(db: Session, workspace_id: int) -> List[Dict[str, Any]]:
        members = db.query(WorkspaceMember).filter(WorkspaceMember.workspace_id == workspace_id).all()
        result = []
        for m in members:
            user = db.query(User).filter(User.id == m.user_id).first()
            inviter = db.query(User).filter(User.id == m.invited_by).first() if m.invited_by else None
            
            # Count assigned findings in projects under this workspace
            workspace_project_ids = [p.id for p in db.query(Project).filter(Project.workspace_id == workspace_id).all()]
            assigned_count = 0
            if workspace_project_ids and user:
                assigned_count = db.query(ReviewFinding).filter(
                    ReviewFinding.project_id.in_(workspace_project_ids),
                    ReviewFinding.assigned_to == user.username
                ).count()

            result.append({
                "id": m.id,
                "user_id": m.user_id,
                "username": user.username if user else "Unknown User",
                "role": m.role,
                "invited_by_username": inviter.username if inviter else "System",
                "joined_at": m.joined_at.isoformat(),
                "assigned_findings": assigned_count
            })
        return result

    @staticmethod
    def remove_member(db: Session, operator_id: int, workspace_id: int, member_id: int):
        member = db.query(WorkspaceMember).filter(
            WorkspaceMember.id == member_id,
            WorkspaceMember.workspace_id == workspace_id
        ).first()
        if not member:
            raise HTTPException(status_code=404, detail="Workspace member not found.")

        # Prevent removing last owner
        if member.role == "Owner":
            owners_count = db.query(WorkspaceMember).filter(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == "Owner"
            ).count()
            if owners_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot remove the only Owner in the workspace.")

        user = db.query(User).filter(User.id == member.user_id).first()
        username = user.username if user else "Unknown User"

        db.delete(member)
        db.commit()

        # Log Activity
        ActivityService.log_activity(
            db=db,
            workspace_id=workspace_id,
            project_id=None,
            user_id=operator_id,
            activity_type="Member Removed",
            entity_type="workspace_member",
            entity_id=member_id,
            description=f"User '{username}' was removed from the workspace.",
            metadata_json={"removed_user": username}
        )

    @staticmethod
    def change_member_role(db: Session, operator_id: int, workspace_id: int, member_id: int, new_role: str) -> WorkspaceMember:
        if new_role not in ["Owner", "Admin", "Developer", "Viewer"]:
            raise HTTPException(status_code=400, detail="Invalid member role.")

        member = db.query(WorkspaceMember).filter(
            WorkspaceMember.id == member_id,
            WorkspaceMember.workspace_id == workspace_id
        ).first()
        if not member:
            raise HTTPException(status_code=404, detail="Workspace member not found.")

        # Prevent demoting last owner
        if member.role == "Owner" and new_role != "Owner":
            owners_count = db.query(WorkspaceMember).filter(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == "Owner"
            ).count()
            if owners_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot demote the only Owner in the workspace.")

        user = db.query(User).filter(User.id == member.user_id).first()
        username = user.username if user else "Unknown User"

        old_role = member.role
        member.role = new_role
        db.commit()

        # Log Activity
        ActivityService.log_activity(
            db=db,
            workspace_id=workspace_id,
            project_id=None,
            user_id=operator_id,
            activity_type="Member Role Changed",
            entity_type="workspace_member",
            entity_id=member_id,
            description=f"User '{username}' role changed from {old_role} to {new_role}.",
            metadata_json={"updated_user": username, "old_role": old_role, "new_role": new_role}
        )
        return member

    @staticmethod
    def get_workspace_statistics(db: Session, workspace_id: int) -> Dict[str, Any]:
        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found.")

        projects = db.query(Project).filter(Project.workspace_id == workspace_id).all()
        project_ids = [p.id for p in projects]

        total_members = db.query(WorkspaceMember).filter(WorkspaceMember.workspace_id == workspace_id).count()
        total_projects = len(projects)

        analyses_count = 0
        findings_count = {"Open": 0, "In Progress": 0, "Resolved": 0, "Ignored": 0}
        findings_severity = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}

        if project_ids:
            analyses_count = db.query(Analysis).filter(Analysis.project_id.in_(project_ids)).count()
            findings = db.query(ReviewFinding).filter(ReviewFinding.project_id.in_(project_ids)).all()
            for f in findings:
                if f.status in findings_count:
                    findings_count[f.status] += 1
                if f.severity in findings_severity:
                    findings_severity[f.severity] += 1

        return {
            "workspace_id": workspace_id,
            "workspace_name": workspace.name,
            "total_members": total_members,
            "total_projects": total_projects,
            "total_analyses": analyses_count,
            "findings_by_status": findings_count,
            "findings_by_severity": findings_severity
        }
