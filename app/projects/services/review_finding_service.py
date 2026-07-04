import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.projects.models.project_models import ReviewFinding, ProjectVersion, Analysis

class ReviewFindingService:
    @staticmethod
    def sync_findings(
        db: Session,
        project_id: int,
        analysis_id: int,
        issues: List[Dict[str, Any]],
        reviewed_files: Optional[List[str]] = None
    ) -> List[ReviewFinding]:
        """
        Synchronizes newly generated review issues with the persistent ReviewFinding table.
        - Identifies duplicates/matching findings based on file_path, category, and line/explanation similarity.
        - Reopens previously resolved/ignored findings if the issue persists in the current run.
        - Updates active findings' metadata.
        - Creates new findings for newly discovered issues.
        - Resolves existing active findings in the reviewed file context that did not re-appear.
        """
        # 1. Fetch all existing findings for this project
        existing_findings = db.query(ReviewFinding).filter(
            ReviewFinding.project_id == project_id
        ).all()

        # Helper set to track which db findings are matched in the current analysis run
        matched_db_finding_ids = set()
        synced_findings = []

        # 2. Iterate through new issues from the analysis run
        for issue in issues:
            file_path = issue.get("file", "").replace("\\", "/")
            line_number = int(issue.get("line", 1))
            category = issue.get("category", "Bug")
            severity = issue.get("severity", "medium").lower()
            explanation = issue.get("explanation", "").strip()
            recommendation = issue.get("recommendation", "").strip()
            confidence = float(issue.get("confidence", 0.8))
            evidence = issue.get("evidence", "").strip()
            
            # Construct a human-readable title
            title = f"{category} issue in {file_path}"
            if evidence:
                title = f"{category}: {evidence[:50]}"
                if len(evidence) > 50:
                    title += "..."

            # Find matching existing finding
            matched_finding = None
            for ef in existing_findings:
                # Match criteria: file_path and category must match
                if ef.file_path == file_path and ef.category == category:
                    # Also match by line_number OR description similarity
                    desc_match = (ef.description.strip() == explanation or explanation in ef.description or ef.description in explanation)
                    line_match = (ef.line_number == line_number)
                    if line_match or desc_match:
                        matched_finding = ef
                        break

            if matched_finding:
                # Update existing finding
                matched_finding.analysis_id = analysis_id
                matched_finding.line_number = line_number
                matched_finding.severity = severity
                matched_finding.description = explanation
                matched_finding.recommendation = recommendation
                matched_finding.confidence = confidence
                matched_finding.updated_at = datetime.utcnow()

                # Reopen finding if it was resolved or ignored
                if matched_finding.status in ["Resolved", "Ignored"]:
                    matched_finding.status = "Open"
                    matched_finding.resolved_at = None
                    matched_finding.resolved_in_version_id = None

                matched_db_finding_ids.add(matched_finding.id)
                synced_findings.append(matched_finding)
            else:
                # Create a new finding
                new_finding = ReviewFinding(
                    project_id=project_id,
                    analysis_id=analysis_id,
                    file_path=file_path,
                    line_number=line_number,
                    category=category,
                    severity=severity,
                    title=title,
                    description=explanation,
                    recommendation=recommendation,
                    confidence=confidence,
                    status="Open",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(new_finding)
                db.commit()
                db.refresh(new_finding)
                matched_db_finding_ids.add(new_finding.id)
                synced_findings.append(new_finding)

        # 3. Handle Auto-Resolution of disappeared findings
        # Only resolve findings that belong to files that were actually reviewed in this analysis!
        # If reviewed_files is not specified, resolve all other findings in the project (regular project review).
        active_findings_to_resolve_query = db.query(ReviewFinding).filter(
            ReviewFinding.project_id == project_id,
            ReviewFinding.status.in_(["Open", "In Progress"]),
            ~ReviewFinding.id.in_(list(matched_db_finding_ids)) if matched_db_finding_ids else True
        )

        if reviewed_files is not None:
            normalized_reviewed = [f.replace("\\", "/") for f in reviewed_files]
            active_findings_to_resolve_query = active_findings_to_resolve_query.filter(
                ReviewFinding.file_path.in_(normalized_reviewed)
            )

        findings_to_resolve = active_findings_to_resolve_query.all()
        for f in findings_to_resolve:
            f.status = "Resolved"
            f.resolved_at = datetime.utcnow()
            # Try to associate with the current latest project version if available
            latest_version = db.query(ProjectVersion).filter(
                ProjectVersion.project_id == project_id
            ).order_by(ProjectVersion.version_number.desc()).first()
            if latest_version:
                f.resolved_in_version_id = latest_version.id

        db.commit()
        return synced_findings

    @staticmethod
    def get_findings_history(db: Session, project_id: int) -> List[Dict[str, Any]]:
        """
        Returns a timeline history of resolved findings to calculate resolution rates.
        """
        resolved_findings = db.query(ReviewFinding).filter(
            ReviewFinding.project_id == project_id,
            ReviewFinding.status == "Resolved",
            ReviewFinding.resolved_at != None
        ).order_by(ReviewFinding.resolved_at.asc()).all()

        history = []
        for f in resolved_findings:
            history.append({
                "id": f.id,
                "title": f.title,
                "category": f.category,
                "severity": f.severity,
                "resolved_at": f.resolved_at.isoformat() if f.resolved_at else None,
                "created_at": f.created_at.isoformat() if f.created_at else None
            })
        return history

    @staticmethod
    def update_finding_status(db: Session, finding_id: int, status: str) -> ReviewFinding:
        finding = db.query(ReviewFinding).filter(ReviewFinding.id == finding_id).first()
        if not finding:
            raise ValueError(f"Finding with ID {finding_id} not found.")
        
        valid_statuses = ["Open", "In Progress", "Resolved", "Ignored"]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")
            
        finding.status = status
        finding.updated_at = datetime.utcnow()
        if status == "Resolved":
            finding.resolved_at = datetime.utcnow()
            # Try to associate with the current latest project version if available
            latest_version = db.query(ProjectVersion).filter(
                ProjectVersion.project_id == finding.project_id
            ).order_by(ProjectVersion.version_number.desc()).first()
            if latest_version:
                finding.resolved_in_version_id = latest_version.id
        else:
            finding.resolved_at = None
            finding.resolved_in_version_id = None
            
        db.commit()
        db.refresh(finding)
        return finding

    @staticmethod
    def assign_finding(db: Session, finding_id: int, username: Optional[str]) -> ReviewFinding:
        finding = db.query(ReviewFinding).filter(ReviewFinding.id == finding_id).first()
        if not finding:
            raise ValueError(f"Finding with ID {finding_id} not found.")
        finding.assigned_to = username
        finding.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(finding)
        return finding

    @staticmethod
    def ignore_finding(db: Session, finding_id: int, reason: Optional[str]) -> ReviewFinding:
        finding = db.query(ReviewFinding).filter(ReviewFinding.id == finding_id).first()
        if not finding:
            raise ValueError(f"Finding with ID {finding_id} not found.")
        finding.status = "Ignored"
        finding.ignored_reason = reason
        finding.resolved_at = None
        finding.resolved_in_version_id = None
        finding.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(finding)
        return finding

    @staticmethod
    def reopen_finding(db: Session, finding_id: int) -> ReviewFinding:
        finding = db.query(ReviewFinding).filter(ReviewFinding.id == finding_id).first()
        if not finding:
            raise ValueError(f"Finding with ID {finding_id} not found.")
        finding.status = "Open"
        finding.resolved_at = None
        finding.resolved_in_version_id = None
        finding.ignored_reason = None
        finding.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(finding)
        return finding
