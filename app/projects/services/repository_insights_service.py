import json
import re
from datetime import datetime
from sqlalchemy.orm import Session
from app.projects.models.project_models import (
    Project, Analysis, Report, ReviewFinding, 
    SemanticNode, SemanticEdge, TestExecution, 
    RepositoryInsight, RepositoryInsightHistory
)
from app.projects.services.diagnostics_service import DiagnosticsService

class RepositoryInsightsService:
    @staticmethod
    def generate_insight(db: Session, project_id: int) -> RepositoryInsight:
        # Fetch project
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project with ID {project_id} not found")

        # Fetch latest analysis
        latest_analysis = db.query(Analysis).filter(
            Analysis.project_id == project_id,
            Analysis.status == "completed"
        ).order_by(Analysis.created_at.desc()).first()

        # 1. Architecture Score (20%)
        architecture_score = 90
        try:
            edges = db.query(SemanticEdge).filter(
                SemanticEdge.project_id == project_id
            ).all()
            imports_count = sum(1 for e in edges if e.relationship == "IMPORTS")
            depends_count = sum(1 for e in edges if e.relationship == "DEPENDS_ON")
            
            if imports_count > 50:
                architecture_score -= 10
            if depends_count > 30:
                architecture_score -= 5
                
            edge_pairs = set()
            cycles = 0
            for e in edges:
                edge_pairs.add((e.source_node_id, e.target_node_id))
                if (e.target_node_id, e.source_node_id) in edge_pairs:
                    cycles += 1
            if cycles > 0:
                architecture_score -= min(30, cycles * 8)
        except Exception:
            pass
        architecture_score = max(30, min(100, architecture_score))

        # 2. Security Score (20%)
        security_score = 100
        try:
            findings = db.query(ReviewFinding).filter(
                ReviewFinding.project_id == project_id,
                ReviewFinding.status == "Open"
            ).all()
            for f in findings:
                sev = (f.severity or "medium").lower()
                if sev == "critical":
                    security_score -= 20
                elif sev == "high":
                    security_score -= 15
                elif sev == "medium":
                    security_score -= 10
                else:
                    security_score -= 5
        except Exception:
            pass
        security_score = max(20, min(100, security_score))

        # 3. Testing Score (20%)
        testing_score = 50
        try:
            latest_test = db.query(TestExecution).filter(
                TestExecution.project_id == project_id
            ).order_by(TestExecution.created_at.desc()).first()
            if latest_test and latest_test.total_tests > 0:
                pass_rate = latest_test.passed_tests / latest_test.total_tests
                testing_score = int(pass_rate * 70 + (latest_test.coverage_percentage or 0.0) * 0.3)
            elif latest_test:
                testing_score = int(latest_test.coverage_percentage or 50)
        except Exception:
            pass
        testing_score = max(20, min(100, testing_score))

        # 4. Deployment Score (15%)
        deployment_score = 90
        try:
            diag = DiagnosticsService.run_diagnostics(db)
            if diag.get("status") == "FAIL":
                deployment_score = 50
            else:
                warnings_count = len(diag.get("warnings", []))
                deployment_score -= min(40, warnings_count * 10)
        except Exception:
            pass
        deployment_score = max(30, min(100, deployment_score))

        # 5. Maintainability Score (15%)
        maintainability_score = 85
        try:
            if latest_analysis and latest_analysis.score:
                maintainability_score = int(latest_analysis.score * 0.8 + 20)
        except Exception:
            pass
        maintainability_score = max(30, min(100, maintainability_score))

        # 6. Documentation Score (10%)
        documentation_score = 75
        try:
            from app.projects.models.project_models import ProjectVersion, ProjectVersionFile
            latest_ver = db.query(ProjectVersion).filter(
                ProjectVersion.project_id == project_id
            ).order_by(ProjectVersion.version_number.desc()).first()
            if latest_ver:
                v_files = db.query(ProjectVersionFile).filter(
                    ProjectVersionFile.version_id == latest_ver.id
                ).all()
                total_lines = 0
                comment_lines = 0
                has_readme = False
                for vf in v_files:
                    if vf.filename.lower().endswith("readme.md"):
                        has_readme = True
                    content = vf.content or ""
                    total_lines += len(content.splitlines())
                    comment_lines += len(re.findall(r'(?://|#|/\*)', content))
                
                doc_ratio = comment_lines / max(1, total_lines)
                documentation_score = int(doc_ratio * 200 + (50 if has_readme else 30))
        except Exception:
            pass
        documentation_score = max(30, min(100, documentation_score))

        # Overall Repository Score
        repository_score = int(
            architecture_score * 0.20 +
            security_score * 0.20 +
            testing_score * 0.20 +
            deployment_score * 0.15 +
            maintainability_score * 0.15 +
            documentation_score * 0.10
        )

        # Technical Debt Score
        if repository_score >= 90:
            technical_debt_score = "Very Low"
        elif repository_score >= 80:
            technical_debt_score = "Low"
        elif repository_score >= 70:
            technical_debt_score = "Moderate"
        elif repository_score >= 55:
            technical_debt_score = "High"
        else:
            technical_debt_score = "Critical"

        # Engineering Maturity
        if repository_score >= 93:
            engineering_maturity = "Enterprise Ready"
        elif repository_score >= 88:
            engineering_maturity = "Production Ready"
        elif repository_score >= 80:
            engineering_maturity = "Production Candidate"
        elif repository_score >= 70:
            engineering_maturity = "Intermediate"
        elif repository_score >= 55:
            engineering_maturity = "Growing"
        else:
            engineering_maturity = "Starter"

        # Generate Strengths
        strengths = []
        if architecture_score >= 85:
            strengths.append("Modular Architecture")
        if security_score >= 85:
            strengths.append("Strong Security Baseline")
        if testing_score >= 80:
            strengths.append("Excellent Test Suite Coverage")
        if deployment_score >= 85:
            strengths.append("Reliable Deployment Configuration")
        if documentation_score >= 80:
            strengths.append("Well-documented Codebase")
            
        if not strengths:
            scores = [
                ("Modular Architecture", architecture_score),
                ("Strong Security Baseline", security_score),
                ("Test Coverage", testing_score),
                ("Deployment Configuration", deployment_score)
            ]
            strengths.append(max(scores, key=lambda x: x[1])[0])

        # Generate Weaknesses
        weaknesses = []
        if architecture_score < 75:
            weaknesses.append("High Architectural Coupling / Cycles")
        if security_score < 75:
            weaknesses.append("Open Security Vulnerabilities")
        if testing_score < 70:
            weaknesses.append("Low Test Coverage / Failing Tests")
        if deployment_score < 75:
            weaknesses.append("Degraded Deployment Diagnostics")
        if documentation_score < 70:
            weaknesses.append("Insufficient Code Documentation")

        if not weaknesses:
            scores = [
                ("Architectural Tight Coupling", architecture_score),
                ("Minor Security Gaps", security_score),
                ("Test Suitability", testing_score),
                ("Documentation Depth", documentation_score)
            ]
            weaknesses.append(min(scores, key=lambda x: x[1])[0])

        # Roadmap generation
        roadmap = []
        order = 1
        
        if security_score < 85:
            roadmap.append({
                "title": "Mitigate Security Findings",
                "description": "Fix open critical and high-priority vulnerabilities identified by AI code review scans.",
                "priority": "High" if security_score < 70 else "Medium",
                "effort": "Medium",
                "business_impact": "High",
                "estimated_time": "2 days",
                "dependency_requirements": "None",
                "recommended_order": order
            })
            order += 1
            
        if testing_score < 80:
            roadmap.append({
                "title": "Increase Test Coverage",
                "description": "Generate integration and edge-case unit test coverage using Test Center suite runner.",
                "priority": "High" if testing_score < 60 else "Medium",
                "effort": "High",
                "business_impact": "High",
                "estimated_time": "1 week",
                "dependency_requirements": "None",
                "recommended_order": order
            })
            order += 1
            
        if architecture_score < 80:
            roadmap.append({
                "title": "Optimize Architecture & Coupling",
                "description": "Decouple high-traffic components, resolve cyclic package imports, and introduce abstract interfaces.",
                "priority": "Medium",
                "effort": "High",
                "business_impact": "Medium",
                "estimated_time": "5 days",
                "dependency_requirements": "None",
                "recommended_order": order
            })
            order += 1

        if deployment_score < 85:
            roadmap.append({
                "title": "Resolve Deployment Warnings",
                "description": "Configure live caching database replicas and adjust connection pool limits to eliminate diagnostic telemetry warnings.",
                "priority": "High" if deployment_score < 60 else "Medium",
                "effort": "Low",
                "business_impact": "High",
                "estimated_time": "1 day",
                "dependency_requirements": "None",
                "recommended_order": order
            })
            order += 1

        if documentation_score < 75:
            roadmap.append({
                "title": "Improve API Documentation",
                "description": "Add inline comments and structured function-level docstrings for codebase components.",
                "priority": "Low",
                "effort": "Low",
                "business_impact": "Low",
                "estimated_time": "2 days",
                "dependency_requirements": "None",
                "recommended_order": order
            })
            order += 1

        if not roadmap:
            roadmap.append({
                "title": "Proactive Security Audit",
                "description": "Run routine dependency scanning and compliance audits for enterprise readiness.",
                "priority": "Low",
                "effort": "Low",
                "business_impact": "Medium",
                "estimated_time": "3 days",
                "dependency_requirements": "None",
                "recommended_order": 1
            })

        summary = (
            f"The repository is currently graded as {engineering_maturity} with an overall score of {repository_score}/100. "
            f"Key strengths include {', '.join(strengths[:2])}. "
            f"To scale towards production stability, we recommend prioritising {roadmap[0]['title']}."
        )

        insight = db.query(RepositoryInsight).filter(
            RepositoryInsight.project_id == project_id
        ).first()

        if not insight:
            insight = RepositoryInsight(
                project_id=project_id,
                repository_score=repository_score,
                architecture_score=architecture_score,
                security_score=security_score,
                testing_score=testing_score,
                deployment_score=deployment_score,
                maintainability_score=maintainability_score,
                documentation_score=documentation_score,
                technical_debt_score=technical_debt_score,
                engineering_maturity=engineering_maturity,
                strengths_json=json.dumps(strengths),
                weaknesses_json=json.dumps(weaknesses),
                roadmap_json=json.dumps(roadmap),
                summary=summary
            )
            db.add(insight)
        else:
            insight.repository_score = repository_score
            insight.architecture_score = architecture_score
            insight.security_score = security_score
            insight.testing_score = testing_score
            insight.deployment_score = deployment_score
            insight.maintainability_score = maintainability_score
            insight.documentation_score = documentation_score
            insight.technical_debt_score = technical_debt_score
            insight.engineering_maturity = engineering_maturity
            insight.strengths_json = json.dumps(strengths)
            insight.weaknesses_json = json.dumps(weaknesses)
            insight.roadmap_json = json.dumps(roadmap)
            insight.summary = summary
            insight.updated_at = datetime.utcnow()

        db.flush()

        from app.projects.models.project_models import ProjectVersion
        latest_ver = db.query(ProjectVersion).filter(
            ProjectVersion.project_id == project_id
        ).order_by(ProjectVersion.version_number.desc()).first()
        version_num = latest_ver.version_number if latest_ver else 1
        analysis_id = latest_analysis.id if latest_analysis else 1

        existing_history = db.query(RepositoryInsightHistory).filter(
            RepositoryInsightHistory.project_id == project_id,
            RepositoryInsightHistory.analysis_id == analysis_id
        ).first()

        if not existing_history:
            history_record = RepositoryInsightHistory(
                project_id=project_id,
                analysis_id=analysis_id,
                version_number=version_num,
                repository_score=repository_score
            )
            db.add(history_record)

        db.commit()
        return insight
