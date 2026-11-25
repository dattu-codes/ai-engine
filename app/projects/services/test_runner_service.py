import os
import shutil
import subprocess
import time
import re
import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.projects.models.project_models import TestExecution, ProjectVersionFile, Project
from app.projects.services.activity_service import ActivityService
from app.projects.services.coverage_service import CoverageService
from app.projects.services.regression_service import RegressionService

class TestRunnerService:
    @staticmethod
    async def execute_tests(db: Session, test_execution_id: int) -> TestExecution:
        """
        Executes the generated tests for a TestExecution run.
        For Python, writes snapshot files to disk and runs pytest in a subprocess.
        For other languages, generates high-fidelity simulated test runner execution logs.
        """
        test_exec = db.query(TestExecution).filter(TestExecution.id == test_execution_id).first()
        if not test_exec:
            raise ValueError(f"TestExecution {test_execution_id} not found.")

        project = db.query(Project).filter(Project.id == test_exec.project_id).first()
        test_exec.status = "Running"
        db.commit()

        start_time = time.time()
        
        # Load version files from DB
        vfs = db.query(ProjectVersionFile).filter(ProjectVersionFile.version_id == test_exec.version_id).all()
        language = test_exec.language or "Python"

        # Real Python test execution via isolated temporary workspace
        if language.lower() == "python":
            temp_dir = os.path.abspath(os.path.join(os.getcwd(), f"temp_run_{test_execution_id}"))
            os.makedirs(temp_dir, exist_ok=True)
            
            try:
                # Write files physically to temp folder with strict boundary verification
                abs_temp_dir = os.path.abspath(temp_dir)
                for vf in vfs:
                    abs_file_path = os.path.abspath(os.path.join(abs_temp_dir, vf.filename))
                    if not (abs_file_path.startswith(abs_temp_dir + os.sep) or abs_file_path == abs_temp_dir):
                        raise ValueError(f"Security: Path traversal attempt blocked for file '{vf.filename}'")
                    os.makedirs(os.path.dirname(abs_file_path), exist_ok=True)
                    with open(abs_file_path, "w", encoding="utf-8") as f:
                        f.write(vf.content or "")
                
                # Use current Python executable to run pytest
                import sys
                python_bin = sys.executable
                cmd = [python_bin, "-m", "pytest", "-v", "--tb=short"]
                
                result = subprocess.run(
                    cmd,
                    cwd=abs_temp_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30
                )
                
                execution_log = (result.stdout or "") + "\n" + (result.stderr or "")
                
                # Parse real pytest results from execution output
                passed = 0
                failed = 0
                skipped = 0
                
                passed_match = re.search(r"(\d+)\s+passed", execution_log)
                failed_match = re.search(r"(\d+)\s+failed", execution_log)
                skipped_match = re.search(r"(\d+)\s+skipped", execution_log)
                
                if passed_match:
                    passed = int(passed_match.group(1))
                if failed_match:
                    failed = int(failed_match.group(1))
                if skipped_match:
                    skipped = int(skipped_match.group(1))
                
                total = passed + failed + skipped
                
                # If no tests were collected, status must be 'No tests found', never 'passed'
                if total == 0:
                    test_exec.total_tests = 0
                    test_exec.passed_tests = 0
                    test_exec.failed_tests = 0
                    test_exec.skipped_tests = 0
                    test_exec.status = "No tests found"
                    test_exec.coverage_percentage = None
                else:
                    test_exec.total_tests = total
                    test_exec.passed_tests = passed
                    test_exec.failed_tests = failed
                    test_exec.skipped_tests = skipped
                    test_exec.status = "Completed" if failed == 0 else "Failed"
                    
                    # Coverage must come from a real coverage run or show N/A (None). No default numbers.
                    real_coverage_pct = None
                    try:
                        cov_res = subprocess.run(
                            [python_bin, "-m", "coverage", "run", "-m", "pytest", "-v"],
                            cwd=abs_temp_dir,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            timeout=20
                        )
                        if cov_res.returncode in (0, 1):
                            cov_json_res = subprocess.run(
                                [python_bin, "-m", "coverage", "json", "-o", "coverage.json"],
                                cwd=abs_temp_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                timeout=10
                            )
                            cov_path = os.path.join(abs_temp_dir, "coverage.json")
                            if os.path.exists(cov_path):
                                with open(cov_path, "r", encoding="utf-8") as cf:
                                    cov_data = json.load(cf)
                                    if "totals" in cov_data and "percent_covered" in cov_data["totals"]:
                                        real_coverage_pct = round(float(cov_data["totals"]["percent_covered"]), 1)
                    except Exception:
                        real_coverage_pct = None
                    
                    test_exec.coverage_percentage = real_coverage_pct

                test_exec.execution_log = execution_log.strip()

            except subprocess.TimeoutExpired:
                test_exec.execution_log = "Test execution timed out after 30 seconds."
                test_exec.status = "Failed"
                test_exec.failed_tests = 1
                db.commit()
                return test_exec
            except Exception as e:
                test_exec.execution_log = f"Test execution failed: {str(e)}"
                test_exec.status = "Failed"
                db.commit()
                return test_exec
            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)

        # Non-Python Execution: Check for real runtime or report unconfigured cleanly
        else:
            runner_binary = None
            if language.lower() == "java":
                runner_binary = shutil.which("mvn") or shutil.which("gradle")
            elif language.lower() in ["javascript", "typescript"]:
                runner_binary = shutil.which("npm") or shutil.which("yarn")
            elif language.lower() == "go":
                runner_binary = shutil.which("go")

            if runner_binary:
                # Real build runner exists on host -> execute it
                temp_dir = os.path.abspath(os.path.join(os.getcwd(), f"temp_run_{test_execution_id}"))
                os.makedirs(temp_dir, exist_ok=True)
                try:
                    for vf in vfs:
                        p = os.path.abspath(os.path.join(temp_dir, vf.filename))
                        os.makedirs(os.path.dirname(p), exist_ok=True)
                        with open(p, "w", encoding="utf-8") as f:
                            f.write(vf.content or "")
                    
                    cmd = [runner_binary, "test"]
                    proc = subprocess.run(cmd, cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=45)
                    test_exec.execution_log = proc.stdout + "\n" + proc.stderr
                    test_exec.status = "Completed" if proc.returncode == 0 else "Failed"
                finally:
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
            else:
                # Honest notification without simulation: build tools not present on host
                test_exec.total_tests = 0
                test_exec.passed_tests = 0
                test_exec.failed_tests = 0
                test_exec.skipped_tests = 0
                test_exec.coverage_percentage = None
                test_exec.execution_log = (
                    f"Test runner for '{language}' skipped: Native toolchain (e.g. Maven, npm, or Go) "
                    f"is not installed on the host environment.\n"
                    f"Platform policy strictly forbids reporting simulated test results.\n"
                    f"To run {language} tests, install the toolchain or deploy via Docker."
                )
                test_exec.status = "No tests found"

        # Validate Regression
        regression_report = RegressionService.verify_behavior(db, test_exec)
        # If regression checks fail, update status
        
        test_exec.execution_time = time.time() - start_time
        if test_exec.total_tests == 0 or test_exec.status == "No tests found":
            test_exec.status = "No tests found"
        else:
            test_exec.status = "Completed" if test_exec.failed_tests == 0 else "Failed"
        db.commit()

        # Log Activity Run Completed
        if test_exec.status == "No tests found":
            activity_type = "Test Run (No Tests Found)"
        elif test_exec.status == "Completed":
            activity_type = "Test Run Completed"
        else:
            activity_type = "Test Run Failed"

        cov_str = f"{test_exec.coverage_percentage}%" if test_exec.coverage_percentage is not None else "N/A"
        ActivityService.log_activity(
            db=db,
            workspace_id=project.workspace_id,
            project_id=project.id,
            user_id=test_exec.version.created_by if test_exec.version else None,
            activity_type=activity_type,
            entity_type="test_execution",
            entity_id=test_exec.id,
            description=f"Automated tests run completed for version {test_exec.version.version_number if test_exec.version else 'N/A'}. Pass rate: {test_exec.passed_tests}/{test_exec.total_tests} ({cov_str} coverage)."
        )

        return test_exec
