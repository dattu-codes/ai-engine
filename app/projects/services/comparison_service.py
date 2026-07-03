import json
import difflib
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.projects.models.project_models import ProjectVersion, ProjectVersionFile, Report

class ComparisonService:
    @staticmethod
    def compare_versions(db: Session, v1_id: int, v2_id: int) -> Dict[str, Any]:
        """
        Compares two project version snapshots.
        v1: Base/Older version
        v2: Target/Newer version
        """
        v1 = db.query(ProjectVersion).filter(ProjectVersion.id == v1_id).first()
        v2 = db.query(ProjectVersion).filter(ProjectVersion.id == v2_id).first()

        if not v1 or not v2:
            raise ValueError("One or both versions not found.")

        # Load files for both versions
        v1_files = db.query(ProjectVersionFile).filter(ProjectVersionFile.version_id == v1.id).all()
        v2_files = db.query(ProjectVersionFile).filter(ProjectVersionFile.version_id == v2.id).all()

        v1_file_map = {f.filename: f for f in v1_files}
        v2_file_map = {f.filename: f for f in v2_files}

        all_filenames = set(v1_file_map.keys()).union(set(v2_file_map.keys()))

        files_changed = []
        lines_added = 0
        lines_removed = 0
        diffs = {}

        for filename in all_filenames:
            f1 = v1_file_map.get(filename)
            f2 = v2_file_map.get(filename)

            if f1 and f2:
                # File exists in both
                if f1.hash != f2.hash:
                    files_changed.append(filename)
                    c1 = (f1.content or "").splitlines(keepends=True)
                    c2 = (f2.content or "").splitlines(keepends=True)
                    
                    diff = list(difflib.unified_diff(c1, c2, fromfile=f"a/{filename}", tofile=f"b/{filename}"))
                    diffs[filename] = "".join(diff)

                    # Calculate lines added/removed
                    for line in diff:
                        if line.startswith("+") and not line.startswith("+++"):
                            lines_added += 1
                        elif line.startswith("-") and not line.startswith("---"):
                            lines_removed += 1
            elif f2:
                # File added in v2
                files_changed.append(filename)
                c2 = (f2.content or "").splitlines(keepends=True)
                diff = list(difflib.unified_diff([], c2, fromfile="/dev/null", tofile=f"b/{filename}"))
                diffs[filename] = "".join(diff)
                lines_added += len(c2)
            elif f1:
                # File deleted in v2
                files_changed.append(filename)
                c1 = (f1.content or "").splitlines(keepends=True)
                diff = list(difflib.unified_diff(c1, [], fromfile=f"a/{filename}", tofile="/dev/null"))
                diffs[filename] = "".join(diff)
                lines_removed += len(c1)

        # Retrieve and compare issues from associated reports
        v1_issues = []
        v2_issues = []

        if v1.source_analysis_id:
            r1 = db.query(Report).filter(Report.analysis_id == v1.source_analysis_id).first()
            if r1 and r1.details_json:
                try:
                    v1_issues = json.loads(r1.details_json)
                    if isinstance(v1_issues, dict):
                        v1_issues = v1_issues.get("issues", [])
                except Exception:
                    pass

        if v2.source_analysis_id:
            r2 = db.query(Report).filter(Report.analysis_id == v2.source_analysis_id).first()
            if r2 and r2.details_json:
                try:
                    v2_issues = json.loads(r2.details_json)
                    if isinstance(v2_issues, dict):
                        v2_issues = v2_issues.get("issues", [])
                except Exception:
                    pass

        # Match issues to identify fixed and remaining ones
        # Use filename, category, and explanation for uniqueness
        def get_issue_key(iss: dict) -> str:
            return f"{iss.get('file')}:{iss.get('line')}:{iss.get('category')}:{iss.get('explanation') or iss.get('description')}"

        v2_keys = {get_issue_key(iss) for iss in v2_issues}
        
        issues_fixed = []
        for iss in v1_issues:
            key = get_issue_key(iss)
            if key not in v2_keys:
                issues_fixed.append(iss)

        return {
            "files_changed_count": len(files_changed),
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "files_changed": files_changed,
            "issues_fixed": issues_fixed,
            "remaining_issues": v2_issues,
            "diffs": diffs
        }
