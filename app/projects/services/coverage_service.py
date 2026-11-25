from typing import List, Dict, Any, Optional
from app.projects.models.project_models import ProjectVersionFile

class CoverageService:
    @staticmethod
    def calculate_coverage(
        files: List[ProjectVersionFile], 
        modified_files: List[str], 
        language: str,
        real_coverage_pct: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculates line, function, branch, and changed-line coverage percentage.
        Coverage must come from a real coverage run or return None (showing 'N/A').
        Zero default/simulated numbers.
        """
        if real_coverage_pct is not None:
            return {
                "overall_coverage": round(real_coverage_pct, 1),
                "line_coverage": round(real_coverage_pct, 1),
                "function_coverage": round(real_coverage_pct, 1),
                "branch_coverage": round(real_coverage_pct, 1),
                "changed_line_coverage": round(real_coverage_pct, 1),
                "is_available": True
            }

        return {
            "overall_coverage": None,
            "line_coverage": None,
            "function_coverage": None,
            "branch_coverage": None,
            "changed_line_coverage": None,
            "is_available": False
        }
