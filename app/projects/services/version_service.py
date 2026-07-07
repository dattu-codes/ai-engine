import json
import hashlib
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.projects.models.project_models import ProjectVersion, ProjectVersionFile, Analysis, AnalysisFile, Report, Project
from app.projects.repositories.project_repository import ProjectRepository
from app.services.ai import GeminiClient
from app.projects.services.activity_service import ActivityService

class AIFixEngine:
    @staticmethod
    async def fix_code(content: str, filename: str, issue: dict, api_key: Optional[str] = None) -> str:
        """
        Applies a codebase repair. In Live Mode, queries the Gemini API to fix the code,
        otherwise runs a localized rules-based search-and-replace simulator.
        """
        if api_key:
            prompt = f"""
You are an expert AI code refactoring engine. Your task is to fix the security, performance, or style issue described below inside the file '{filename}'.

Issue Category: {issue.get('category')}
Severity: {issue.get('severity')}
Description: {issue.get('explanation') or issue.get('description')}
Line Number: {issue.get('line')}
Evidence: {issue.get('evidence')}
Recommendation: {issue.get('recommendation')}

Here is the complete source code of the file:
```
{content}
```

Please fix the issue following the recommendation. Output the complete, updated source code of the file.
Do NOT output any markdown code blocks, explanatory text, or backticks. Return ONLY the code.
"""
            try:
                fixed_code = await GeminiClient.call_gemini(prompt, api_key=api_key)
                if fixed_code.startswith("```"):
                    lines = fixed_code.splitlines()
                    if lines and lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    fixed_code = "\n".join(lines)
                return fixed_code.strip()
            except Exception as e:
                # Fallback to simulator if API error occurs
                print(f"Gemini Fix API call failed, falling back to simulator: {e}")
                pass

        # Offline Rules-based Simulator Mode
        lines = content.splitlines()
        evidence = issue.get("evidence", "").strip()
        line_no = issue.get("line")
        matched = False

        if line_no and 1 <= line_no <= len(lines):
            target_line = lines[line_no - 1]
            if not evidence or evidence in target_line or (target_line.strip() and target_line.strip() in evidence):
                matched = True
                if "eval(" in target_line:
                    lines[line_no - 1] = target_line.replace('eval("arbitrary_string")', '# eval removed for safety')
                    lines[line_no - 1] = lines[line_no - 1].replace("eval(", "# eval removed: ")
                elif "print(" in target_line:
                    lines[line_no - 1] = target_line.replace("print(", "logging.info(")
                    if not any("import logging" in l for l in lines):
                        lines.insert(0, "import logging")
                elif "console.log(" in target_line:
                    lines[line_no - 1] = target_line.replace("console.log(", "// console.log removed: ")
                elif "System.out.println(" in target_line:
                    lines[line_no - 1] = target_line.replace("System.out.println(", "logger.info(")
                elif "pass" in target_line:
                    indent = len(target_line) - len(target_line.lstrip())
                    lines[line_no - 1] = " " * indent + "logging.warning('Exception caught and ignored', exc_info=True)"
                    if not any("import logging" in l for l in lines):
                        lines.insert(0, "import logging")
                elif "TODO" in target_line:
                    lines[line_no - 1] = target_line.replace("TODO", "RESOLVED TODO")
                else:
                    lines[line_no - 1] = f"# Fixed: {target_line}"
                content = "\n".join(lines)

        if not matched:
            # Fallback text replacements if line number is not matching or evidence check failed
            content_lower = content.lower()
            if "eval(" in content:
                content = content.replace('eval("arbitrary_string")', '# eval removed for safety')
            elif "print(" in content:
                content = "import logging\n" + content.replace("print(", "logging.info(")
            elif "pass" in content and "except" in content:
                content = content.replace("pass", "logging.warning('Error logged', exc_info=True)")
                
        return content


