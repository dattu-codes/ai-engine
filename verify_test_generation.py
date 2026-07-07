import sys
import os
import json
import asyncio
from datetime import datetime

# Add workspace directory to python path
sys.path.append(r"c:\Users\datta\.gemini\antigravity-ide\scratch\ai-engine-intern")

from app.auth.database.connection import SessionLocal, Base, engine
from app.auth.models.auth_models import User
from app.projects.models.project_models import Project, ReviewFinding, FixExecution, ProjectVersion, ProjectVersionFile, TestExecution
from app.projects.services.ai_fix_center import AIFixCenter

async def main():
    print("Creating database tables if not exist...")
    Base.metadata.create_all(bind=engine)
    print("Initializing test database session...")
    db = SessionLocal()
    
    try:
        # Get or create user
        user = db.query(User).first()
        if not user:
            user = User(username="test_gen_verify_user", password_hash="dummy-hash", role="user")
            db.add(user)
            db.commit()
            db.refresh(user)

        # Get or create workspace
        from app.projects.models.project_models import Workspace
        workspace = db.query(Workspace).first()
        if not workspace:
            workspace = Workspace(name="Test Workspace", created_at=datetime.utcnow())
            db.add(workspace)
            db.commit()
            db.refresh(workspace)

        # 1. Create target dummy project
        print("Creating mock project...")
        proj = Project(
            user_id=user.id,
            workspace_id=workspace.id,
            name="Test Auto-Gen Verification Project",
            project_type="Python",
            framework="pytest",
            architecture="Monolithic",
            languages_distribution='{"python": 100.0}',
            dependencies_json='[]',
            total_lines=150,
            created_at=datetime.utcnow()
        )
        db.add(proj)
        db.commit()
        db.refresh(proj)
        print(f"Mock project created with ID: {proj.id}")

        # 2. Ingest baseline snapshot files
        print("Creating baseline version...")
        version = ProjectVersion(
            project_id=proj.id,
            version_number=1,
            created_at=datetime.utcnow(),
            summary="Baseline source files ingestion.",
            snapshot_metadata='{}'
        )
        db.add(version)
        db.commit()
        db.refresh(version)

        # Add target vulnerable source file
        vuln_content = """def dummy_eval_executor(user_input):
    # Vulnerable eval pattern
    eval(user_input)
    pass
"""
        vf = ProjectVersionFile(
            version_id=version.id,
            filename="vuln_auth.py",
            extension="py",
            size=len(vuln_content),
            language="Python",
            hash="dummy-sha256-hash",
            content=vuln_content
        )
        db.add(vf)
        db.commit()
        print("Vulnerable source file added to baseline version 1.")

        # 3. Create simulated finding
        print("Creating Review Finding for vuln_auth.py eval injection...")
        finding = ReviewFinding(
            project_id=proj.id,
            analysis_id=1,
            title="Arbitrary Code Execution via Eval",
            description="Eval executes arbitrary code, causing severe security issues.",
            recommendation="Replace eval with secure parsing logic.",
            confidence=0.9,
            severity="Critical",
            category="Security",
            file_path="vuln_auth.py",
            line_number=3,
            status="Open",
            created_at=datetime.utcnow()
        )
        db.add(finding)
        db.commit()
        db.refresh(finding)
        print(f"Review Finding created with ID: {finding.id}")

        # 4. Run AI Fix generation
        print("Executing AI Fix generation workflow...")
        fix_exec = await AIFixCenter.generate_fix(db, finding.id)
        print(f"FixExecution created with ID: {fix_exec.id} in state: {fix_exec.status}")
        
        # Assertions
        assert fix_exec.status == "Waiting Approval"
        assert fix_exec.fix_plan_json is not None
        assert fix_exec.patch_summary is not None
        
        print(f"Confidence score: {fix_exec.confidence_score}")
        print(f"Patch Preview Diff:\n{fix_exec.patch_summary}")

        # 5. Approve fix
        print("Approving generated patch fix...")
        # Since we are in offline simulator mode, AIFixCenter will use verification mock
        completed_fix = await AIFixCenter.approve_fix(db, fix_exec.id)
        print(f"Approved FixExecution status: {completed_fix.status}")
        if completed_fix.status == "Failed":
            print(f"Failure reason: {completed_fix.failure_reason}")
        
        # Assertions
        assert completed_fix.status == "Completed"
        
        # 6. Verify automated test execution records
        print("Checking generated test execution database records...")
        test_runs = db.query(TestExecution).filter(TestExecution.project_id == proj.id).all()
        print(f"Found {len(test_runs)} test executions for project.")
        
        assert len(test_runs) > 0
        latest_run = test_runs[0]
        
        print("\n=== Test Execution Metrics ===")
        print(f"ID: {latest_run.id}")
        print(f"Status: {latest_run.status}")
        print(f"Framework: {latest_run.framework}")
        print(f"Total Tests: {latest_run.total_tests}")
        print(f"Passed Tests: {latest_run.passed_tests}")
        print(f"Failed Tests: {latest_run.failed_tests}")
        print(f"Skipped Tests: {latest_run.skipped_tests}")
        print(f"Coverage: {latest_run.coverage_percentage}%")
        print(f"Execution Time: {latest_run.execution_time}s")
        print("=== Test Runner Log Output ===")
        print(latest_run.execution_log)
        
        # Clean up database mock records
        print("Cleaning up test execution records...")
        db.delete(latest_run)
        db.delete(completed_fix)
        db.delete(finding)
        db.delete(vf)
        db.delete(version)
        db.delete(proj)
        db.commit()
        print("Cleanup successful. End-to-end Verification PASSED!")

    except Exception as e:
        print(f"Verification FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
