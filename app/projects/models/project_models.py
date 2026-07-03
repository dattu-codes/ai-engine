from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Boolean
from sqlalchemy.orm import relationship
from app.auth.database.connection import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    analyses = relationship("Analysis", back_populates="project", cascade="all, delete-orphan")
    user = relationship("User")

    # GitHub Repository Metadata
    repo_url = Column(String(512), nullable=True)
    repo_name = Column(String(255), nullable=True)
    repo_owner = Column(String(255), nullable=True)
    default_branch = Column(String(100), nullable=True)
    current_branch = Column(String(100), nullable=True)
    last_commit_sha = Column(String(100), nullable=True)
    last_commit_message = Column(Text, nullable=True)
    last_sync_time = Column(DateTime, nullable=True)

    # Code Intelligence Metadata Cache
    project_type = Column(String(100), nullable=True)
    framework = Column(String(100), nullable=True)
    architecture = Column(String(100), nullable=True)
    languages_distribution = Column(Text, nullable=True)  # JSON-serialized dict
    dependencies_json = Column(Text, nullable=True)  # JSON-serialized list
    entry_point = Column(String(255), nullable=True)
    file_priorities = Column(Text, nullable=True)  # JSON-serialized dict filename -> priority
    total_lines = Column(Integer, default=0, nullable=True)
    has_intelligence = Column(Boolean, default=False, nullable=False)


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), default="pending", nullable=False)  # pending, completed, failed
    source_type = Column(String(50), nullable=False)  # paste, zip, repository
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Tracking fields for analysis run execution metrics
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration = Column(Float, nullable=True)  # duration in seconds
    model_used = Column(String(100), nullable=True)

    # Intelligent review pipeline fields (v1.5)
    modules_reviewed = Column(Text, nullable=True)  # JSON-serialized list of module names
    files_reviewed = Column(Integer, default=0, nullable=True)
    total_files = Column(Integer, default=0, nullable=True)
    skipped_files = Column(Integer, default=0, nullable=True)
    coverage_percentage = Column(Float, default=0.0, nullable=True)
    skipped_reasons_json = Column(Text, nullable=True)  # JSON-serialized dict (filename -> reason)
    ai_calls = Column(Integer, default=0, nullable=True)
    overall_confidence = Column(Float, default=0.0, nullable=True)
    pipeline_stages = Column(Text, nullable=True)  # JSON-serialized list of stages

    # Relationships
    project = relationship("Project", back_populates="analyses")
    files = relationship("AnalysisFile", back_populates="analysis", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="analysis", cascade="all, delete-orphan")


class AnalysisFile(Base):
    __tablename__ = "analysis_files"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(512), nullable=False)
    extension = Column(String(50), nullable=False)
    size = Column(Integer, nullable=False)  # size in bytes
    language = Column(String(100), nullable=False)  # Python, Java, JavaScript, TypeScript
    hash = Column(String(64), nullable=False)  # SHA-256 hash of content
    content = Column(Text, nullable=True)  # File source code contents

    # Relationships
    analysis = relationship("Analysis", back_populates="files")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    score = Column(Integer, nullable=True)
    summary = Column(Text, nullable=True)
    details_json = Column(Text, nullable=True)  # Scanned issues and suggestions JSON
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    analysis = relationship("Analysis", back_populates="reports")
