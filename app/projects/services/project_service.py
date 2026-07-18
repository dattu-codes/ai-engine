import json
import hashlib
from datetime import datetime
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status

from app.projects.models.project_models import Project, Analysis, AnalysisFile, Report, WorkspaceMember
from app.projects.repositories.project_repository import ProjectRepository
from app.projects.services.zip_processor import ZipProcessor
from app.projects.services.git_service import GitService
from app.projects.services.permission_service import PermissionService
from app.projects.services.activity_service import ActivityService

class ProjectService:
    @staticmethod
    def create_project(db: Session, user_id: int, name: str, repo_url: Optional[str] = None, workspace_id: Optional[int] = None) -> Project:
        if workspace_id:
            role = PermissionService.get_user_role(db, user_id, workspace_id)
            if role not in ["Owner", "Admin", "Developer"]:
                raise HTTPException(status_code=403, detail="Not authorized to create a project in this workspace.")

        if repo_url:
            # Validate, clone, and parse repository files
            try:
                metadata, files = GitService.clone_and_parse_repository(repo_url)
            except ValueError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

            if not files:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No supported files (.py, .java, .js, .ts) found in the repository."
                )

            # Create the project with GitHub repository metadata
            project = ProjectRepository.create_project(
                db=db,
                user_id=user_id,
                name=name,
                repo_url=repo_url,
                repo_name=metadata["repo_name"],
                repo_owner=metadata["repo_owner"],
                default_branch=metadata["default_branch"],
                current_branch=metadata["current_branch"],
                last_commit_sha=metadata["last_commit_sha"],
                last_commit_message=metadata["last_commit_message"],
                last_sync_time=datetime.utcnow(),
                workspace_id=workspace_id
            )

            # Ingest files under a starting "completed" ingestion Analysis run
            analysis = ProjectRepository.create_analysis(db, project.id, source_type="repository", status="completed")

            for f in files:
                ProjectRepository.create_analysis_file(
                    db,
                    analysis_id=analysis.id,
                    filename=f["filename"],
                    extension=f["extension"],
                    size=f["size"],
                    language=f["language"],
                    file_hash=f["hash"],
                    content=f["content"]
                )

            # Create a parsed metadata mock report
            summary = f"Successfully imported GitHub repository. Ingested {len(files)} files."
            report_details = {
                "repo_url": repo_url,
                "total_files": len(files),
                "files_by_language": {}
            }
            for f in files:
                lang = f["language"]
                report_details["files_by_language"][lang] = report_details["files_by_language"].get(lang, 0) + 1

            ProjectRepository.create_report(
                db,
                analysis_id=analysis.id,
                score=100,
                summary=summary,
                details_json=json.dumps(report_details)
            )

            # Generate initial baseline version snapshot and semantic graph (v3.1)
            from app.projects.services.version_service import VersionService
            VersionService.record_ingestion_version(
                db, 
                project.id, 
                analysis.id, 
                summary="Linked public Git repository baseline."
            )
            
            try:
                from app.projects.services.semantic_graph_service import SemanticGraphService
                SemanticGraphService.generate_graph(db, project.id)
            except Exception as ge:
                print(f"Error generating semantic graph on project creation: {ge}")

            # Log Repository Linked and Git Sync
            ActivityService.log_activity(
                db=db,
                workspace_id=workspace_id,
                project_id=project.id,
                user_id=user_id,
                activity_type="Project Created",
                entity_type="project",
                entity_id=project.id,
                description=f"Project '{name}' was created.",
                metadata_json=None
            )
            ActivityService.log_activity(
                db=db,
                workspace_id=workspace_id,
                project_id=project.id,
                user_id=user_id,
                activity_type="Repository Linked",
                entity_type="project",
                entity_id=project.id,
                description=f"GitHub Repository '{repo_url}' linked to project.",
                metadata_json=None
            )
            ActivityService.log_activity(
                db=db,
                workspace_id=workspace_id,
                project_id=project.id,
                user_id=user_id,
                activity_type="Git Sync",
                entity_type="project",
                entity_id=project.id,
                description=f"Synchronized {len(files)} files from GitHub repository.",
                metadata_json=None
            )

            return project
        else:
            project = ProjectRepository.create_project(db, user_id, name, workspace_id=workspace_id)
            ActivityService.log_activity(
                db=db,
                workspace_id=workspace_id,
                project_id=project.id,
                user_id=user_id,
                activity_type="Project Created",
                entity_type="project",
                entity_id=project.id,
                description=f"Project '{name}' was created.",
                metadata_json=None
            )
            return project

    @staticmethod
    def get_projects(db: Session, user_id: int) -> List[Project]:
        memberships = db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user_id).all()
        workspace_ids = [m.workspace_id for m in memberships]
        return db.query(Project).filter(
            (Project.user_id == user_id) | (Project.workspace_id.in_(workspace_ids))
        ).order_by(Project.created_at.desc()).all()

    @staticmethod
    def get_project_details(db: Session, project_id: int, user_id: int) -> Dict[str, Any]:
        project = ProjectRepository.get_project(db, project_id, user_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        latest_analysis = ProjectRepository.get_latest_analysis(db, project_id)

        # Retrieve codebase files to calculate correct metrics (v3.1)
        files = []
        from app.projects.models.project_models import ProjectVersion, ProjectVersionFile, Analysis
        current_version = db.query(ProjectVersion).filter(
            ProjectVersion.project_id == project_id
        ).order_by(ProjectVersion.version_number.desc()).first()

        if current_version:
            files = db.query(ProjectVersionFile).filter(ProjectVersionFile.version_id == current_version.id).all()

        if not files:
            all_analyses = ProjectRepository.get_project_analyses(db, project_id)
            for anal in all_analyses:
                if anal.status == "completed":
                    files = ProjectRepository.get_analysis_files(db, anal.id)
                    if files:
                        break

        total_files = len(files)
        languages = set(f.language for f in files)

        if latest_analysis:
                from app.projects.services.code_intelligence import CodeIntelligenceEngine
                intel = CodeIntelligenceEngine.analyze_project(files)
                ProjectRepository.update_project_intelligence(
                    db=db,
                    project=project,
                    project_type=intel["project_type"],
                    framework=intel["framework"],
                    architecture=intel["architecture"],
                    languages_distribution=json.dumps(intel["languages_distribution"]),
                    dependencies_json=json.dumps(intel["dependencies"]),
                    entry_point=intel["entry_point"],
                    file_priorities=json.dumps(intel["file_priorities"]),
                    total_lines=intel["total_lines"],
                    has_intelligence=True
                )

        return {
            "id": project.id,
            "name": project.name,
            "workspace_id": project.workspace_id,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
            "total_files": total_files,
            "last_analysis": latest_analysis,
            "languages": list(languages),
            "repo_url": project.repo_url,
            "repo_name": project.repo_name,
            "repo_owner": project.repo_owner,
            "default_branch": project.default_branch,
            "current_branch": project.current_branch,
            "last_commit_sha": project.last_commit_sha,
            "last_commit_message": project.last_commit_message,
            "last_sync_time": project.last_sync_time,
            "project_type": project.project_type,
            "framework": project.framework,
            "architecture": project.architecture,
            "languages_distribution": project.languages_distribution,
            "dependencies_json": project.dependencies_json,
            "entry_point": project.entry_point,
            "file_priorities": project.file_priorities,
            "total_lines": project.total_lines,
            "has_intelligence": project.has_intelligence,
        }

    @staticmethod
    def rename_project(db: Session, project_id: int, user_id: int, name: str) -> Project:
        project = ProjectRepository.get_project(db, project_id, user_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return ProjectRepository.update_project_name(db, project, name)

    @staticmethod
    def delete_project(db: Session, project_id: int, user_id: int) -> None:
        project = ProjectRepository.get_project(db, project_id, user_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        ProjectRepository.delete_project(db, project)

    @staticmethod
    def upload_project_zip(db: Session, project_id: int, user_id: int, zip_bytes: bytes) -> Analysis:
        project = ProjectRepository.get_project(db, project_id, user_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        try:
            files = ZipProcessor.process_zip(zip_bytes)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="No supported files (.py, .java, .js, .ts) found in the ZIP archive."
            )

        # Create new Analysis run
        analysis = ProjectRepository.create_analysis(db, project_id, source_type="zip", status="completed")
        project.has_intelligence = False
        db.commit()

        # Save files to database
        for f in files:
            ProjectRepository.create_analysis_file(
                db, 
                analysis_id=analysis.id,
                filename=f["filename"],
                extension=f["extension"],
                size=f["size"],
                language=f["language"],
                file_hash=f["hash"],
                content=f["content"]
            )

        # Create a parsed metadata mock report
        summary = f"Successfully parsed ZIP archive. Extracted {len(files)} files."
        report_details = {
            "total_files": len(files),
            "files_by_language": {}
        }
        for f in files:
            lang = f["language"]
            report_details["files_by_language"][lang] = report_details["files_by_language"].get(lang, 0) + 1

        ProjectRepository.create_report(
            db, 
            analysis_id=analysis.id, 
            score=100, 
            summary=summary, 
            details_json=json.dumps(report_details)
        )

        from app.projects.services.version_service import VersionService
        VersionService.record_ingestion_version(db, project_id, analysis.id, summary="Uploaded ZIP archive ingestion.")

        # Generate semantic graph cache (v2.2)
        try:
            from app.projects.services.semantic_graph_service import SemanticGraphService
            SemanticGraphService.generate_graph(db, project_id)
        except Exception as ge:
            print(f"Error generating semantic graph on upload: {ge}")

        return analysis

    @staticmethod
    def paste_project_code(db: Session, project_id: int, user_id: int, filename: str, content: str) -> Analysis:
        project = ProjectRepository.get_project(db, project_id, user_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        # Basic extension checking
        dot_idx = filename.rfind(".")
        if dot_idx == -1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename must have a supported extension.")
        
        extension = filename[dot_idx:].lower()
        if extension not in ZipProcessor.SUPPORTED_EXTENSIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file extension. Choose from .py, .java, .js, .ts")

        language = ZipProcessor.SUPPORTED_EXTENSIONS[extension]
        content_bytes = content.encode("utf-8")
        file_size = len(content_bytes)
        file_hash = hashlib.sha256(content_bytes).hexdigest()

        # Create new Analysis run
        analysis = ProjectRepository.create_analysis(db, project_id, source_type="paste", status="completed")
        project.has_intelligence = False
        db.commit()

        # Save single file to DB
        ProjectRepository.create_analysis_file(
            db, 
            analysis_id=analysis.id,
            filename=filename,
            extension=extension,
            size=file_size,
            language=language,
            file_hash=file_hash,
            content=content
        )

        # Create a parsed metadata mock report
        summary = f"Successfully parsed pasted code snippet for {filename}."
        report_details = {
            "pasted_filename": filename,
            "language": language,
            "size": file_size
        }

        ProjectRepository.create_report(
            db, 
            analysis_id=analysis.id, 
            score=100, 
            summary=summary, 
            details_json=json.dumps(report_details)
        )

        from app.projects.services.version_service import VersionService
        VersionService.record_ingestion_version(db, project_id, analysis.id, summary=f"Ingested pasted code file: '{filename}'.")

        # Generate semantic graph cache (v2.2)
        try:
            from app.projects.services.semantic_graph_service import SemanticGraphService
            SemanticGraphService.generate_graph(db, project_id)
        except Exception as ge:
            print(f"Error generating semantic graph on paste: {ge}")

        return analysis

    @staticmethod
    def save_project_repository(db: Session, project_id: int, user_id: int, repo_url: str) -> Analysis:
        project = ProjectRepository.get_project(db, project_id, user_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        try:
            metadata, files = GitService.clone_and_parse_repository(repo_url)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No supported files (.py, .java, .js, .ts) found in the repository."
            )

        # Update the project's repository metadata fields
        project.repo_url = repo_url
        project.repo_name = metadata["repo_name"]
        project.repo_owner = metadata["repo_owner"]
        project.default_branch = metadata["default_branch"]
        project.current_branch = metadata["current_branch"]
        project.last_commit_sha = metadata["last_commit_sha"]
        project.last_commit_message = metadata["last_commit_message"]
        project.last_sync_time = datetime.utcnow()
        project.has_intelligence = False
        db.commit()
        db.refresh(project)

        # Create new Analysis run
        analysis = ProjectRepository.create_analysis(db, project_id, source_type="repository", status="completed")

        for f in files:
            ProjectRepository.create_analysis_file(
                db,
                analysis_id=analysis.id,
                filename=f["filename"],
                extension=f["extension"],
                size=f["size"],
                language=f["language"],
                file_hash=f["hash"],
                content=f["content"]
            )

        summary = f"GitHub repository linked: {repo_url}. Remote source metadata synced successfully."
        report_details = {
            "repo_url": repo_url,
            "total_files": len(files),
            "files_by_language": {}
        }
        for f in files:
            lang = f["language"]
            report_details["files_by_language"][lang] = report_details["files_by_language"].get(lang, 0) + 1

        ProjectRepository.create_report(
            db, 
            analysis_id=analysis.id, 
            score=100, 
            summary=summary, 
            details_json=json.dumps(report_details)
        )

        from app.projects.services.version_service import VersionService
        VersionService.record_ingestion_version(db, project_id, analysis.id, summary="Linked public Git repository baseline.")

        # Generate semantic graph cache (v2.2)
        try:
            from app.projects.services.semantic_graph_service import SemanticGraphService
            SemanticGraphService.generate_graph(db, project_id)
        except Exception as ge:
            print(f"Error generating semantic graph on repository save: {ge}")

        return analysis

    @staticmethod
    def sync_project_repository(db: Session, project_id: int, user_id: int) -> Dict[str, Any]:
        project = ProjectRepository.get_project(db, project_id, user_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        if not project.repo_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Project is not linked to a GitHub repository."
            )

        try:
            metadata, files = GitService.clone_and_parse_repository(project.repo_url)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        # Check if commit SHA matches the last synced SHA
        if project.last_commit_sha == metadata["last_commit_sha"]:
            project.last_sync_time = datetime.utcnow()
            db.commit()
            db.refresh(project)
            return {
                "status": "up_to_date",
                "message": "Repository is already up to date.",
                "last_commit_sha": project.last_commit_sha,
                "last_sync_time": project.last_sync_time.isoformat() if project.last_sync_time else None
            }

        # If a different commit SHA is detected, we process files
        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No supported files (.py, .java, .js, .ts) found in the repository."
            )

        # Update the project's repository metadata fields
        project.default_branch = metadata["default_branch"]
        project.current_branch = metadata["current_branch"]
        project.last_commit_sha = metadata["last_commit_sha"]
        project.last_commit_message = metadata["last_commit_message"]
        project.last_sync_time = datetime.utcnow()
        project.has_intelligence = False
        db.commit()
        db.refresh(project)

        # Create new Analysis run
        analysis = ProjectRepository.create_analysis(db, project_id, source_type="repository", status="completed")

        for f in files:
            ProjectRepository.create_analysis_file(
                db,
                analysis_id=analysis.id,
                filename=f["filename"],
                extension=f["extension"],
                size=f["size"],
                language=f["language"],
                file_hash=f["hash"],
                content=f["content"]
            )

        summary = f"Repository synchronized successfully. Ingested {len(files)} files at commit {metadata['last_commit_sha'][:7]}."
        report_details = {
            "repo_url": project.repo_url,
            "total_files": len(files),
            "files_by_language": {}
        }
        for f in files:
            lang = f["language"]
            report_details["files_by_language"][lang] = report_details["files_by_language"].get(lang, 0) + 1

        ProjectRepository.create_report(
            db, 
            analysis_id=analysis.id, 
            score=100, 
            summary=summary, 
            details_json=json.dumps(report_details)
        )

        from app.projects.services.version_service import VersionService
        VersionService.record_ingestion_version(db, project_id, analysis.id, summary=f"Synced GitHub repository to commit {metadata['last_commit_sha'][:7]}.")

        # Generate semantic graph cache (v2.2)
        try:
            from app.projects.services.semantic_graph_service import SemanticGraphService
            SemanticGraphService.generate_graph(db, project_id)
        except Exception as ge:
            print(f"Error generating semantic graph on repository sync: {ge}")

        return {
            "status": "synced",
            "message": f"Synchronized successfully to commit {metadata['last_commit_sha'][:7]}.",
            "last_commit_sha": project.last_commit_sha,
            "last_sync_time": project.last_sync_time.isoformat() if project.last_sync_time else None
        }
