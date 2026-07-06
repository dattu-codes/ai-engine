import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.projects.models.project_models import ReviewFinding, ProjectVersion, Analysis, Project
from app.projects.services.activity_service import ActivityService

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

                # Calculate dependency risk context (v2.2)
                try:
                    from app.projects.services.impact_analysis_service import ImpactAnalysisService
                    from app.projects.services.review_pipeline_services import ModuleGrouper
                    impact = ImpactAnalysisService.analyze_impact(db, project_id, file_path)
                    
                    matched_finding.dependency_chain = json.dumps(impact["dependent_files"])
                    matched_finding.downstream_risk = impact["risk_rating"]
                    
                    imp_mods = set()
                    for fp in impact["dependent_files"]:
                        _, mod, _ = ModuleGrouper.get_priority_and_module(fp)
                        if mod:
                            imp_mods.add(mod)
                    matched_finding.impacted_modules = json.dumps(list(imp_mods))
                except Exception as de:
                    print(f"Error compiling finding dependency risk: {de}")

                # Reopen finding if it was resolved or ignored
                if matched_finding.status in ["Resolved", "Ignored"]:
                    matched_finding.status = "Open"
                    matched_finding.resolved_at = None
                    matched_finding.resolved_in_version_id = None

                matched_db_finding_ids.add(matched_finding.id)
                synced_findings.append(matched_finding)
            else:
                # Calculate dependency risk context (v2.2)
                dep_chain = "[]"
                down_risk = "Low Risk"
                imp_modules = "[]"
                try:
                    from app.projects.services.impact_analysis_service import ImpactAnalysisService
                    from app.projects.services.review_pipeline_services import ModuleGrouper
                    impact = ImpactAnalysisService.analyze_impact(db, project_id, file_path)
                    dep_chain = json.dumps(impact["dependent_files"])
                    down_risk = impact["risk_rating"]
                    
                    imp_mods = set()
                    for fp in impact["dependent_files"]:
                        _, mod, _ = ModuleGrouper.get_priority_and_module(fp)
                        if mod:
                            imp_mods.add(mod)
                    imp_modules = json.dumps(list(imp_mods))
                except Exception as de:
                    print(f"Error compiling new finding dependency risk: {de}")

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
                    impacted_modules=imp_modules,
                    dependency_chain=dep_chain,
                    downstream_risk=down_risk,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(new_finding)
                db.commit()
                db.refresh(new_finding)
                
                # Log Activity
                project_obj = db.query(Project).filter(Project.id == project_id).first()
                ActivityService.log_activity(
                    db=db,
                    workspace_id=project_obj.workspace_id if project_obj else None,
                    project_id=project_id,
                    user_id=None,
                    activity_type="Finding Created",
                    entity_type="finding",
                    entity_id=new_finding.id,
                    description=f"New finding #{new_finding.id} discovered in {file_path}: '{title}'."
                )

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
        project_obj = db.query(Project).filter(Project.id == project_id).first()
        for f in findings_to_resolve:
            f.status = "Resolved"
            f.resolved_at = datetime.utcnow()
            # Try to associate with the current latest project version if available
            latest_version = db.query(ProjectVersion).filter(
                ProjectVersion.project_id == project_id
            ).order_by(ProjectVersion.version_number.desc()).first()
            if latest_version:
                f.resolved_in_version_id = latest_version.id
            
            # Log Activity
            ActivityService.log_activity(
                db=db,
                workspace_id=project_obj.workspace_id if project_obj else None,
                project_id=project_id,
                user_id=None,
                activity_type="Finding Resolved",
                entity_type="finding",
                entity_id=f.id,
                description=f"Finding #{f.id} in {f.file_path} was automatically resolved.",
                metadata_json={"resolved_by": "sync"}
            )

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
    def update_finding_status(db: Session, finding_id: int, status: str, operator_id: Optional[int] = None) -> ReviewFinding:
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

        if operator_id:
            project = db.query(Project).filter(Project.id == finding.project_id).first()
            ActivityService.log_activity(
                db=db,
                workspace_id=project.workspace_id if project else None,
                project_id=finding.project_id,
                user_id=operator_id,
                activity_type="Finding Resolved" if status == "Resolved" else ("Finding Ignored" if status == "Ignored" else "Finding Reopened"),
                entity_type="finding",
                entity_id=finding.id,
                description=f"Finding #{finding.id} status was changed to {status}.",
                metadata_json={"status": status}
            )

        return finding

    @staticmethod
    def assign_finding(db: Session, finding_id: int, username: Optional[str], operator_id: int, due_date: Optional[datetime] = None) -> ReviewFinding:
        finding = db.query(ReviewFinding).filter(ReviewFinding.id == finding_id).first()
        if not finding:
            raise ValueError(f"Finding with ID {finding_id} not found.")
        
        finding.assigned_to = username
        finding.assigned_by = operator_id
        finding.assigned_at = datetime.utcnow() if username else None
        finding.due_date = due_date
        finding.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(finding)

        project = db.query(Project).filter(Project.id == finding.project_id).first()
        desc = f"Finding #{finding.id} was assigned to {username}." if username else f"Finding #{finding.id} was unassigned."
        ActivityService.log_activity(
            db=db,
            workspace_id=project.workspace_id if project else None,
            project_id=finding.project_id,
            user_id=operator_id,
            activity_type="Finding Assigned",
            entity_type="finding",
            entity_id=finding.id,
            description=desc,
            metadata_json={"assigned_to": username, "due_date": due_date.isoformat() if due_date else None}
        )

        return finding

    @staticmethod
    def ignore_finding(db: Session, finding_id: int, reason: Optional[str], operator_id: int) -> ReviewFinding:
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

        project = db.query(Project).filter(Project.id == finding.project_id).first()
        ActivityService.log_activity(
            db=db,
            workspace_id=project.workspace_id if project else None,
            project_id=finding.project_id,
            user_id=operator_id,
            activity_type="Finding Ignored",
            entity_type="finding",
            entity_id=finding.id,
            description=f"Finding #{finding.id} was ignored. Reason: {reason or 'None'}.",
            metadata_json={"reason": reason}
        )

        return finding

    @staticmethod
    def reopen_finding(db: Session, finding_id: int, operator_id: int) -> ReviewFinding:
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

        project = db.query(Project).filter(Project.id == finding.project_id).first()
        ActivityService.log_activity(
            db=db,
            workspace_id=project.workspace_id if project else None,
            project_id=finding.project_id,
            user_id=operator_id,
            activity_type="Finding Reopened",
            entity_type="finding",
            entity_id=finding.id,
            description=f"Finding #{finding.id} was reopened.",
            metadata_json=None
        )

        return finding
