import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.projects.models.project_models import Analysis, Report

class PRSummaryService:
    @staticmethod
    def generate_summary(db: Session, analysis_id: int) -> Dict[str, Any]:
        """
        Gathers review metrics and issues statistics from a completed analysis.
        """
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return {
                "error": "Analysis not found",
                "score": 0,
                "summary": "No analysis data available.",
                "severity_distribution": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                "risk_assessment": "low",
                "processing_metrics": {"duration": 0.0, "ai_calls": 0},
                "statistics": {"files_count": 0, "lines_count": 0}
            }

        report = db.query(Report).filter(Report.analysis_id == analysis_id).first()
        score = report.score if report else 0
        summary_text = report.summary if report else "Pending review analysis completion."
        
        # Calculate counts
        severity_dist = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        
        if report and report.details_json:
            try:
                details = json.loads(report.details_json)
                issues = details.get("issues", [])
                for iss in issues:
                    sev = iss.get("severity", "low").lower()
                    if sev in severity_dist:
                        severity_dist[sev] += 1
                    else:
                        # Fallback for unrecognized categories
                        severity_dist["low"] += 1
            except Exception:
                pass

        # Risk assessment mapping
        if severity_dist["critical"] > 0:
            risk = "critical"
        elif severity_dist["high"] > 0:
            risk = "high"
        elif severity_dist["medium"] > 0:
            risk = "medium"
        else:
            risk = "low"

        # Processing and volume stats
        duration = analysis.duration or 0.0
        ai_calls = analysis.ai_calls or 0
        
        # Retrieve stats from analysis files if available
        files_count = analysis.files_reviewed or 0
        
        # Approximate lines count from files list
        lines_count = 0
        from app.projects.models.project_models import AnalysisFile
        db_files = db.query(AnalysisFile).filter(AnalysisFile.analysis_id == analysis_id).all()
        for f in db_files:
            if f.content:
                lines_count += len(f.content.splitlines())

        return {
            "score": score,
            "summary": summary_text,
            "severity_distribution": severity_dist,
            "risk_assessment": risk,
            "processing_metrics": {
                "duration": duration,
                "ai_calls": ai_calls
            },
            "statistics": {
                "files_count": files_count,
                "lines_count": lines_count
            }
        }
