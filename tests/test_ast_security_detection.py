import ast
import pytest
from app.projects.services.code_analyzer import PythonASTVisitor
from app.services.ai import MockAISimulator
from app.projects.services.analysis_simulator import MockAnalysisSimulator

def test_ast_security_comment_eval_and_pickle_not_reported():
    """Comments mentioning eval() and pickle.loads() must NOT be reported."""
    code = """
# WARNING: Do not use eval(user_input) here
# Also avoid pickle.loads(raw_data) or pickle.load(fp)
def compute(x, y):
    return x + y
"""
    # 1. AST Visitor
    tree = ast.parse(code)
    visitor = PythonASTVisitor()
    visitor.visit(tree)
    assert len(visitor.vulnerabilities) == 0, f"AST visitor falsely reported comment: {visitor.vulnerabilities}"

    # 2. MockAISimulator.detect_issues
    issues = MockAISimulator.detect_issues(code)
    sec_issues = [i for i in issues if "eval" in i["description"].lower() or "pickle" in i["description"].lower()]
    assert len(sec_issues) == 0, f"detect_issues falsely reported comment: {sec_issues}"

    # 3. MockAnalysisSimulator
    sim_report = MockAnalysisSimulator.simulate_review("test_project", [{"filename": "main.py", "content": code}])
    sim_sec = [i for i in sim_report["issues"] if "eval" in i["explanation"].lower() or "pickle" in i["explanation"].lower()]
    assert len(sim_sec) == 0, f"MockAnalysisSimulator falsely reported comment: {sim_sec}"


def test_ast_security_string_literal_eval_and_pickle_not_reported():
    """String literals containing eval() and pickle.loads() must NOT be reported."""
    code = """
warning_banner = "Never execute eval(data) or pickle.loads(data) in production!"
regex_pattern = r"eval\\([a-zA-Z0-9_]+\\)"
pickle_template = 'pickle.load(stream)'

def echo(msg):
    return f"Security guide: {warning_banner}"
"""
    # 1. AST Visitor
    tree = ast.parse(code)
    visitor = PythonASTVisitor()
    visitor.visit(tree)
    assert len(visitor.vulnerabilities) == 0, f"AST visitor falsely reported string literal: {visitor.vulnerabilities}"

    # 2. MockAISimulator.detect_issues
    issues = MockAISimulator.detect_issues(code)
    sec_issues = [i for i in issues if "eval" in i["description"].lower() or "pickle" in i["description"].lower()]
    assert len(sec_issues) == 0, f"detect_issues falsely reported string literal: {sec_issues}"

    # 3. MockAnalysisSimulator
    sim_report = MockAnalysisSimulator.simulate_review("test_project", [{"filename": "main.py", "content": code}])
    sim_sec = [i for i in sim_report["issues"] if "eval" in i["explanation"].lower() or "pickle" in i["explanation"].lower()]
    assert len(sim_sec) == 0, f"MockAnalysisSimulator falsely reported string literal: {sim_sec}"


def test_ast_security_docstring_eval_and_pickle_not_reported():
    """Docstrings containing eval() and pickle.loads() must NOT be reported."""
    code = '''"""
Module documentation.
Usage example:
    >>> eval("2 + 2")
    >>> pickle.loads(b"cos\\nsystem\\n(S'ls'\\ntR.")
"""

def parse_input(data):
    """Parses input data. Do not pass to eval() or pickle.loads()."""
    return data.strip()
'''
    # 1. AST Visitor
    tree = ast.parse(code)
    visitor = PythonASTVisitor()
    visitor.visit(tree)
    assert len(visitor.vulnerabilities) == 0, f"AST visitor falsely reported docstring: {visitor.vulnerabilities}"

    # 2. MockAISimulator.detect_issues
    issues = MockAISimulator.detect_issues(code)
    sec_issues = [i for i in issues if "eval" in i["description"].lower() or "pickle" in i["description"].lower()]
    assert len(sec_issues) == 0, f"detect_issues falsely reported docstring: {sec_issues}"

    # 3. MockAnalysisSimulator
    sim_report = MockAnalysisSimulator.simulate_review("test_project", [{"filename": "main.py", "content": code}])
    sim_sec = [i for i in sim_report["issues"] if "eval" in i["explanation"].lower() or "pickle" in i["explanation"].lower()]
    assert len(sim_sec) == 0, f"MockAnalysisSimulator falsely reported docstring: {sim_sec}"


def test_ast_security_real_call_reported():
    """Real executable calls to eval() and pickle.loads() MUST be reported with high severity."""
    code = """import pickle

def execute_untrusted(user_cmd, raw_bytes):
    result = eval(user_cmd)
    obj = pickle.loads(raw_bytes)
    return result, obj
"""
    # 1. AST Visitor
    tree = ast.parse(code)
    visitor = PythonASTVisitor()
    visitor.visit(tree)
    vuln_descs = [v["description"].lower() for v in visitor.vulnerabilities]
    assert any("eval" in d for d in vuln_descs), "Real eval() call was NOT reported by AST visitor"
    assert any("pickle" in d for d in vuln_descs), "Real pickle.loads() call was NOT reported by AST visitor"

    # 2. MockAISimulator.detect_issues
    issues = MockAISimulator.detect_issues(code)
    eval_issue = next((i for i in issues if "eval" in i["description"].lower()), None)
    pickle_issue = next((i for i in issues if "pickle" in i["description"].lower()), None)

    assert eval_issue is not None, "Real eval() was NOT reported in detect_issues"
    assert pickle_issue is not None, "Real pickle.loads() was NOT reported in detect_issues"
    assert eval_issue["severity"].lower() == "high"
    assert pickle_issue["severity"].lower() == "high"

    # 3. MockAnalysisSimulator
    sim_report = MockAnalysisSimulator.simulate_review("test_project", [{"filename": "main.py", "content": code}])
    sim_eval = next((i for i in sim_report["issues"] if "eval" in i["explanation"].lower()), None)
    sim_pickle = next((i for i in sim_report["issues"] if "pickle" in i["explanation"].lower()), None)

    assert sim_eval is not None, "Real eval() was NOT reported by MockAnalysisSimulator"
    assert sim_pickle is not None, "Real pickle.loads() was NOT reported by MockAnalysisSimulator"
    assert sim_eval["severity"].lower() == "high"
    assert sim_pickle["severity"].lower() == "high"

