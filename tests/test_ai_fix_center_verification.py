import ast
import pytest
from app.services.ai import MockAISimulator
from app.projects.services.code_analyzer import PythonASTVisitor

SAMPLE_CODE = """import pickle
def run(user_input):
    eval(user_input)
    pickle.loads(user_input)
    try:
        pass
    except:
        pass
"""

def test_detection_eval_pickle_and_empty_except():
    """Test 1: eval + pickle + empty except are all detected with high/medium severity."""
    # 1. Via PythonASTVisitor directly
    tree = ast.parse(SAMPLE_CODE)
    visitor = PythonASTVisitor()
    visitor.visit(tree)
    vuln_descs = [v["description"].lower() for v in visitor.vulnerabilities]
    assert any("eval" in d for d in vuln_descs), "eval vulnerability not detected by AST visitor"
    assert any("pickle" in d for d in vuln_descs), "pickle vulnerability not detected by AST visitor"
    
    # 2. Via MockAISimulator.detect_issues (which is called by the live review path)
    issues = MockAISimulator.detect_issues(SAMPLE_CODE)
    descriptions = [iss["description"].lower() for iss in issues]
    
    eval_detected = any("eval" in d for d in descriptions)
    pickle_detected = any("pickle" in d for d in descriptions)
    except_detected = any("except" in d for d in descriptions)
    
    assert eval_detected, "eval issue not detected in MockAISimulator.detect_issues"
    assert pickle_detected, "pickle issue not detected in MockAISimulator.detect_issues"
    assert except_detected, "empty except issue not detected in MockAISimulator.detect_issues"
    
    # Check severity
    eval_issue = next(iss for iss in issues if "eval" in iss["description"].lower())
    pickle_issue = next(iss for iss in issues if "pickle" in iss["description"].lower())
    assert eval_issue["severity"].lower() == "high", f"eval severity should be high, got {eval_issue['severity']}"
    assert pickle_issue["severity"].lower() == "high", f"pickle severity should be high, got {pickle_issue['severity']}"


def test_patch_touches_only_except_block_try_body_unchanged():
    """Test 2: patch touches only the except block; the try body pass is completely untouched."""
    issues = MockAISimulator.detect_issues(SAMPLE_CODE)
    patch_result = MockAISimulator.suggest_improvements(SAMPLE_CODE, issues)
    patched_code = patch_result["refactored_code"]
    
    # The try block body must remain 'pass'
    assert "    try:\n        pass" in patched_code, "try body 'pass' was modified or overwritten!"
    
    # The except line must be expanded to catch Exception as e
    assert "except Exception as e:" in patched_code, "except was not expanded to 'except Exception as e:'"
    
    # The except body must be logging, not pass
    assert 'logging.warning("An error occurred: %s", e)' in patched_code
    
    # The original eval and pickle lines must remain untouched
    assert "    eval(user_input)" in patched_code
    assert "    pickle.loads(user_input)" in patched_code


def test_remaining_findings_include_eval_and_pickle():
    """Test 3: after patch, eval and pickle are still reported as remaining (not claimed as resolved)."""
    issues = MockAISimulator.detect_issues(SAMPLE_CODE)
    patch_result = MockAISimulator.suggest_improvements(SAMPLE_CODE, issues)
    patched_code = patch_result["refactored_code"]
    
    verification = MockAISimulator.verify_patch(SAMPLE_CODE, patched_code)
    
    resolved = verification["resolved"]
    remaining = verification["remaining"]
    
    resolved_descs = [r["description"].lower() for r in resolved]
    remaining_descs = [r["description"].lower() for r in remaining]
    
    # Empty except was resolved
    assert any("except" in d for d in resolved_descs), "except finding not in resolved list"
    assert not any("eval" in d for d in resolved_descs), "eval falsely claimed as resolved!"
    assert not any("pickle" in d for d in resolved_descs), "pickle falsely claimed as resolved!"
    
    # eval and pickle must remain
    assert any("eval" in d for d in remaining_descs), "eval not reported in remaining findings"
    assert any("pickle" in d for d in remaining_descs), "pickle not reported in remaining findings"
    
    # Check line numbers and annotations
    eval_rem = next(r for r in remaining if "eval" in r["description"].lower())
    pickle_rem = next(r for r in remaining if "pickle" in r["description"].lower())
    assert eval_rem.get("original_location") == "Line 3"
    assert "in patched code" in eval_rem.get("patched_location", "")
    assert pickle_rem.get("original_location") == "Line 4"
    assert "in patched code" in pickle_rem.get("patched_location", "")


def test_no_duplicate_bullets_and_syntax_ok():
    """Test 4: no duplicate bullets in improvements list; syntax_ok is True on patched code."""
    issues = MockAISimulator.detect_issues(SAMPLE_CODE)
    patch_result = MockAISimulator.suggest_improvements(SAMPLE_CODE, issues)
    improvements = patch_result["improvements"]
    
    # Check for duplicate bullets
    assert len(improvements) == len(set(improvements)), f"Duplicate improvements bullets found: {improvements}"
    
    # Check that false claims like docstring aren't in improvements
    assert not any("docstring" in imp.lower() for imp in improvements), "False docstring improvement claimed"
    assert not any("eval" in imp.lower() for imp in improvements), "False eval fix improvement claimed"
    
    # Check syntax verification
    verification = MockAISimulator.verify_patch(SAMPLE_CODE, patch_result["refactored_code"])
    assert verification["syntax_ok"] is True, "Patched code failed syntax compilation / parsing"
    
    # Verify compile() and ast.parse() pass
    compile(patch_result["refactored_code"], "<test>", "exec")
    ast.parse(patch_result["refactored_code"])
