from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Boolean
from sqlalchemy.orm import relationship, relationship as orm_relationship
from app.auth.database.connection import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    analyses = relationship("Analysis", back_populates="project", cascade="all, delete-orphan")
    versions = relationship("ProjectVersion", back_populates="project", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="project", cascade="all, delete-orphan")
    pull_requests = relationship("PullRequest", back_populates="project", cascade="all, delete-orphan")
    findings = relationship("ReviewFinding", back_populates="project", cascade="all, delete-orphan")
    semantic_nodes = relationship("SemanticNode", back_populates="project", cascade="all, delete-orphan")
    semantic_edges = relationship("SemanticEdge", back_populates="project", cascade="all, delete-orphan")
    user = relationship("User")
    workspace = relationship("Workspace", back_populates="projects")

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
    
    # Semantic Code Graph Cache (v2.2)
    has_semantic_graph = Column(Boolean, default=False, nullable=False)
    graph_generated_at = Column(DateTime, nullable=True)
    graph_statistics_json = Column(Text, nullable=True)


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
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id", ondelete="SET NULL"), nullable=True)
    pull_request = relationship("PullRequest", foreign_keys=[pull_request_id], back_populates="analyses")
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    @property
    def score(self) -> Optional[int]:
        if self.reports:
            return self.reports[0].score
        return None


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


class ProjectVersion(Base):
    __tablename__ = "project_versions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    parent_version_id = Column(Integer, ForeignKey("project_versions.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    source_analysis_id = Column(Integer, ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True)
    applied_fixes = Column(Text, nullable=True)  # JSON-serialized list of issues/fixes
    summary = Column(Text, nullable=True)
    snapshot_metadata = Column(Text, nullable=True)  # JSON-serialized metadata

    # Relationships
    project = relationship("Project", back_populates="versions")
    parent = relationship("ProjectVersion", remote_side=[id])
    files = relationship("ProjectVersionFile", back_populates="version", cascade="all, delete-orphan")
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class ProjectVersionFile(Base):
    __tablename__ = "project_version_files"

    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("project_versions.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(512), nullable=False)
    extension = Column(String(50), nullable=False)
    size = Column(Integer, nullable=False)
    language = Column(String(100), nullable=False)
    hash = Column(String(64), nullable=False)
    content = Column(Text, nullable=True)

    # Relationships
    version = relationship("ProjectVersion", back_populates="files")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Citations metadata
    referenced_files = Column(Text, nullable=True)  # JSON list
    referenced_classes = Column(Text, nullable=True)  # JSON list
    referenced_functions = Column(Text, nullable=True)  # JSON list
    referenced_reports = Column(Text, nullable=True)  # JSON list
    referenced_version = Column(Integer, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="chat_messages")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    github_pr_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    author = Column(String(100), nullable=False)
    base_branch = Column(String(100), nullable=False)
    head_branch = Column(String(100), nullable=False)
    status = Column(String(50), default="open", nullable=False)  # open, closed, merged
    files_changed = Column(Integer, default=0, nullable=False)
    additions = Column(Integer, default=0, nullable=False)
    deletions = Column(Integer, default=0, nullable=False)
    commits = Column(Integer, default=0, nullable=False)
    latest_analysis_id = Column(Integer, ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True)
    pr_files_json = Column(Text, nullable=True)  # JSON cache of file list and patches
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="pull_requests")
    analyses = relationship("Analysis", foreign_keys=[Analysis.pull_request_id], back_populates="pull_request", cascade="all, delete-orphan")
    latest_analysis = relationship("Analysis", foreign_keys=[latest_analysis_id])
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class ReviewFinding(Base):
    __tablename__ = "review_findings"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    analysis_id = Column(Integer, ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True)
    resolved_in_version_id = Column(Integer, ForeignKey("project_versions.id", ondelete="SET NULL"), nullable=True)
    
    file_path = Column(String(512), nullable=False)
    line_number = Column(Integer, nullable=False)
    category = Column(String(100), nullable=False)
    severity = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=False)
    confidence = Column(Float, default=0.8, nullable=False)
    status = Column(String(50), default="Open", nullable=False)  # Open, In Progress, Resolved, Ignored
    assigned_to = Column(String(100), nullable=True)
    assigned_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_at = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    ignored_reason = Column(Text, nullable=True)
    
    # Semantic Code Graph Dependency Metrics (v2.2)
    impacted_modules = Column(Text, nullable=True)  # JSON-serialized list of modules
    dependency_chain = Column(Text, nullable=True)  # JSON-serialized list of dependency file paths
    downstream_risk = Column(String(100), nullable=True)  # High Risk, Medium Risk, Low Risk

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="findings")
    analysis = relationship("Analysis")
    resolved_in_version = relationship("ProjectVersion")
    comments = relationship("FindingComment", back_populates="finding", cascade="all, delete-orphan")


