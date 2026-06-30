from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    repo_url: Optional[str] = Field(None, description="Optional public GitHub Repository URL")


class ProjectRename(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="New project name")


class ProjectResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AnalysisResponse(BaseModel):
    id: int
    project_id: int
    status: str
    source_type: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None
    model_used: Optional[str] = None

    class Config:
        from_attributes = True


class FileMetadataResponse(BaseModel):
    id: int
    filename: str
    extension: str
    size: int
    language: str
    hash: str

    class Config:
        from_attributes = True


class ReportResponse(BaseModel):
    id: int
    analysis_id: int
    score: Optional[int] = None
    summary: Optional[str] = None
    details_json: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PastedCodeRequest(BaseModel):
    filename: str = Field("main.py", description="Target filename")
    content: str = Field(..., description="Pasted source code content")


class ProjectDetailsResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    total_files: int
    last_analysis: Optional[AnalysisResponse] = None
    languages: List[str] = []
    
    # GitHub Repository Metadata
    repo_url: Optional[str] = None
    repo_name: Optional[str] = None
    repo_owner: Optional[str] = None
    default_branch: Optional[str] = None
    current_branch: Optional[str] = None
    last_commit_sha: Optional[str] = None
    last_commit_message: Optional[str] = None
    last_sync_time: Optional[datetime] = None

    class Config:
        from_attributes = True
