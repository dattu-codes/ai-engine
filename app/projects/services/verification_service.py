import json
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.projects.models.project_models import (
    Analysis, AnalysisFile, Report, ReviewFinding, 
    ProjectVersion, ProjectVersionFile, Project
)
from app.projects.services.review_pipeline_services import ReviewOrchestrator
from app.projects.services.activity_service import ActivityService

class VerificationService:
    @staticmethod
    async def verify_fix(
        db: Session, 
        project_id: int, 
        original_finding_id: int, 
        new_version: ProjectVersion, 
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes a background review run on the new codebase version, compiles verification metrics,
        and determines whether the fix should be committed or rolled back.
        """
        project = db.query(Project).filter(Project.id == project_id).first()
        finding = db.query(ReviewFinding).filter(ReviewFinding.id == original_finding_id).first()
        
        # 1. Create a new Analysis run record specifically for the verification
        analysis = Analysis(
            project_id=project_id,
            status="pending",
            source_type="version_fix",
            created_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
            created_by=new_version.created_by
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        # 2. Copy ProjectVersionFiles of the new version to AnalysisFiles of this new analysis
        version_files = db.query(ProjectVersionFile).filter(
            ProjectVersionFile.version_id == new_version.id
        ).all()

        analysis_files = []
        for vf in version_files:
            af = AnalysisFile(
                analysis_id=analysis.id,
                filename=vf.filename,
                extension=vf.extension,
                size=vf.size,
                language=vf.language,
                hash=vf.hash,
                content=vf.content
            )
            db.add(af)
            analysis_files.append(af)
        
        db.commit()

        # Update version's source analysis link
        new_version.source_analysis_id = analysis.id
        db.commit()

        # Log Activity
        ActivityService.log_activity(
            db=db,
            workspace_id=project.workspace_id,
            project_id=project_id,
            user_id=new_version.created_by,
            activity_type="Verification Started",
            entity_type="analysis",
            entity_id=analysis.id,
            description=f"Verification review pipeline execution #{analysis.id} started for version {new_version.version_number}."
        )

        # 3. Execute pipeline on these analysis files
        try:
            analysis.status = "running"
            db.commit()
            
            await ReviewOrchestrator.execute_pipeline(
                db=db,
                analysis_id=analysis.id,
                files=analysis_files,
                api_key=api_key
            )
            
            # Commit successfully finished analysis status and refresh
            db.refresh(analysis)
            db.refresh(finding)
        except Exception as pe:
            analysis.status = "failed"
            analysis.completed_at = datetime.utcnow()
            db.commit()
            
            # Log Activity Failed
            ActivityService.log_activity(
                db=db,
                workspace_id=project.workspace_id,
                project_id=project_id,
                user_id=new_version.created_by,
                activity_type="Verification Failed",
                entity_type="analysis",
                entity_id=analysis.id,
                description=f"Verification run #{analysis.id} failed due to pipeline execution error: {pe}."
            )
            
            return {
                "success": False,
                "analysis_id": analysis.id,
                "score": 0,
                "summary": f"Verification pipeline execution failed: {pe}",
                "risk_report": "High risk - Syntax / parser crash."
            }

        # 4. Check results:
        # Is original finding resolved?
        is_resolved = (finding.status == "Resolved")
        
        # Check if new critical issues were introduced
        new_issues = db.query(ReviewFinding).filter(
            ReviewFinding.project_id == project_id,
            ReviewFinding.analysis_id == analysis.id,
            ReviewFinding.severity.in_(["critical", "high"])
        ).all()
        
        has_new_critical = len(new_issues) > 0

        success = is_resolved and not has_new_critical

        if success:
            score = 100
            summary = "Fix verified successfully. The vulnerability was resolved and no regressions were introduced."
            risk_report = "Low risk - Code base remains stable."
            
            ActivityService.log_activity(
                db=db,
                workspace_id=project.workspace_id,
                project_id=project_id,
                user_id=new_version.created_by,
                activity_type="Verification Completed",
                entity_type="analysis",
                entity_id=analysis.id,
                description=f"Verification run #{analysis.id} completed successfully. Issue #{original_finding_id} resolved."
            )
        else:
            score = 0
            reasons = []
            if not is_resolved:
                reasons.append("Vulnerability was not resolved.")
            if has_new_critical:
                reasons.append(f"Introduced {len(new_issues)} new critical or high severity finding(s).")
            
            summary = f"Verification failed: {'; '.join(reasons)}"
            risk_report = "High risk - Regression detected."
            
            ActivityService.log_activity(
                db=db,
                workspace_id=project.workspace_id,
                project_id=project_id,
                user_id=new_version.created_by,
                activity_type="Verification Failed",
                entity_type="analysis",
                entity_id=analysis.id,
                description=f"Verification run #{analysis.id} failed: {summary}"
            )

        return {
            "success": success,
            "analysis_id": analysis.id,
            "score": score,
            "summary": summary,
            "risk_report": risk_report
        }
