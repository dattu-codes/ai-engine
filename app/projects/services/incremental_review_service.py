import time
import asyncio
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any
import json
from sqlalchemy.orm import Session
from app.projects.models.project_models import Analysis, AnalysisFile, PullRequest, Project
from app.projects.services.review_pipeline_services import ReviewOrchestrator
from app.projects.repositories.project_repository import ProjectRepository
from app.projects.services.zip_processor import ZipProcessor

class IncrementalReviewService:
    @staticmethod
    async def start_pr_review(
        db: Session, 
        project_id: int, 
        pr_id: int, 
        changed_files: list, 
        api_key: str = None,
        user_id: Optional[int] = None
    ) -> Analysis:
        """
        Creates a new Analysis record associated with the PullRequest, constructs the 
        changed-file context, and triggers the ReviewOrchestrator.execute_pipeline.
        """
        # 1. Create a new Analysis run record
        analysis = ProjectRepository.create_analysis(
            db,
            project_id=project_id,
            source_type="repository",
            status="pending"
        )
        analysis.created_by = user_id
        
        # Link to the pull request
        analysis.pull_request_id = pr_id
        analysis.started_at = datetime.utcnow()
        db.commit()
        db.refresh(analysis)

        # Log Activity
        try:
            from app.projects.services.activity_service import ActivityService
            project = db.query(Project).filter(Project.id == project_id).first()
            ActivityService.log_activity(
                db=db,
                workspace_id=project.workspace_id if project else None,
                project_id=project_id,
                user_id=user_id,
                activity_type="PR Review Started",
                entity_type="analysis",
                entity_id=analysis.id,
                description=f"PR Review started for analysis run #{analysis.id}."
            )
        except Exception as ae:
            print(f"Error logging PR review start activity: {ae}")
        
        # 2. Insert only the modified files into the AnalysisFile table for this analysis run
        db_files = []
        supported_exts = ZipProcessor.SUPPORTED_EXTENSIONS
        
        for file_info in changed_files:
            filename = file_info["filename"]
            content = file_info.get("content", "")
            
            # Determine language based on extension
            dot_idx = filename.rfind(".")
            ext = filename[dot_idx:].lower() if dot_idx != -1 else ""
            language = supported_exts.get(ext, "Plain Text")
            
            file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            
            db_file = AnalysisFile(
                analysis_id=analysis.id,
                filename=filename,
                extension=ext,
                size=len(content),
                language=language,
                hash=file_hash,
                content=content
            )
            db.add(db_file)
            db_files.append(db_file)
            
        db.commit()
        
        # 3. Trigger the asynchronous review orchestrator task safely across thread environments
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                IncrementalReviewService._execute_pr_analysis(
                    analysis.id,
                    db_files,
                    api_key
                )
            )
        except RuntimeError:
            try:
                import anyio
                anyio.from_thread.run_sync(
                    lambda: asyncio.create_task(
                        IncrementalReviewService._execute_pr_analysis(
                            analysis.id,
                            db_files,
                            api_key
                        )
                    )
                )
            except Exception:
                try:
                    main_loop = asyncio.get_event_loop_policy().get_event_loop()
                    asyncio.run_coroutine_threadsafe(
                        IncrementalReviewService._execute_pr_analysis(
                            analysis.id,
                            db_files,
                            api_key
                        ),
                        main_loop
                    )
                except Exception:
                    import threading
                    def run_sync_fallback():
                        asyncio.run(
                            IncrementalReviewService._execute_pr_analysis(
                                analysis.id,
                                db_files,
                                api_key
                            )
                        )
                    threading.Thread(target=run_sync_fallback, daemon=True).start()
        
        return analysis

    @staticmethod
    async def _execute_pr_analysis(analysis_id: int, db_files: list, api_key: str = None):
        """Asynchronously runs ReviewOrchestrator on the changed files context."""
        from app.auth.database.connection import SessionLocal
        db = SessionLocal()
        try:
            analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
            if not analysis:
                return
                
            analysis.status = "running"
            db.commit()
            
            # Regenerate Semantic Graph cache (v2.2)
            try:
                from app.projects.services.semantic_graph_service import SemanticGraphService
                SemanticGraphService.generate_graph(db, analysis.project_id)
            except Exception as ge:
                print(f"Error generating semantic graph on PR review: {ge}")

            # Run the existing ReviewOrchestrator pipeline using only the PR files
            await ReviewOrchestrator.execute_pipeline(
                db=db,
                analysis_id=analysis_id,
                files=db_files,
                api_key=api_key
            )

            # Calculate overall PR impact (v2.2)
            pr_impact_details = []
            max_risk = "Low Risk"
            overall_impacted_files = set()
            overall_impacted_modules = set()
            
            try:
                from app.projects.services.impact_analysis_service import ImpactAnalysisService
                from app.projects.services.review_pipeline_services import ModuleGrouper
                for dbf in db_files:
                    fpath = dbf.filename.replace("\\", "/")
                    impact = ImpactAnalysisService.analyze_impact(db, analysis.project_id, fpath)
                    
                    if impact["risk_rating"] == "High Risk":
                        max_risk = "High Risk"
                    elif impact["risk_rating"] == "Medium Risk" and max_risk != "High Risk":
                        max_risk = "Medium Risk"
                        
                    for f in impact["dependent_files"]:
                        overall_impacted_files.add(f)
                        _, mod, _ = ModuleGrouper.get_priority_and_module(f)
                        if mod:
                            overall_impacted_modules.add(mod)
                            
                    pr_impact_details.append({
                        "file_path": fpath,
                        "risk_score": impact["risk_score"],
                        "risk_rating": impact["risk_rating"],
                        "dependent_files": impact["dependent_files"]
                    })
            except Exception as ie:
                print(f"Error calculating PR impact metrics: {ie}")

            # Enrich generated report with semantic impact
            from app.projects.models.project_models import Report
            report = db.query(Report).filter(Report.analysis_id == analysis_id).first()
            if report:
                try:
                    rep_details = json.loads(report.details_json) if report.details_json else {}
                except Exception:
                    rep_details = {}
                
                rep_details["pr_semantic_impact"] = {
                    "overall_risk": max_risk,
                    "impacted_files": list(overall_impacted_files),
                    "impacted_modules": list(overall_impacted_modules),
                    "file_details": pr_impact_details
                }
                report.summary = f"Pull Request review completed. Dependency Risk: {max_risk}. " + (report.summary or "")
                report.details_json = json.dumps(rep_details)
                db.commit()
            
            # Update PullRequest record's latest_analysis_id
            if analysis.pull_request_id:
                pr = db.query(PullRequest).filter(PullRequest.id == analysis.pull_request_id).first()
                if pr:
                    pr.latest_analysis_id = analysis_id
                    db.commit()

            # Log Activity Success
            try:
                from app.projects.services.activity_service import ActivityService
                project = db.query(Project).filter(Project.id == analysis.project_id).first()
                ActivityService.log_activity(
                    db=db,
                    workspace_id=project.workspace_id if project else None,
                    project_id=analysis.project_id,
                    user_id=analysis.created_by,
                    activity_type="PR Review Completed",
                    entity_type="analysis",
                    entity_id=analysis_id,
                    description=f"PR Review completed successfully for analysis run #{analysis_id}."
                )
            except Exception as ae:
                print(f"Error logging PR review success activity: {ae}")
        except Exception as e:
            analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
            if analysis:
                analysis.status = "failed"
                analysis.completed_at = datetime.utcnow()
                
                from app.projects.models.project_models import Report
                err_report = Report(
                    analysis_id=analysis_id,
                    score=0,
                    summary=f"PR Review execution crashed: {str(e)}",
                    details_json=json.dumps({"error": str(e)})
                )
                db.add(err_report)
                db.commit()

                # Log Activity Failure
                try:
                    from app.projects.services.activity_service import ActivityService
                    project = db.query(Project).filter(Project.id == analysis.project_id).first()
                    ActivityService.log_activity(
                        db=db,
                        workspace_id=project.workspace_id if project else None,
                        project_id=analysis.project_id,
                        user_id=analysis.created_by,
                        activity_type="PR Review Failed",
                        entity_type="analysis",
                        entity_id=analysis_id,
                        description=f"PR Review failed for analysis run #{analysis_id}: {str(e)}."
                    )
                except Exception as ae:
                    print(f"Error logging PR review failure activity: {ae}")
            print(f"PR Analysis task exception: {str(e)}")
        finally:
            db.close()
