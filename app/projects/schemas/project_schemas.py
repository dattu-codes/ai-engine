from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Project name")


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

    class Config:
        from_attributes = True
