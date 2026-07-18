import json
import time
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.auth.database.connection import SessionLocal
from app.projects.models.project_models import Project, Analysis, Report, AnalysisFile
from app.projects.repositories.project_repository import ProjectRepository
from app.projects.services.prompt_builder import PromptBuilder
from app.projects.services.analysis_simulator import MockAnalysisSimulator
from app.projects.services.code_analyzer import CodeAnalyzerService
from app.services.ai import GeminiClient
from app.projects.services.review_pipeline_services import ReviewOrchestrator
from app.projects.services.activity_service import ActivityService

class AnalysisService:
    @staticmethod
    def start_analysis(db: Session, project_id: int, user_id: int, api_key: str = None, model: str = None) -> Analysis:
        """
        Validates ownership and project files, then schedules the async AI analysis workflow in the background.
        """
        # Verify project ownership
        project = ProjectRepository.get_project(db, project_id, user_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        # Find the latest completed analysis run that actually has files
        latest_completed = None
        all_analyses = ProjectRepository.get_project_analyses(db, project_id)
        files = []
        for anal in all_analyses:
            if anal.status == "completed":
                files = ProjectRepository.get_analysis_files(db, anal.id)
                if files:
                    latest_completed = anal
                    break

        if not latest_completed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Cannot analyze an empty project. Please ingest source code files first."
            )

        # Prepare code files dictionary context list
        files_list = [
            {
                "filename": f.filename,
                "language": f.language,
                "content": f.content or ""
            }
            for f in files
        ]

        # Initialize the new Analysis run record
        analysis = ProjectRepository.create_analysis(
            db, 
            project_id=project_id, 
            source_type=latest_completed.source_type, 
            status="pending"
        )
        analysis.created_by = user_id
        
        # Add execution fields
        analysis.started_at = datetime.utcnow()
        db.commit()
        db.refresh(analysis)

        # Associate this analysis with the latest ProjectVersion
        from app.projects.models.project_models import ProjectVersion
        latest_version = db.query(ProjectVersion).filter(
            ProjectVersion.project_id == project_id
        ).order_by(ProjectVersion.version_number.desc()).first()
        if latest_version:
            latest_version.source_analysis_id = analysis.id
            db.commit()

        # Log Activity
        ActivityService.log_activity(
            db=db,
            workspace_id=project.workspace_id,
            project_id=project_id,
            user_id=user_id,
            activity_type="Analysis Started",
            entity_type="analysis",
            entity_id=analysis.id,
            description=f"AI Review Analysis run #{analysis.id} started on project '{project.name}'."
        )

        # Launch the background async task
        asyncio.create_task(
            AnalysisService._execute_analysis_task(
                analysis.id, 
                project.name, 
                files_list, 
                api_key,
                model
            )
        )

        return analysis

    @staticmethod
    async def _execute_analysis_task(analysis_id: int, project_name: str, files_list: list, api_key: str = None, model: str = None):
        """
        Background task delegating to ReviewOrchestrator.
        """
        db = SessionLocal()
        try:
            analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
            if not analysis:
                return

            analysis.status = "running"
            db.commit()

            # Retrieve database analysis files from latest completed run that has files
            db_files = []
            completed_analyses = db.query(Analysis)\
                .filter(Analysis.project_id == analysis.project_id)\
                .filter(Analysis.status == "completed")\
                .filter(Analysis.id != analysis_id)\
                .order_by(Analysis.id.desc())\
                .all()
            for ca in completed_analyses:
                db_files = db.query(AnalysisFile).filter(AnalysisFile.analysis_id == ca.id).all()
                if db_files:
                    break
            
            if not db_files:
                db_files = db.query(AnalysisFile).filter(AnalysisFile.analysis_id == analysis_id).all()
            
            # Execute pipeline
            await ReviewOrchestrator.execute_pipeline(
                db=db,
                analysis_id=analysis_id,
                files=db_files,
                api_key=api_key,
                model=model
            )

            # Generate Repository Insights automatically on completion of the analysis pipeline
            try:
                from app.projects.services.repository_insights_service import RepositoryInsightsService
                RepositoryInsightsService.generate_insight(db, analysis.project_id)
            except Exception as re_err:
                print(f"Error auto-generating repository insights: {re_err}")

            # Log Activity Success
            analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
            if analysis:
                project = db.query(Project).filter(Project.id == analysis.project_id).first()
                ActivityService.log_activity(
                    db=db,
                    workspace_id=project.workspace_id if project else None,
                    project_id=analysis.project_id,
                    user_id=analysis.created_by,
                    activity_type="Analysis Completed",
                    entity_type="analysis",
                    entity_id=analysis_id,
                    description=f"AI Review Analysis run #{analysis_id} completed successfully for '{project.name if project else 'project'}'."
                )
        except Exception as e:
            # Handle unexpected failures
            analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
            if analysis:
                analysis.status = "failed"
                analysis.completed_at = datetime.utcnow()
                
                # Save error report
                err_report = Report(
                    analysis_id=analysis_id,
                    score=0,
                    summary=f"Analysis pipeline crashed: {str(e)}",
                    details_json=json.dumps({"error": str(e), "pipeline_stages": getattr(analysis, "pipeline_stages", None)})
                )
                db.add(err_report)
                db.commit()

                # Log Activity Failure
                project = db.query(Project).filter(Project.id == analysis.project_id).first()
                ActivityService.log_activity(
                    db=db,
                    workspace_id=project.workspace_id if project else None,
                    project_id=analysis.project_id,
                    user_id=analysis.created_by,
                    activity_type="Analysis Failed",
                    entity_type="analysis",
                    entity_id=analysis_id,
                    description=f"AI Review Analysis run #{analysis_id} failed: {str(e)}."
                )
            print(f"Analysis task exception: {str(e)}")
        finally:
            db.close()
