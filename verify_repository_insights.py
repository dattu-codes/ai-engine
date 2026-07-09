import sys
import os
import json
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Setup path imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.auth.database.connection import Base, engine, SessionLocal
from app.projects.models.project_models import (
    Project, Analysis, AnalysisFile, Report, ReviewFinding, 
    SemanticNode, SemanticEdge, TestExecution, RepositoryInsight, RepositoryInsightHistory,
    ProjectVersion
)
from app.projects.services.semantic_graph_service import SemanticGraphService
from app.projects.services.code_analyzer import CodeAnalyzerService
from app.projects.services.repository_insights_service import RepositoryInsightsService
from app.projects.services.project_chat_service import ProjectChatService
from app.main import app

def run_tests():
    print("======================================================================")
    print("STARTING AI ENGINE v2.7: REPOSITORY INSIGHTS VERIFICATION SUITE")
    print("======================================================================")
    
    # 1. Initialize DB tables
    db = SessionLocal()
    try:
        # Create a mock user if not exists
        from app.auth.models.auth_models import User
        mock_user = db.query(User).filter(User.username == "insights_tester").first()
        if not mock_user:
            mock_user = User(username="insights_tester", hashed_password="hash", role="developer")
            db.add(mock_user)
            db.commit()
            db.refresh(mock_user)
            
        # Create project
        project = Project(
            user_id=mock_user.id,
            name="Mock Go Service",
            project_type="Go",
            framework="None",
            architecture="Monolith",
            total_lines=150,
            has_intelligence=True,
            has_semantic_graph=True
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        print(f"[x] Created project ID: {project.id}")

        # Create Analysis
        analysis = Analysis(
            project_id=project.id,
            status="completed",
            source_type="zip",
            created_by=mock_user.id
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        # Create Version
        version = ProjectVersion(
            project_id=project.id,
            version_number=1,
            summary="Initial version",
            source_analysis_id=analysis.id
        )
        db.add(version)
        db.commit()
        db.refresh(version)

        # 2. Test Go file AST semantic parsing
        mock_go_content = """package main

import (
    "database/sql"
    "fmt"
)

type User struct {
    ID   int
    Name string
}

type Service interface {
    GetUser(id int) (*User, error)
}

func (u *User) GetName() string {
    return u.Name
}

func QueryUser(db *sql.DB, id string) {
    // SQL injection risk
    q := "SELECT * FROM users WHERE id = " + id
    rows, _ := db.Query(q)
    _ = rows
}
"""
        # Save file to analysis
        af = AnalysisFile(
            analysis_id=analysis.id,
            filename="main.go",
            extension=".go",
            size=len(mock_go_content),
            language="Go",
            hash="hash123",
            content=mock_go_content
        )
        db.add(af)
        db.commit()
        
        symbol_map = {}
        # Execute parser
        SemanticGraphService._parse_go_nodes(mock_go_content, "main.go", project.id, db, symbol_map)
        
        # Verify nodes generated
        nodes = db.query(SemanticNode).filter(SemanticNode.project_id == project.id).all()
        assert len(nodes) > 0, "Go parser failed to extract semantic nodes!"
        print(f"[x] Successfully extracted {len(nodes)} Go semantic nodes (structs, methods, interfaces, functions)")
        
        # Execute edge builder
        file_map = {"main.go": 1}
        SemanticGraphService._parse_go_edges(mock_go_content, "main.go", project.id, db, 1, symbol_map, file_map)
        print("[x] Successfully generated Go Semantic Graph dependency edges")

        # 3. Test Go static code analysis (Regex code analyzer)
        vulns = CodeAnalyzerService._regex_security(mock_go_content, "main.go", "go")
        
        # Assert specific vulnerabilities detected
        categories = [v["category"] for v in vulns]
        titles = [v["title"] for v in vulns]
        
        assert "Bug" in categories, "Failed to identify blank identifier error ignores!"
        assert "Security" in categories, "Failed to flag string concatenation SQL injection!"
        print(f"[x] Successfully detected Go-specific vulnerabilities: {', '.join(titles)}")

        # Save findings in database
        for v in vulns:
            finding = ReviewFinding(
                project_id=project.id,
                analysis_id=analysis.id,
                file_path="main.go",
                line_number=v["line"],
                category=v["category"],
                severity=v["severity"],
                description=v["description"],
                recommendation=v["recommendation"],
                confidence=0.9,
                status="Open",
                title=v["title"]
            )
            db.add(finding)
        db.commit()

        # 4. Test Repository Insights Service calculations
        insight = RepositoryInsightsService.generate_insight(db, project.id)
        
        assert insight.repository_score > 0, "Insight scoring calculated zero overall score!"
        assert insight.technical_debt_score in ["Very Low", "Low", "Moderate", "High", "Critical"], "Invalid Technical Debt level calculated!"
        assert insight.engineering_maturity in ["Starter", "Growing", "Intermediate", "Production Candidate", "Production Ready", "Enterprise Ready"], "Invalid engineering maturity level calculated!"
        
        print("[x] RepositoryInsightsService score evaluation completed successfully:")
        print(f"  - Overall Score: {insight.repository_score}")
        print(f"  - Architecture Score: {insight.architecture_score}")
        print(f"  - Security Score: {insight.security_score}")
        print(f"  - Technical Debt Rating: {insight.technical_debt_score}")
        print(f"  - Engineering Maturity Level: {insight.engineering_maturity}")
        
        roadmap = json.loads(insight.roadmap_json)
        assert len(roadmap) > 0, "Maturity roadmap recommendations list was empty!"
        print(f"[x] Successfully compiled {len(roadmap)} evolution roadmap recommendations")

        # 5. Verify Repository Score History Trend Tracking
        history = db.query(RepositoryInsightHistory).filter(
            RepositoryInsightHistory.project_id == project.id
        ).all()
        assert len(history) == 1, "Failed to insert score snapshot record into RepositoryInsightHistory!"
        print("[x] Score history tracking verified successfully")

        # 6. Test FastAPI Router endpoints using TestClient
        client = TestClient(app)
        
        # Get mock user token for authentication
        from app.auth.services.auth_service import AuthService
        access_token, _, _, _ = AuthService.create_jwt_pair(mock_user.id, mock_user.role)
        headers = {"Authorization": f"Bearer {access_token}"}
        
        endpoints = [
            (f"/projects/{project.id}/repository-insights", 200),
            (f"/projects/{project.id}/repository-score", 200),
            (f"/projects/{project.id}/repository-roadmap", 200),
            (f"/projects/{project.id}/repository-strengths", 200),
            (f"/projects/{project.id}/repository-weaknesses", 200),
            (f"/projects/{project.id}/repository-history", 200),
            (f"/projects/{project.id}/engineering-maturity", 200),
            (f"/projects/{project.id}/technical-debt", 200),
        ]
        
        for url, expected_status in endpoints:
            response = client.get(url, headers=headers)
            assert response.status_code == expected_status, f"Endpoint {url} failed with status {response.status_code}!"
        print("[x] All REST API Repository Insights routes responded with status HTTP 200 (Success)")

        # 7. Test Chat Prompt integration context
        async def mock_chat():
            context_generator = ProjectChatService.chat_stream(
                db=db,
                project_id=project.id,
                user_query="What is my biggest weakness and roadmap recommended steps?",
                api_key=None,
                user_id=mock_user.id
            )
            # Fetch prompt parts via internals or verify flow runs without exception
            async for token in context_generator:
                pass
        
        # Run async test safely
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(mock_chat())
        print("[x] Project Chat prompt integration context verified successfully")

        print("======================================================================")
        print("ALL VERIFICATION SUITE TESTS COMPLETED SUCCESSFULLY!")
        print("======================================================================")
        
    finally:
        # Cleanup test data to prevent database pollution
        try:
            db.query(RepositoryInsightHistory).filter(RepositoryInsightHistory.project_id == project.id).delete()
            db.query(RepositoryInsight).filter(RepositoryInsight.project_id == project.id).delete()
            db.query(ReviewFinding).filter(ReviewFinding.project_id == project.id).delete()
            db.query(SemanticEdge).filter(SemanticEdge.project_id == project.id).delete()
            db.query(SemanticNode).filter(SemanticNode.project_id == project.id).delete()
            db.query(AnalysisFile).filter(AnalysisFile.analysis_id == analysis.id).delete()
            db.query(ProjectVersion).filter(ProjectVersion.project_id == project.id).delete()
            db.query(Analysis).filter(Analysis.project_id == project.id).delete()
            db.query(Project).filter(Project.id == project.id).delete()
            db.commit()
        except Exception:
            pass
        db.close()

if __name__ == "__main__":
    run_tests()