class VersionService:
    @staticmethod
    def create_initial_version(db: Session, project_id: int, analysis_id: int) -> ProjectVersion:
        """
        Creates Version 1 baseline snapshot from the project ingestion analysis.
        """
        # Fetch ingestion analysis run
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            raise ValueError(f"Analysis run {analysis_id} not found.")

        # Check if version 1 already exists to prevent duplicate baselines
        existing = db.query(ProjectVersion).filter(
            ProjectVersion.project_id == project_id,
            ProjectVersion.version_number == 1
        ).first()
        if existing:
            return existing

        db_files = db.query(AnalysisFile).filter(AnalysisFile.analysis_id == analysis_id).all()
        
        # Build metadata map
        meta = {f.filename: f.hash for f in db_files}

        project = db.query(Project).filter(Project.id == project_id).first()
        version = ProjectVersion(
            project_id=project_id,
            version_number=1,
            parent_version_id=None,
            source_analysis_id=analysis_id,
            applied_fixes="[]",
            summary="Baseline version created from project ingestion.",
            snapshot_metadata=json.dumps(meta),
            created_by=project.user_id if project else None
        )
        db.add(version)
        db.commit()
        db.refresh(version)

        # Log baseline creation activity
        ActivityService.log_activity(
            db=db,
            workspace_id=project.workspace_id if project else None,
            project_id=project_id,
            user_id=project.user_id if project else None,
            activity_type="Version Created",
            entity_type="version",
            entity_id=version.id,
            description=f"Baseline Version 1 snapshot created from project ingestion."
        )

        # Replicate files to the ProjectVersionFile snapshot table
        for f in db_files:
            vf = ProjectVersionFile(
                version_id=version.id,
                filename=f.filename,
                extension=f.extension,
                size=f.size,
                language=f.language,
                hash=f.hash,
                content=f.content
            )
            db.add(vf)
        
        db.commit()
        db.refresh(version)
        return version

    @classmethod
    async def apply_fix_and_create_version(
        cls,
        db: Session,
        project_id: int,
        issue: dict,
        api_key: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> ProjectVersion:
        """
        Applies a targeted fix to the codebase, increments the project version, and creates a snapshot.
        """
        # 1. Fetch current active (highest) version
        current_version = db.query(ProjectVersion).filter(
            ProjectVersion.project_id == project_id
        ).order_by(ProjectVersion.version_number.desc()).first()

        if not current_version:
            raise ValueError("No baseline version exists for this project yet.")

        target_file = issue.get("file")
        if not target_file:
            raise ValueError("Issue must specify a file path.")

        # Fetch files at current version
        curr_files = db.query(ProjectVersionFile).filter(
            ProjectVersionFile.version_id == current_version.id
        ).all()

        target_vf = next((f for f in curr_files if f.filename == target_file), None)
        if not target_vf:
            raise ValueError(f"File '{target_file}' not found in current version.")

        # 2. Fix target code using the AI/Simulator engine
        fixed_content = await AIFixEngine.fix_code(
            content=target_vf.content or "",
            filename=target_file,
            issue=issue,
            api_key=api_key
        )

        # 3. Create the new immutable version
        new_version_num = current_version.version_number + 1
        fix_summary = issue.get("explanation") or issue.get("description") or f"Fixed issue in {target_file}"
        
        applied_list = [{"file": target_file, "fix": fix_summary, "line": issue.get("line"), "category": issue.get("category")}]

        # Pre-build snapshot metadata map
        meta = {}
        
        new_version = ProjectVersion(
            project_id=project_id,
            version_number=new_version_num,
            parent_version_id=current_version.id,
            source_analysis_id=current_version.source_analysis_id, # will be updated after running analysis
            applied_fixes=json.dumps(applied_list),
            summary=f"Version {new_version_num} - Applied fix for {issue.get('category')} in '{target_file}'.",
            snapshot_metadata="{}",
            created_by=user_id
        )
        db.add(new_version)
        db.commit()
        db.refresh(new_version)

        # 4. Copy all files over to ProjectVersionFile snapshot list, applying fix to target_file
        for f in curr_files:
            if f.filename == target_file:
                # Update file content, size, and hash
                content_bytes = fixed_content.encode("utf-8")
                size = len(content_bytes)
                file_hash = hashlib.sha256(content_bytes).hexdigest()
                content = fixed_content
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

        # Save metadata and commit
        new_version.snapshot_metadata = json.dumps(meta)
        
        # Resolve associated ReviewFinding
        try:
            from app.projects.models.project_models import ReviewFinding
            finding = db.query(ReviewFinding).filter(
                ReviewFinding.project_id == project_id,
                ReviewFinding.file_path == target_file,
                ReviewFinding.category == issue.get("category"),
                ReviewFinding.line_number == issue.get("line"),
                ReviewFinding.status.in_(["Open", "In Progress"])
            ).first()
            if not finding:
                finding = db.query(ReviewFinding).filter(
                    ReviewFinding.project_id == project_id,
                    ReviewFinding.file_path == target_file,
                    ReviewFinding.category == issue.get("category"),
                    ReviewFinding.status.in_(["Open", "In Progress"])
                ).first()
            
            if finding:
                finding.status = "Resolved"
                finding.resolved_at = datetime.utcnow()
                finding.resolved_in_version_id = new_version.id
        except Exception as fe:
            print(f"Error marking finding resolved on fix: {fe}")

        db.commit()
        db.refresh(new_version)

        # Log Version Created activity
        project = db.query(Project).filter(Project.id == project_id).first()
        ActivityService.log_activity(
            db=db,
            workspace_id=project.workspace_id if project else None,
            project_id=project_id,
            user_id=user_id,
            activity_type="Version Created",
            entity_type="version",
            entity_id=new_version.id,
            description=f"Version {new_version_num} created: Applied AI Fix for {issue.get('category')} in '{target_file}'."
        )

        # Generate semantic graph cache (v2.2)
        try:
            from app.projects.services.semantic_graph_service import SemanticGraphService
            SemanticGraphService.generate_graph(db, project_id)
        except Exception as ge:
            print(f"Error generating semantic graph on fix: {ge}")

        return new_version

    @staticmethod
    def restore_version(db: Session, project_id: int, target_version_id: int, user_id: Optional[int] = None) -> ProjectVersion:
        """
        Restores the codebase back to a historical version snapshot by creating a new head version.
        """
        # Fetch target version to restore
        target_version = db.query(ProjectVersion).filter(
            ProjectVersion.id == target_version_id,
            ProjectVersion.project_id == project_id
        ).first()

        if not target_version:
            raise ValueError(f"Version with ID {target_version_id} not found.")

        # Fetch current active version
        current_version = db.query(ProjectVersion).filter(
            ProjectVersion.project_id == project_id
        ).order_by(ProjectVersion.version_number.desc()).first()

        if not current_version:
            raise ValueError("No active version found to restore to.")

        # Create restored version record
        new_version_num = current_version.version_number + 1
        summary = f"Restored codebase state back to Version {target_version.version_number}."
        
        restored_version = ProjectVersion(
            project_id=project_id,
            version_number=new_version_num,
            parent_version_id=current_version.id,
            source_analysis_id=target_version.source_analysis_id,
            applied_fixes=json.dumps([{"restored_from": target_version.version_number}]),
            summary=summary,
            snapshot_metadata=target_version.snapshot_metadata,
            created_by=user_id
        )
        db.add(restored_version)
        db.commit()
        db.refresh(restored_version)

        # Duplicate version files list from the target version
        target_files = db.query(ProjectVersionFile).filter(
            ProjectVersionFile.version_id == target_version.id
        ).all()

        for tf in target_files:
            new_vf = ProjectVersionFile(
                version_id=restored_version.id,
                filename=tf.filename,
                extension=tf.extension,
                size=tf.size,
                language=tf.language,
                hash=tf.hash,
                content=tf.content
            )
            db.add(new_vf)

        db.commit()
        db.refresh(restored_version)

        # Log Version Restored activity
        project = db.query(Project).filter(Project.id == project_id).first()
        ActivityService.log_activity(
            db=db,
            workspace_id=project.workspace_id if project else None,
            project_id=project_id,
            user_id=user_id,
            activity_type="Version Restored",
            entity_type="version",
            entity_id=restored_version.id,
            description=f"Restored codebase back to Version {target_version.version_number}."
        )

        # Generate semantic graph cache (v2.2)
        try:
            from app.projects.services.semantic_graph_service import SemanticGraphService
            SemanticGraphService.generate_graph(db, project_id)
        except Exception as ge:
            print(f"Error generating semantic graph on restore: {ge}")

        return restored_version

    @staticmethod
    def get_version_history(db: Session, project_id: int) -> List[ProjectVersion]:
        """
        Lists version history chronologically for a project.
        """
        return db.query(ProjectVersion).filter(
            ProjectVersion.project_id == project_id
        ).order_by(ProjectVersion.version_number.desc()).all()

    @staticmethod
    def record_ingestion_version(db: Session, project_id: int, analysis_id: int, summary: str = "Updated source code via ingestion.") -> ProjectVersion:
        """
        Records a new project version after code ingestion or sync has completed.
        If no versions exist, creates the baseline Version 1.
        """
        current_version = db.query(ProjectVersion).filter(
            ProjectVersion.project_id == project_id
        ).order_by(ProjectVersion.version_number.desc()).first()

        if not current_version:
            return VersionService.create_initial_version(db, project_id, analysis_id)

        db_files = db.query(AnalysisFile).filter(AnalysisFile.analysis_id == analysis_id).all()
        meta = {f.filename: f.hash for f in db_files}
        new_version_num = current_version.version_number + 1

        version = ProjectVersion(
            project_id=project_id,
            version_number=new_version_num,
            parent_version_id=current_version.id,
            source_analysis_id=analysis_id,
            applied_fixes="[]",
            summary=summary,
            snapshot_metadata=json.dumps(meta)
        )
        db.add(version)
        db.commit()
        db.refresh(version)

        for f in db_files:
            vf = ProjectVersionFile(
                version_id=version.id,
                filename=f.filename,
                extension=f.extension,
                size=f.size,
                language=f.language,
                hash=f.hash,
                content=f.content
            )
            db.add(vf)
        
        db.commit()
        db.refresh(version)
        return version

    @staticmethod
    def create_fix_version(
        db: Session,
        project_id: int,
        parent_version_id: int,
        patch_summary: str,
        verification_score: int,
        files_changed: list,
        ai_model: str,
        execution_metadata: dict,
        user_id: Optional[int] = None
    ) -> ProjectVersion:
        """
        Creates an immutable ProjectVersion record after a successful AI Fix application.
        """
        current_version = db.query(ProjectVersion).filter(
            ProjectVersion.id == parent_version_id
        ).first()

        new_version_num = current_version.version_number + 1 if current_version else 1
        
        meta = {
            "parent_version": parent_version_id,
            "patch_summary": patch_summary,
            "verification_score": verification_score,
            "files_changed": files_changed,
            "ai_model": ai_model,
            "execution_metadata": execution_metadata
        }

        new_version = ProjectVersion(
            project_id=project_id,
            version_number=new_version_num,
            parent_version_id=parent_version_id,
            applied_fixes=json.dumps([{
                "patch_summary": patch_summary, 
                "files_changed": files_changed, 
                "ai_model": ai_model
            }]),
            summary=f"Version {new_version_num} - AI Fix applied by {ai_model}.",
            snapshot_metadata=json.dumps(meta),
            created_by=user_id
        )
        db.add(new_version)
        db.commit()
        db.refresh(new_version)
        return new_version
