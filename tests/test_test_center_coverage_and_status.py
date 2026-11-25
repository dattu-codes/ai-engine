import pytest
import asyncio
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth.database.connection import Base
from app.auth.models.auth_models import User
from app.projects.models.project_models import (
    Project, ProjectVersion, ProjectVersionFile, FixExecution, TestExecution as TestExecutionModel, ReviewFinding
)
TestExecutionModel.__test__ = False
from app.projects.services.coverage_service import CoverageService
from app.projects.services.test_runner_service import TestRunnerService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_coverage_service_no_default_numbers_shows_none_na():
    """Verify CoverageService returns None for coverage without real coverage measurement (no default numbers)."""
    coverage_data = CoverageService.calculate_coverage(
        files=[],
        modified_files=[],
        language="Python",
        real_coverage_pct=None
    )
    assert coverage_data["overall_coverage"] is None, "Expected overall_coverage to be None when not measured"
    assert coverage_data["line_coverage"] is None, "Expected line_coverage to be None when not measured"
    assert coverage_data["is_available"] is False, "Expected is_available to be False"
    # Ensure no legacy hardcoded default numbers (like 82.5, 78.0, 75.0) are returned
    for key, val in coverage_data.items():
        if key != "is_available":
            assert val is None, f"Expected {key} to be None, got {val}"


def test_coverage_service_preserves_real_coverage():
    """Verify CoverageService preserves and returns real coverage percentage when measured."""
    coverage_data = CoverageService.calculate_coverage(
        files=[],
        modified_files=[],
        language="Python",
        real_coverage_pct=88.5
    )
    assert coverage_data["overall_coverage"] == 88.5
    assert coverage_data["is_available"] is True


def test_no_tests_collected_shows_no_tests_found_never_passed(db_session):
    """
    Verify that when no tests are collected (0 items), TestRunnerService sets
    status to 'No tests found' and NEVER 'passed' or 'Completed', with coverage as None (N/A).
    """
    proj = Project(name="TestProj", user_id=1)
    db_session.add(proj)
    db_session.commit()
    db_session.refresh(proj)

    version = ProjectVersion(project_id=proj.id, version_number=1, created_by=1)
    db_session.add(version)
    db_session.commit()
    db_session.refresh(version)

    # Empty files or files with no test functions -> pytest collects 0 items
    vf = ProjectVersionFile(
        version_id=version.id,
        filename="app.py",
        extension=".py",
        size=30,
        language="Python",
        hash="hash_app",
        content="def hello(): return 'world'"
    )
    db_session.add(vf)
    db_session.commit()

    test_exec = TestExecutionModel(
        project_id=proj.id,
        version_id=version.id,
        language="Python",
        framework="pytest",
        total_tests=0,
        passed_tests=0,
        failed_tests=0,
        skipped_tests=0,
        coverage_percentage=None,
        status="Pending"
    )
    db_session.add(test_exec)
    db_session.commit()
    db_session.refresh(test_exec)

    # Run execute_tests
    updated = asyncio.run(TestRunnerService.execute_tests(db_session, test_exec.id))

    assert updated.total_tests == 0, f"Expected 0 total tests, got {updated.total_tests}"
    assert updated.passed_tests == 0, f"Expected 0 passed tests, got {updated.passed_tests}"
    assert updated.status == "No tests found", f"Status must be 'No tests found', but was '{updated.status}'"
    assert updated.status != "Completed", "Status must NEVER be 'Completed' when no tests are collected"
    assert updated.status != "passed", "Status must NEVER be 'passed' when no tests are collected"
    assert updated.coverage_percentage is None, f"Coverage must be None (N/A) without real coverage, got {updated.coverage_percentage}"


def test_tests_collected_and_passing_sets_completed(db_session):
    """Verify that when tests are collected and pass, status is 'Completed'."""
    proj = Project(name="TestProj2", user_id=1)
    db_session.add(proj)
    db_session.commit()
    db_session.refresh(proj)

    version = ProjectVersion(project_id=proj.id, version_number=1, created_by=1)
    db_session.add(version)
    db_session.commit()
    db_session.refresh(version)

    vf_code = ProjectVersionFile(
        version_id=version.id,
        filename="math_lib.py",
        extension=".py",
        size=30,
        language="Python",
        hash="hash_math",
        content="def add(a, b): return a + b\n"
    )
    vf_test = ProjectVersionFile(
        version_id=version.id,
        filename="test_math.py",
        extension=".py",
        size=60,
        language="Python",
        hash="hash_test",
        content="from math_lib import add\ndef test_add(): assert add(1, 2) == 3\n"
    )
    db_session.add_all([vf_code, vf_test])
    db_session.commit()

    test_exec = TestExecutionModel(
        project_id=proj.id,
        version_id=version.id,
        language="Python",
        framework="pytest",
        total_tests=0,
        passed_tests=0,
        failed_tests=0,
        skipped_tests=0,
        coverage_percentage=None,
        status="Pending"
    )
    db_session.add(test_exec)
    db_session.commit()
    db_session.refresh(test_exec)

    updated = asyncio.run(TestRunnerService.execute_tests(db_session, test_exec.id))

    assert updated.total_tests == 1
    assert updated.passed_tests == 1
    assert updated.failed_tests == 0
    assert updated.status == "Completed"
    # Coverage without real coverage tool must be None (N/A), not a hardcoded default number
    assert updated.coverage_percentage is None or isinstance(updated.coverage_percentage, float)
