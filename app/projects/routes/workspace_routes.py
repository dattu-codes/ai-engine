from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List

from app.auth.database.connection import get_db
from app.auth.dependencies import get_current_user
from app.auth.models.auth_models import User
from app.projects.services.workspace_service import WorkspaceService
from app.projects.services.permission_service import PermissionService

workspace_router = APIRouter(prefix="/workspaces", tags=["Workspaces"])

# Pydantic Schemas
class WorkspaceCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None

class WorkspaceUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class MemberInviteRequest(BaseModel):
    username: str
    role: str

class MemberRoleUpdateRequest(BaseModel):
    role: str


# Endpoints
@workspace_router.post("", status_code=201)
def create_workspace(
    req: WorkspaceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ws = WorkspaceService.create_workspace(db, current_user.id, req.name, req.description)
    return {
        "id": ws.id,
        "name": ws.name,
        "description": ws.description,
        "created_at": ws.created_at.isoformat() if ws.created_at else None,
        "updated_at": ws.updated_at.isoformat() if ws.updated_at else None
    }

@workspace_router.get("")
def get_workspaces(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    workspaces = WorkspaceService.get_user_workspaces(db, current_user.id)
    return [
        {
            "id": ws.id,
            "name": ws.name,
            "description": ws.description,
            "created_at": ws.created_at.isoformat() if ws.created_at else None,
            "updated_at": ws.updated_at.isoformat() if ws.updated_at else None
        }
        for ws in workspaces
    ]

@workspace_router.get("/{id}")
def get_workspace_by_id(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not PermissionService.can_view_project(db, current_user.id, id):
        role = PermissionService.get_user_role(db, current_user.id, id)
        if not role:
            raise HTTPException(status_code=403, detail="Not a member of this workspace.")
    
    workspace = WorkspaceService.get_workspace_by_id(db, id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return {
        "id": workspace.id,
        "name": workspace.name,
        "description": workspace.description,
        "created_at": workspace.created_at.isoformat() if workspace.created_at else None,
        "updated_at": workspace.updated_at.isoformat() if workspace.updated_at else None
    }

@workspace_router.patch("/{id}")
def update_workspace(
    id: int,
    req: WorkspaceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not PermissionService.can_manage_workspace(db, current_user.id, id):
        raise HTTPException(status_code=403, detail="Only Owners or Admins can edit the workspace properties.")
    ws = WorkspaceService.update_workspace(db, current_user.id, id, req.name, req.description)
    return {
        "id": ws.id,
        "name": ws.name,
        "description": ws.description,
        "created_at": ws.created_at.isoformat() if ws.created_at else None,
        "updated_at": ws.updated_at.isoformat() if ws.updated_at else None
    }

@workspace_router.delete("/{id}")
def delete_workspace(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    role = PermissionService.get_user_role(db, current_user.id, id)
    if role != "Owner":
        raise HTTPException(status_code=403, detail="Only the workspace Owner can delete the workspace.")
    WorkspaceService.delete_workspace(db, current_user.id, id)
    return {"message": "Workspace deleted successfully."}

@workspace_router.post("/{id}/members", status_code=201)
def invite_member(
    id: int,
    req: MemberInviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not PermissionService.can_manage_members(db, current_user.id, id):
        raise HTTPException(status_code=403, detail="Only Owners or Admins can invite workspace members.")
    member = WorkspaceService.invite_member(db, current_user.id, id, req.username, req.role)
    return {
        "id": member.id,
        "workspace_id": member.workspace_id,
        "user_id": member.user_id,
        "role": member.role,
        "invited_by": member.invited_by,
        "joined_at": member.joined_at.isoformat() if member.joined_at else None
    }

@workspace_router.get("/{id}/members")
def get_workspace_members(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    role = PermissionService.get_user_role(db, current_user.id, id)
    if not role:
        raise HTTPException(status_code=403, detail="Access denied.")
    return WorkspaceService.get_workspace_members(db, id)

@workspace_router.patch("/{id}/members/{member_id}")
def change_member_role(
    id: int,
    member_id: int,
    req: MemberRoleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not PermissionService.can_manage_members(db, current_user.id, id):
        raise HTTPException(status_code=403, detail="Only Owners or Admins can change member roles.")
    member = WorkspaceService.change_member_role(db, current_user.id, id, member_id, req.role)
    return {
        "id": member.id,
        "workspace_id": member.workspace_id,
        "user_id": member.user_id,
        "role": member.role,
        "invited_by": member.invited_by,
        "joined_at": member.joined_at.isoformat() if member.joined_at else None
    }

@workspace_router.delete("/{id}/members/{member_id}")
def remove_member(
    id: int,
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not PermissionService.can_manage_members(db, current_user.id, id):
        # Allow a user to remove themselves (leave the workspace)
        member = db.query(WorkspaceMember).filter(WorkspaceMember.id == member_id).first()
        if not member or member.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Only Owners or Admins can remove other workspace members.")
            
    WorkspaceService.remove_member(db, current_user.id, id, member_id)
    return {"message": "Member removed successfully."}

@workspace_router.get("/{id}/statistics")
def get_workspace_statistics(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    role = PermissionService.get_user_role(db, current_user.id, id)
    if not role:
        raise HTTPException(status_code=403, detail="Access denied.")
    return WorkspaceService.get_workspace_statistics(db, id)
