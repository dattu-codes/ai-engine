import ast
import json
from typing import List, Dict, Any

class MockAnalysisSimulator:
    @staticmethod
    def simulate_review(project_name: str, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Simulates an AI code review by running basic rule checks on the files list.
        Returns a dictionary that conforms to the expected Stage 3 JSON schema.
        """
        issues = []
        strengths = [
            "Project structure separates modular files cleanly.",
            "Appropriate naming convention for source files."
        ]
        weaknesses = []
        recommendations = []

        total_lines = 0
        total_files = len(files)

        for f in files:
            filename = f.get("filename", "")
            content = f.get("content", "")
            lines = content.splitlines()
            total_lines += len(lines)

            is_python = filename.endswith(".py") or filename == ""
            if is_python:
                try:
                    tree = ast.parse(content)
                    pickle_aliases = set()
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ImportFrom) and node.module in ["pickle", "_pickle"]:
                            for alias in node.names:
                                if alias.name in ["loads", "load"]:
                                    pickle_aliases.add(alias.asname or alias.name)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call):
                            if isinstance(node.func, ast.Name) and node.func.id == "eval":
                                line_text = lines[node.lineno - 1] if node.lineno <= len(lines) else "eval(...)"
                                issues.append({
                                    "category": "Security",
                                    "severity": "high",
                                    "file": filename,
                                    "line": node.lineno,
                                    "evidence": line_text.strip(),
                                    "explanation": "The code uses 'eval()', which allows arbitrary code execution and poses a major security vulnerability.",
                                    "recommendation": "Avoid using eval(). Parse inputs using structured libraries (such as json.loads) or execute functions dynamically via map tables.",
                                    "confidence": 0.95
                                })
                            is_pickle = False
                            if isinstance(node.func, ast.Attribute) and node.func.attr in ["loads", "load"]:
                                if isinstance(node.func.value, ast.Name) and node.func.value.id in ["pickle", "_pickle"]:
                                    is_pickle = True
                            elif isinstance(node.func, ast.Name) and node.func.id in pickle_aliases:
                                is_pickle = True

                            if is_pickle:
                                line_text = lines[node.lineno - 1] if node.lineno <= len(lines) else "pickle.loads(...)"
                                issues.append({
                                    "category": "Security",
                                    "severity": "high",
                                    "file": filename,
                                    "line": node.lineno,
                                    "evidence": line_text.strip(),
                                    "explanation": "The code uses pickle deserialization, which allows arbitrary code execution and is vulnerable to untrusted data injection.",
                                    "recommendation": "Use safe serialization formats like JSON (json.loads) instead of pickle.",
                                    "confidence": 0.95
                                })
                except Exception:
                    pass

            # File-specific scans
            for i, line in enumerate(lines, 1):
                stripped = line.strip()

                # 1. Eval usage check (non-Python only; Python security detection uses ONLY AST)
                if not is_python and "eval(" in line and "literal_eval" not in line and not stripped.startswith("//") and not stripped.startswith("#"):
                    issues.append({
                        "category": "Security",
                        "severity": "high",
                        "file": filename,
                        "line": i,
                        "evidence": line.strip(),
                        "explanation": "The code uses 'eval()', which allows arbitrary code execution and poses a major security vulnerability.",
                        "recommendation": "Avoid using eval(). Parse inputs using structured libraries (such as json.loads) or execute functions dynamically via map tables.",
                        "confidence": 0.95
                    })

                # 2. Pickle deserialization check (non-Python only; Python security detection uses ONLY AST)
                if not is_python and ("pickle.loads(" in line or "pickle.load(" in line) and not stripped.startswith("#"):
                    issues.append({
                        "category": "Security",
                        "severity": "high",
                        "file": filename,
                        "line": i,
                        "evidence": line.strip(),
                        "explanation": "The code uses pickle deserialization, which allows arbitrary code execution and is vulnerable to untrusted data injection.",
                        "recommendation": "Use safe serialization formats like JSON (json.loads) instead of pickle.",
                        "confidence": 0.95
                    })

                # 3. YAML load without SafeLoader
                if "yaml.load(" in line and "safeloader" not in line.lower() and not stripped.startswith("#"):
                    issues.append({
                        "category": "Security",
                        "severity": "high",
                        "file": filename,
                        "line": i,
                        "evidence": line.strip(),
                        "explanation": "yaml.load without SafeLoader allows arbitrary Python object instantiation and code execution.",
                        "recommendation": "Use yaml.safe_load(data) instead.",
                        "confidence": 0.95
                    })

                # 4. os.system command injection
                if "os.system(" in line and not stripped.startswith("#"):
                    issues.append({
                        "category": "Security",
                        "severity": "high",
                        "file": filename,
                        "line": i,
                        "evidence": line.strip(),
                        "explanation": "Executing arbitrary shell commands via os.system allows command injection.",
                        "recommendation": "Use subprocess.run with argument vectors and shell=False.",
                        "confidence": 0.95
                    })

                # 5. subprocess with shell=True
                if ("subprocess." in line or "popen(" in line.lower()) and "shell=true" in line.lower().replace(" ", "") and not stripped.startswith("#"):
                    issues.append({
                        "category": "Security",
                        "severity": "high",
                        "file": filename,
                        "line": i,
                        "evidence": line.strip(),
                        "explanation": "Executing commands via system shell permits malicious command manipulation and input injection.",
                        "recommendation": "Pass argument vectors as lists and set shell=False.",
                        "confidence": 0.95
                    })

                # 6. Print / Console log check
                if "print(" in line and "logging" not in line and not stripped.startswith("#"):
                    issues.append({
                        "category": "Style",
                        "severity": "low",
                        "file": filename,
                        "line": i,
                        "evidence": line.strip(),
                        "explanation": "Standard print() statements write directly to standard output, making log configuration difficult.",
                        "recommendation": "Replace standard prints with a configured logging library (e.g. logging.info).",
                        "confidence": 0.85
                    })
                elif "console.log(" in line and not stripped.startswith("//") and not stripped.startswith("/*"):
                    issues.append({
                        "category": "Style",
                        "severity": "low",
                        "file": filename,
                        "line": i,
                        "evidence": line.strip(),
                        "explanation": "Direct console.log statements should be avoided in production environments.",
                        "recommendation": "Use a structured logging package or strip console logs from production builds.",
                        "confidence": 0.80
                    })
                elif "System.out.println(" in line and not stripped.startswith("//") and not stripped.startswith("/*"):
                    issues.append({
                        "category": "Style",
                        "severity": "low",
                        "file": filename,
                        "line": i,
                        "evidence": line.strip(),
                        "explanation": "System.out.println statement is used for debugging console output.",
                        "recommendation": "Use a configured SLF4J or log4j logger instance instead.",
                        "confidence": 0.85
                    })

                # 3. broad pass / empty except check (Python)
                if stripped == "pass" and i > 1:
                    prev_line = lines[i-2].strip()
                    if "except" in prev_line or "except:" in prev_line:
                        issues.append({
                            "category": "Security",
                            "severity": "medium",
                            "file": filename,
                            "line": i,
                            "evidence": line.strip(),
                            "explanation": "An empty except-pass block handles all exceptions implicitly, which can suppress runtime errors and mask hidden bugs.",
                            "recommendation": "At least log the warning traceback (e.g. logging.exception) or handle specific exception types.",
                            "confidence": 0.90
                        })

                # 4. Pending TODO check
                if "TODO" in line or "TODO:" in line:
                    issues.append({
                        "category": "Style",
                        "severity": "low",
                        "file": filename,
                        "line": i,
                        "evidence": line.strip(),
                        "explanation": f"Found pending implementation item: '{line.strip()}'",
                        "recommendation": "Track and resolve the TODO or move it to a project management board.",
                        "confidence": 0.95
                    })

        # Calculate a simulated quality score
        crit_issues = sum(1 for iss in issues if iss["severity"] == "critical")
        high_issues = sum(1 for iss in issues if iss["severity"] == "high")
        med_issues = sum(1 for iss in issues if iss["severity"] == "medium")
        low_issues = sum(1 for iss in issues if iss["severity"] == "low")

        penalty = (crit_issues * 25) + (high_issues * 15) + (med_issues * 5) + (low_issues * 2)
        score = max(0, min(100, 100 - penalty))

        # Build list of weaknesses and recommendations based on issues
        if crit_issues > 0:
            weaknesses.append("Critically hazardous eval functions detected in code execution path.")
            recommendations.append("Prioritize removing all arbitrary code execution paths (eval) to secure system parameters.")
        if med_issues > 0:
            weaknesses.append("Silent except blocks can hide structural runtime anomalies.")
            recommendations.append("Ensure broad catch blocks log the exception traceback before continuing.")
        if low_issues > 0:
            weaknesses.append("Stylistic debugging statements (prints/console logs) are present.")
            recommendations.append("Configure a standard logging module to replace direct console prints.")

        if not weaknesses:
            weaknesses.append("No critical codebase defects found during structural checks.")
            recommendations.append("Maintain modular testing patterns going forward.")

        summary = f"Completed mock offline scan of project '{project_name}'. Checked {total_files} files containing {total_lines} lines of code. Code quality score is rated at {score}%."

        return {
            "score": score,
            "summary": summary,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendations": recommendations,
            "issues": issues
        }
