import time
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.projects.models.project_models import ReviewFinding, ProjectVersion, FixExecution, Project
from app.projects.services.fix_planner import FixPlanner
from app.projects.services.patch_generator import PatchGenerator
from app.projects.services.patch_validator import PatchValidator
from app.projects.services.fix_executor import FixExecutor
from app.projects.services.verification_service import VerificationService
from app.projects.services.version_service import VersionService
from app.projects.services.activity_service import ActivityService

class AIFixCenter:
    @staticmethod
    async def generate_fix(db: Session, finding_id: int, api_key: Optional[str] = None) -> FixExecution:
        """
        Initiates the fix cycle, plans the patch, generates unified diff previews,
        and transitions the status to 'Waiting Approval'.
        """
        finding = db.query(ReviewFinding).filter(ReviewFinding.id == finding_id).first()
        if not finding:
            raise ValueError(f"Review Finding with ID {finding_id} not found.")

        # Find current active version
        current_version = db.query(ProjectVersion).filter(
            ProjectVersion.project_id == finding.project_id
        ).order_by(ProjectVersion.version_number.desc()).first()

        if not current_version:
            raise ValueError("No baseline version exists for this project. Please ingest source code first.")

        # 1. Create a Pending execution record
        fix_exec = FixExecution(
            project_id=finding.project_id,
            finding_id=finding_id,
            version_before_id=current_version.id,
            analysis_before_id=finding.analysis_id,
            status="Pending",
            ai_model="gemini-2.5-flash" if api_key else "mock-simulator",
            created_at=datetime.utcnow()
        )
        db.add(fix_exec)
        db.commit()
        db.refresh(fix_exec)

        # 2. Planning phase
        fix_exec.status = "Planning"
        db.commit()
        
        project = db.query(Project).filter(Project.id == finding.project_id).first()
        ActivityService.log_activity(
            db=db,
            workspace_id=project.workspace_id,
            project_id=finding.project_id,
            user_id=finding.assigned_by or project.user_id,
            activity_type="Fix Planned",
            entity_type="finding",
            entity_id=finding_id,
            description=f"AI Fix planning initiated for finding #{finding_id} in {finding.file_path}."
        )

        plan = await FixPlanner.create_plan(db, finding, api_key=api_key)
        fix_exec.fix_plan_json = json.dumps(plan)
        fix_exec.confidence_score = plan.get("confidence", 0.0)
        fix_exec.impact_score = plan.get("impact_score", 0.0)
        fix_exec.estimated_risk = plan.get("estimated_risk", "Low")
        fix_exec.status = "Generating"
        db.commit()

        # 3. Patch generation phase
        ActivityService.log_activity(
            db=db,
            workspace_id=project.workspace_id,
            project_id=finding.project_id,
            user_id=finding.assigned_by or project.user_id,
            activity_type="Patch Generated",
            entity_type="finding",
            entity_id=finding_id,
            description=f"AI Patch generation started for finding #{finding_id}."
        )

        patch = await PatchGenerator.generate_patch(db, finding, current_version, api_key=api_key)
        fix_exec.patch_summary = patch.get("unified_diff", "")
        fix_exec.files_modified = json.dumps([patch.get("file")])
        
        # Calculate line additions/deletions stats from diff
        lines_added = 0
        lines_removed = 0
        for line in patch.get("unified_diff", "").splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                lines_added += 1
            elif line.startswith("-") and not line.startswith("---"):
                lines_removed += 1
        
        fix_exec.lines_added = lines_added
        fix_exec.lines_removed = lines_removed
        fix_exec.status = "Waiting Approval"
        db.commit()

        ActivityService.log_activity(
            db=db,
            workspace_id=project.workspace_id,
            project_id=finding.project_id,
            user_id=finding.assigned_by or project.user_id,
            activity_type="Preview Created",
            entity_type="finding",
            entity_id=finding_id,
            description=f"AI Patch preview and unified diff generated for finding #{finding_id}."
        )

        return fix_exec

    @staticmethod
    async def approve_fix(db: Session, fix_execution_id: int, api_key: Optional[str] = None) -> FixExecution:
        """
        Approves and applies the generated patch. Validates, commits version,
        verifies using the AI review pipeline, and auto-rolls back if verification fails.
        """
        fix_exec = db.query(FixExecution).filter(FixExecution.id == fix_execution_id).first()
        if not fix_exec:
            raise ValueError(f"Fix execution #{fix_execution_id} not found.")

        if fix_exec.status != "Waiting Approval":
            raise ValueError(f"Cannot approve fix execution in status '{fix_exec.status}'.")

        project = db.query(Project).filter(Project.id == fix_exec.project_id).first()
        finding = fix_exec.finding
        
        # Log Approval
        ActivityService.log_activity(
            db=db,
            workspace_id=project.workspace_id,
            project_id=fix_exec.project_id,
            user_id=finding.assigned_by or project.user_id,
            activity_type="Patch Approved",
            entity_type="finding",
            entity_id=finding.id,
            description=f"User approved patch for finding #{finding.id}."
        )

        # 1. Validation phase
        fix_exec.status = "Validating"
        db.commit()

        # Re-fetch version and patch code details
        current_version = db.query(ProjectVersion).filter(
            ProjectVersion.project_id == fix_exec.project_id
        ).order_by(ProjectVersion.version_number.desc()).first()

        # The patch preview / replacement code needs to be reconstructed or load the cached generation
        # To avoid storing massive contents, we can quickly regenerate or lookup
        patch_info = await PatchGenerator.generate_patch(db, finding, current_version, api_key=api_key)
        replacement_code = patch_info.get("replacement_code")
        target_file = patch_info.get("file")

        start_time = time.time()

        try:
            PatchValidator.validate(replacement_code, target_file)
        except ValueError as ve:
            fix_exec.status = "Failed"
            fix_exec.failure_reason = f"Validation failed: {ve}"
            fix_exec.completed_at = datetime.utcnow()
            db.commit()
            return fix_exec

        # 2. Applying / Versioning phase
        fix_exec.status = "Applying"
        db.commit()

        ActivityService.log_activity(
            db=db,
            workspace_id=project.workspace_id,
            project_id=fix_exec.project_id,
            user_id=finding.assigned_by or project.user_id,
            activity_type="Patch Applied",
            entity_type="finding",
            entity_id=finding.id,
            description=f"Patch successfully applied to workspace file: {target_file}."
        )

        fix_exec.status = "Versioning"
        db.commit()

        try:
            # Create new version
            new_version = FixExecutor.apply_patch(db, fix_exec, replacement_code)
            fix_exec.version_after_id = new_version.id
            db.commit()
        except Exception as ee:
            fix_exec.status = "Failed"
            fix_exec.failure_reason = f"Application or snapshot generation failed: {ee}"
            fix_exec.completed_at = datetime.utcnow()
            db.commit()
            return fix_exec

        # 3. Verification phase
        fix_exec.status = "Verifying"
        db.commit()

        verify_result = await VerificationService.verify_fix(
            db=db,
            project_id=fix_exec.project_id,
            original_finding_id=finding.id,
            new_version=new_version,
            api_key=api_key
        )

        fix_exec.analysis_after_id = verify_result.get("analysis_id")
        fix_exec.verification_score = verify_result.get("score", 0)
        fix_exec.execution_time = time.time() - start_time
        fix_exec.completed_at = datetime.utcnow()

        if verify_result.get("success"):
            # Update finding status to Resolved
            finding.status = "Resolved"
            finding.resolved_at = datetime.utcnow()
            finding.resolved_in_version_id = new_version.id
            
            fix_exec.status = "Completed"
            db.commit()
        else:
            # Revert to version_before_id!
            fix_exec.status = "Failed"
            fix_exec.failure_reason = verify_result.get("summary")
            db.commit()
            
            # Execute auto-rollback!
            await AIFixCenter.rollback_fix(db, fix_exec.id)

        return fix_exec

    @staticmethod
    async def reject_fix(db: Session, fix_execution_id: int) -> FixExecution:
        """
        Rejects the generated patch, transitioning status to 'Failed'.
        """
        fix_exec = db.query(FixExecution).filter(FixExecution.id == fix_execution_id).first()
        if not fix_exec:
            raise ValueError(f"Fix execution #{fix_execution_id} not found.")

        if fix_exec.status != "Waiting Approval":
            raise ValueError(f"Cannot reject fix execution in status '{fix_exec.status}'.")

        fix_exec.status = "Failed"
        fix_exec.failure_reason = "Rejected by user."
        fix_exec.completed_at = datetime.utcnow()
        db.commit()

        project = db.query(Project).filter(Project.id == fix_exec.project_id).first()
        ActivityService.log_activity(
            db=db,
            workspace_id=project.workspace_id,
            project_id=fix_exec.project_id,
            user_id=None,
            activity_type="Verification Failed",
            entity_type="finding",
            entity_id=fix_exec.finding_id,
            description=f"AI patch for finding #{fix_exec.finding_id} was rejected by user."
        )

        return fix_exec

    @staticmethod
    async def rollback_fix(db: Session, fix_execution_id: int) -> FixExecution:
        """
        Restores the codebase back to the prior version snapshot.
        """
        fix_exec = db.query(FixExecution).filter(FixExecution.id == fix_execution_id).first()
        if not fix_exec:
            raise ValueError(f"Fix execution #{fix_execution_id} not found.")

        if not fix_exec.version_before_id:
            raise ValueError("No prior version recorded to rollback to.")

        project = db.query(Project).filter(Project.id == fix_exec.project_id).first()
        
        # Restore version using VersionService.restore_version
        restored_version = VersionService.restore_version(
            db=db,
            project_id=fix_exec.project_id,
            target_version_id=fix_exec.version_before_id,
            user_id=None
        )

        fix_exec.status = "Rolled Back"
        db.commit()

        # Ensure the finding status goes back to Open
        finding = fix_exec.finding
        if finding:
            finding.status = "Open"
            finding.resolved_at = None
            finding.resolved_in_version_id = None
            db.commit()

        # Log Rollback Activity
        ActivityService.log_activity(
            db=db,
            workspace_id=project.workspace_id,
            project_id=fix_exec.project_id,
            user_id=None,
            activity_type="Rollback Executed",
            entity_type="version",
            entity_id=restored_version.id,
            description=f"Rollback executed successfully. Codebase reverted to version {fix_exec.version_before_id}."
        )

        return fix_exec
