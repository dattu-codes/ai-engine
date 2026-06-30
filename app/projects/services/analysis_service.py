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

class AnalysisService:
    @staticmethod
    def start_analysis(db: Session, project_id: int, user_id: int, api_key: str = None) -> Analysis:
        """
        Validates ownership and project files, then schedules the async AI analysis workflow in the background.
        """
        # Verify project ownership
        project = ProjectRepository.get_project(db, project_id, user_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        # Find the latest completed analysis run to extract files from
        latest_completed = ProjectRepository.get_latest_analysis(db, project_id)
        if not latest_completed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Cannot analyze an empty project. Please ingest source files first."
            )

        files = ProjectRepository.get_analysis_files(db, latest_completed.id)
        if not files:
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
        
        # Add execution fields
        analysis.started_at = datetime.utcnow()
        db.commit()
        db.refresh(analysis)

        # Launch the background async task
        asyncio.create_task(
            AnalysisService._execute_analysis_task(
                analysis.id, 
                project.name, 
                files_list, 
                api_key
            )
        )

        return analysis

    @staticmethod
    async def _execute_analysis_task(analysis_id: int, project_name: str, files: list, api_key: str = None):
        """
        Background task to build prompt, execute Gemini API call, parse structured JSON, and persist reports.
        """
        db = SessionLocal()
        start_time = time.time()
        
        # Load the analysis record in this thread's session context
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            db.close()
            return

        try:
            analysis.status = "running"
            db.commit()

            # 1. Build prompt using prompt builder
            prompt = PromptBuilder.build_review_prompt(project_name, files)

            # 2. Call Gemini if API Key is present, else fall back to local mock
            response_json = None
            model_used = "mock-simulator"
            
            if api_key and api_key.strip():
                try:
                    raw_response = await GeminiClient.call_gemini(
                        prompt, 
                        api_key.strip(), 
                        model="gemini-2.5-flash", 
                        json_mode=True
                    )
                    
                    # Clean markdown code block wraps if present
                    cleaned_res = raw_response.strip()
                    if cleaned_res.startswith("```"):
                        lines = cleaned_res.splitlines()
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].startswith("```"):
                            lines = lines[:-1]
                        cleaned_res = "\n".join(lines).strip()
                        
                    response_json = json.loads(cleaned_res)
                    model_used = "gemini-2.5-flash"
                except Exception as e:
                    # Log error internally and fallback
                    print(f"Gemini API execution failed: {str(e)}. Falling back to offline simulator...")
                    response_json = MockAnalysisSimulator.simulate_review(project_name, files)
                    model_used = f"mock-simulator (Gemini Error: {str(e)})"
            else:
                # Direct offline simulation
                response_json = MockAnalysisSimulator.simulate_review(project_name, files)

            # 3. Validate structured response format and calculate metrics
            end_time = time.time()
            duration = float(end_time - start_time)
            score = int(response_json.get("score", 80))
            summary = response_json.get("summary", "Analysis completed successfully.")
            
            # Run Advanced Static Code Analyzers
            analyzer_results = CodeAnalyzerService.analyze_codebase(files)

            # Serialize report details with duration, status and analyzer metrics
            report_data = {
                "summary": summary,
                "score": score,
                "strengths": response_json.get("strengths", []),
                "weaknesses": response_json.get("weaknesses", []),
                "recommendations": response_json.get("recommendations", []),
                "issues": response_json.get("issues", []),
                "execution_time": duration,
                "status": "completed",
                "analyzers": analyzer_results
            }

            # 4. Save Report record in database
            report = Report(
                analysis_id=analysis_id,
                score=score,
                summary=summary,
                details_json=json.dumps(report_data)
            )
            db.add(report)

            # 5. Finalize Analysis run logs
            analysis.status = "completed"
            analysis.completed_at = datetime.utcnow()
            analysis.duration = duration
            analysis.model_used = model_used
            db.commit()

        except Exception as e:
            # Handle unexpected failures
            end_time = time.time()
            analysis.status = "failed"
            analysis.completed_at = datetime.utcnow()
            analysis.duration = float(end_time - start_time)
            analysis.model_used = "error-handler"
            
            # Save error stack trace inside report
            err_report = Report(
                analysis_id=analysis_id,
                score=0,
                summary=f"Analysis pipeline crashed: {str(e)}",
                details_json=json.dumps({"error": str(e)})
            )
            db.add(err_report)
            db.commit()
            print(f"Analysis task exception: {str(e)}")
        finally:
            db.close()
