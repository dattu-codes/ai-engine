import difflib
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.projects.models.project_models import ReviewFinding, ProjectVersion, ProjectVersionFile
from app.projects.services.version_service import AIFixEngine

class PatchGenerator:
    @staticmethod
    async def generate_patch(
        db: Session, 
        finding: ReviewFinding, 
        current_version: ProjectVersion, 
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates a patch containing original code, replacement code, unified diff, and metadata.
        """
        target_file = finding.file_path
        
        # Load current active version file content
        version_file = db.query(ProjectVersionFile).filter(
            ProjectVersionFile.version_id == current_version.id,
            ProjectVersionFile.filename == target_file
        ).first()

        if not version_file:
            raise ValueError(f"File '{target_file}' not found in current snapshot.")

        original_code = version_file.content or ""
        
        # Run code fixer
        # We reuse AIFixEngine.fix_code directly (which automatically manages Gemini calls or offline simulator replacement rules)
        issue_payload = {
            "category": finding.category,
            "severity": finding.severity,
            "description": finding.description,
            "line": finding.line_number,
            "recommendation": finding.recommendation
        }
        
        # Fetch mock evidence or line content
        lines = original_code.splitlines()
        if 1 <= finding.line_number <= len(lines):
            issue_payload["evidence"] = lines[finding.line_number - 1].strip()

        replacement_code = await AIFixEngine.fix_code(
            content=original_code,
            filename=target_file,
            issue=issue_payload,
            api_key=api_key
        )

        # Generate unified diff
        c1 = original_code.splitlines(keepends=True)
        c2 = replacement_code.splitlines(keepends=True)
        
        diff = list(difflib.unified_diff(
            c1, c2, 
            fromfile=f"a/{target_file}", 
            tofile=f"b/{target_file}"
        ))
        unified_diff = "".join(diff)

        explanation = f"Automated refactoring applied to secure database connection or style in {target_file}."
        if finding.category == "Security":
            explanation = f"Refactored user-controlled values to parameterization/sanitization on line {finding.line_number} of {target_file}."

        # Risk estimation
        risk = "Low"
        if finding.severity.lower() == "critical" or finding.severity.lower() == "high":
            risk = "Medium"

        return {
            "file": target_file,
            "original_code": original_code,
            "replacement_code": replacement_code,
            "unified_diff": unified_diff,
            "explanation": explanation,
            "confidence": finding.confidence,
            "estimated_risk": risk
        }
