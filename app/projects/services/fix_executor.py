import json
import hashlib
from datetime import datetime
from sqlalchemy.orm import Session
from app.projects.models.project_models import Project, ProjectVersion, ProjectVersionFile, FixExecution
from app.projects.services.code_intelligence import CodeIntelligenceEngine
from app.projects.services.semantic_graph_service import SemanticGraphService
from app.projects.services.activity_service import ActivityService

class FixExecutor:
    @staticmethod
    def apply_patch(db: Session, fix_exec: FixExecution, replacement_code: str) -> ProjectVersion:
        """
        Applies a validated patch to the codebase, increments the version snapshot,
        and regenerates semantic graph + code intelligence metadata.
        """
        project = db.query(Project).filter(Project.id == fix_exec.project_id).first()
        if not project:
            raise ValueError("Project not found.")

        # Get current version
        current_version = db.query(ProjectVersion).filter(
            ProjectVersion.project_id == fix_exec.project_id
        ).order_by(ProjectVersion.version_number.desc()).first()

        if not current_version:
            raise ValueError("No baseline version exists for this project.")

        finding = fix_exec.finding
        target_file = finding.file_path

        # Load files for the current version
        curr_files = db.query(ProjectVersionFile).filter(
            ProjectVersionFile.version_id == current_version.id
        ).all()

        target_vf = next((f for f in curr_files if f.filename == target_file), None)
        if not target_vf:
            raise ValueError(f"File '{target_file}' not found in current version.")

        # Create new version record using VersionService
        from app.projects.services.version_service import VersionService
        new_version = VersionService.create_fix_version(
            db=db,
            project_id=fix_exec.project_id,
            parent_version_id=current_version.id,
            patch_summary=f"Applied AI Fix for #{finding.id} ({finding.category}) in '{target_file}'.",
            verification_score=0,
            files_changed=[target_file],
            ai_model=fix_exec.ai_model or "ai-assistant",
            execution_metadata={"finding_id": finding.id},
            user_id=finding.assigned_by or project.user_id
        )
        new_version_num = new_version.version_number
        meta = {}

        # Copy files over applying the replacement content to the target file
        new_vfs = []
        for f in curr_files:
            if f.filename == target_file:
                content_bytes = replacement_code.encode("utf-8")
                size = len(content_bytes)
                file_hash = hashlib.sha256(content_bytes).hexdigest()
                content = replacement_code
            else:
                size = f.size
                file_hash = f.hash
                content = f.content

            meta[f.filename] = file_hash
            new_vf = ProjectVersionFile(
                version_id=new_version.id,
                filename=f.filename,
                extension=f.extension,
                size=size,
                language=f.language,
                hash=file_hash,
                content=content
            )
            db.add(new_vf)
            new_vfs.append(new_vf)

        # Update snapshot metadata
        new_version.snapshot_metadata = json.dumps(meta)
        db.commit()

        # Update Code Intelligence cache
        try:
            intelligence = CodeIntelligenceEngine.analyze_project(new_vfs)
            project.project_type = intelligence["project_type"]
            project.framework = intelligence["framework"]
            project.architecture = intelligence["architecture"]
            project.languages_distribution = json.dumps(intelligence["languages_distribution"])
            project.dependencies_json = json.dumps(intelligence["dependencies"])
            project.entry_point = intelligence["entry_point"]
            project.file_priorities = json.dumps(intelligence["file_priorities"])
            project.total_lines = intelligence["total_lines"]
            db.commit()
        except Exception as ie:
            print(f"Error updating code intelligence on patch execution: {ie}")

        # Update Semantic Graph cache
        try:
            SemanticGraphService.refresh_after_patch(db, fix_exec.project_id, [target_file])
        except Exception as ge:
            print(f"Error refreshing semantic graph on patch execution: {ge}")

        # Log Version Created activity
        ActivityService.log_activity(
            db=db,
            workspace_id=project.workspace_id,
            project_id=project.id,
            user_id=finding.assigned_by or project.user_id,
            activity_type="Version Created",
            entity_type="version",
            entity_id=new_version.id,
            description=f"Version {new_version_num} created via AI Fix execution on finding #{finding.id}."
        )

        return new_version
