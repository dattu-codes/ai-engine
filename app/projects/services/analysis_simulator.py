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

            # File-specific scans
            for i, line in enumerate(lines, 1):
                stripped = line.strip()

                # 1. Eval usage check
                if "eval(" in line and not stripped.startswith("//") and not stripped.startswith("#"):
                    issues.append({
                        "category": "Security",
                        "severity": "critical",
                        "file": filename,
                        "line": i,
                        "evidence": line.strip(),
                        "explanation": "The code uses 'eval()', which allows arbitrary code execution and poses a major security vulnerability.",
                        "recommendation": "Avoid using eval(). Parse inputs using structured libraries (such as json.loads) or execute functions dynamically via map tables.",
                        "confidence": 0.95
                    })

                # 2. Print / Console log check
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