class SemanticNode(Base):
    __tablename__ = "semantic_nodes"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    node_type = Column(String(100), nullable=False)  # class, interface, method, function, api_route, db_model, file
    name = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    start_line = Column(Integer, nullable=True)
    end_line = Column(Integer, nullable=True)
    metadata_json = Column(Text, nullable=True)  # JSON metadata (signatures, docstrings, parameters)

    # Relationships
    project = orm_relationship("Project", back_populates="semantic_nodes")


class SemanticEdge(Base):
    __tablename__ = "semantic_edges"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    source_node_id = Column(Integer, ForeignKey("semantic_nodes.id", ondelete="CASCADE"), nullable=False)
    target_node_id = Column(Integer, ForeignKey("semantic_nodes.id", ondelete="CASCADE"), nullable=False)
    relationship = Column(String(100), nullable=False)  # IMPORTS, CALLS, EXTENDS, IMPLEMENTS, DEPENDS_ON, REFERENCES, USES, INHERITS

    # Relationships
    project = orm_relationship("Project", back_populates="semantic_edges")


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    projects = relationship("Project", back_populates="workspace", cascade="all, delete-orphan")
    members = relationship("WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan")
    activities = relationship("ActivityLog", back_populates="workspace", cascade="all, delete-orphan")


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False)  # Owner, Admin, Developer, Viewer
    invited_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="members")
    user = relationship("User", foreign_keys=[user_id])
    inviter = relationship("User", foreign_keys=[invited_by])


class FindingComment(Base):
    __tablename__ = "finding_comments"

    id = Column(Integer, primary_key=True, index=True)
    finding_id = Column(Integer, ForeignKey("review_findings.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    parent_comment_id = Column(Integer, ForeignKey("finding_comments.id", ondelete="CASCADE"), nullable=True)
    comment = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    finding = relationship("ReviewFinding", back_populates="comments")
    user = relationship("User")
    parent = relationship("FindingComment", back_populates="replies", remote_side=[id])
    replies = relationship("FindingComment", back_populates="parent", cascade="all, delete-orphan")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    activity_type = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(Integer, nullable=True)
    description = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="activities")
    project = relationship("Project")
    user = relationship("User")


class FixExecution(Base):
    __tablename__ = "fix_executions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    finding_id = Column(Integer, ForeignKey("review_findings.id", ondelete="CASCADE"), nullable=False)
    
    version_before_id = Column(Integer, ForeignKey("project_versions.id", ondelete="SET NULL"), nullable=True)
    version_after_id = Column(Integer, ForeignKey("project_versions.id", ondelete="SET NULL"), nullable=True)
    
    analysis_before_id = Column(Integer, ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True)
    analysis_after_id = Column(Integer, ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True)
    
    status = Column(String(50), default="Pending", nullable=False)
    ai_model = Column(String(100), nullable=True)
    fix_plan_json = Column(Text, nullable=True)
    patch_summary = Column(Text, nullable=True)
    files_modified = Column(Text, nullable=True)  # JSON-serialized list of strings
    lines_added = Column(Integer, default=0, nullable=False)
    lines_removed = Column(Integer, default=0, nullable=False)
    confidence_score = Column(Float, default=0.0, nullable=False)
    impact_score = Column(Float, default=0.0, nullable=False)
    estimated_risk = Column(String(50), nullable=True)
    verification_score = Column(Integer, nullable=True)
    execution_time = Column(Float, nullable=True)
    failure_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    project = relationship("Project")
    finding = relationship("ReviewFinding")
    version_before = relationship("ProjectVersion", foreign_keys=[version_before_id])
    version_after = relationship("ProjectVersion", foreign_keys=[version_after_id])
    analysis_before = relationship("Analysis", foreign_keys=[analysis_before_id])
    analysis_after = relationship("Analysis", foreign_keys=[analysis_after_id])


class TestExecution(Base):
    __tablename__ = "test_executions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    version_id = Column(Integer, ForeignKey("project_versions.id", ondelete="SET NULL"), nullable=True)
    fix_execution_id = Column(Integer, ForeignKey("fix_executions.id", ondelete="SET NULL"), nullable=True)
    
    language = Column(String(50), nullable=True)
    framework = Column(String(50), nullable=True)
    test_type = Column(String(50), nullable=True)  # Unit, Integration, Regression, Edge-case
    generated_tests_json = Column(Text, nullable=True)  # JSON-serialized list of tests
    execution_log = Column(Text, nullable=True)
    
    total_tests = Column(Integer, default=0, nullable=False)
    passed_tests = Column(Integer, default=0, nullable=False)
    failed_tests = Column(Integer, default=0, nullable=False)
    skipped_tests = Column(Integer, default=0, nullable=False)
    coverage_percentage = Column(Float, default=0.0, nullable=False)
    execution_time = Column(Float, nullable=True)
    status = Column(String(50), default="Pending", nullable=False)  # Pending, Generating, Running, Completed, Failed
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project")
    version = relationship("ProjectVersion")
    fix_execution = relationship("FixExecution")



