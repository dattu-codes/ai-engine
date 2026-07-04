import time
import asyncio
import hashlib
from datetime import datetime
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
        api_key: str = None
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
        
        # Link to the pull request
        analysis.pull_request_id = pr_id
        analysis.started_at = datetime.utcnow()
        db.commit()
        db.refresh(analysis)
        
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
            
            # Run the existing ReviewOrchestrator pipeline using only the PR files
            await ReviewOrchestrator.execute_pipeline(
                db=db,
                analysis_id=analysis_id,
                files=db_files,
                api_key=api_key
            )
            
            # Update PullRequest record's latest_analysis_id
            if analysis.pull_request_id:
                pr = db.query(PullRequest).filter(PullRequest.id == analysis.pull_request_id).first()
                if pr:
                    pr.latest_analysis_id = analysis_id
                    db.commit()
        except Exception as e:
            analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
            if analysis:
                analysis.status = "failed"
                analysis.completed_at = datetime.utcnow()
                
                from app.projects.models.project_models import Report
                import json
                err_report = Report(
                    analysis_id=analysis_id,
                    score=0,
                    summary=f"PR Review execution crashed: {str(e)}",
                    details_json=json.dumps({"error": str(e)})
                )
                db.add(err_report)
                db.commit()
            print(f"PR Analysis task exception: {str(e)}")
        finally:
            db.close()
