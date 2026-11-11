import os
import sys
import time
import subprocess

TEST_SCRIPTS = [
    ("Auth & Security Core", "verify_auth.py"),
    ("Deployment & Health Readiness", "verify_deployment_readiness.py"),
    ("Public SaaS API & RBAC", "verify_public_saas.py"),
    ("Project Ingestion & Zip-Slip Protection", "verify_projects.py"),
    ("AST Static Analysis & Metrics", "verify_analyzers.py"),
    ("Code Intelligence & Frameworks", "verify_intelligence.py"),
    ("AI Review Analysis Core", "verify_analysis.py"),
    ("Modular Review Pipeline (6 Stages)", "verify_review_pipeline.py"),
    ("Review Quality Findings Lifecycle", "verify_review_findings.py"),
    ("Multi-LLM Routing & Fallback", "verify_multi_llm.py"),
    ("Semantic Graph & Impact Analysis", "verify_semantic_graph.py"),
    ("Repository Health & Maturity Insights", "verify_repository_insights.py"),
    ("AI Fix Center & Self-Healing", "verify_ai_fix_center.py"),
    ("Snapshot Versioning & Revert", "verify_versioning.py"),
    ("Grounded RAG Project Assistant", "verify_project_chat.py"),
    ("Test Generation & Sandboxed Runner", "verify_test_generation.py"),
    ("GitHub Repository Integration", "verify_github.py"),
    ("Pull Request Reviews & CI/CD Audits", "verify_pull_requests.py"),
    ("Workspaces & Team Collaboration", "verify_team_collaboration.py"),
]

def main():
    print("=" * 80)
    print("   AI ENGINE — MASTER INTEGRATION VERIFICATION BATTERY")
    print("=" * 80)
    print(f"Total Suites to Execute: {len(TEST_SCRIPTS)}\n")

    results = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    start_all = time.time()

    for idx, (suite_name, script_name) in enumerate(TEST_SCRIPTS, 1):
        script_path = os.path.join(base_dir, script_name)
        print(f"[{idx:02d}/{len(TEST_SCRIPTS):02d}] Running {suite_name} ({script_name})...", end="", flush=True)
        t0 = time.time()
        
        proc = subprocess.run(
            [sys.executable, script_path],
            cwd=base_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        duration = round(time.time() - t0, 2)

        if proc.returncode == 0:
            print(f" -> [PASSED] ({duration}s)")
            results.append((suite_name, script_name, "PASSED", duration, ""))
        else:
            print(f" -> [FAILED] ({duration}s)")
            error_preview = (proc.stderr or proc.stdout)[-500:]
            results.append((suite_name, script_name, "FAILED", duration, error_preview))

    total_duration = round(time.time() - start_all, 2)
    passed_count = sum(1 for r in results if r[2] == "PASSED")
    failed_count = len(results) - passed_count

    print("\n" + "=" * 80)
    print("   VERIFICATION BATTERY SUMMARY SCORECARD")
    print("=" * 80)
    print(f"{'#':<4} {'Suite Name':<42} {'Script':<30} {'Status':<8} {'Time'}")
    print("-" * 90)

    for idx, (suite, script, status, duration, _) in enumerate(results, 1):
        print(f"{idx:<4} {suite:<42} {script:<30} {status:<8} {duration}s")

    print("=" * 90)
    print(f"Passed: {passed_count}/{len(results)} | Failed: {failed_count} | Total Elapsed: {total_duration}s")
    print("=" * 90)

    if failed_count > 0:
        print("\n--- Failure Details ---")
        for suite, script, status, _, err in results:
            if status == "FAILED":
                print(f"\n[FAIL] {suite} ({script}):\n{err}")
        sys.exit(1)
    else:
        print("\nALL 19 VERIFICATION SUITES EXECUTED WITH ZERO ERRORS. PLATFORM 100% HEALTHY.")
        sys.exit(0)

if __name__ == "__main__":
    main()
