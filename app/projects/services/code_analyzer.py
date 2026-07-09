import ast
import re
import math
import json
from typing import List, Dict, Any

class PythonASTVisitor(ast.NodeVisitor):
    def __init__(self):
        self.complexity = 1  # Base complexity is 1
        self.vulnerabilities = []

    def visit_If(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_IfExp(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_ListComp(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_DictComp(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_SetComp(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_GeneratorExp(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        # Each 'and' / 'or' adds 1 to complexity
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_Call(self, node):
        # Check for dangerous functions
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in ["eval", "exec"]:
                self.vulnerabilities.append({
                    "severity": "High",
                    "line": node.lineno,
                    "category": "Insecure Execution",
                    "title": f"Dangerous usage of '{func_name}'",
                    "description": f"Executing arbitrary code via '{func_name}' creates immediate code-injection vulnerabilities.",
                    "recommendation": "Use structural data parsing (like json.loads) instead of raw python evaluation."
                })
            elif func_name == "mktemp":
                self.vulnerabilities.append({
                    "severity": "Medium",
                    "line": node.lineno,
                    "category": "File Handling",
                    "title": "Usage of insecure tempfile.mktemp",
                    "description": "tempfile.mktemp is deprecated and vulnerable to symlink race condition attacks.",
                    "recommendation": "Use tempfile.TemporaryFile or tempfile.NamedTemporaryFile instead."
                })
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            # Check for subprocess.Popen/run with shell=True
            if attr_name in ["Popen", "run", "call", "check_output"]:
                # Check keyword arguments for shell=True
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        self.vulnerabilities.append({
                            "severity": "High",
                            "line": node.lineno,
                            "category": "Command Injection",
                            "title": "Subprocess execution with shell=True",
                            "description": "Executing commands via system shell permits malicious command manipulation and input injection.",
                            "recommendation": "Pass argument vectors as lists and set shell=False."
                        })
            elif attr_name == "mktemp" and isinstance(node.func.value, ast.Name) and node.func.value.id == "tempfile":
                self.vulnerabilities.append({
                    "severity": "Medium",
                    "line": node.lineno,
                    "category": "File Handling",
                    "title": "Usage of insecure tempfile.mktemp",
                    "description": "tempfile.mktemp is deprecated and vulnerable to symlink race condition attacks.",
                    "recommendation": "Use tempfile.TemporaryFile or tempfile.NamedTemporaryFile instead."
                })
        self.generic_visit(node)

    def visit_Assign(self, node):
        # Look for hardcoded keys in variable assignments
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id.lower()
                if any(x in var_name for x in ["password", "passwd", "secret", "api_key", "token", "private_key"]):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        val_str = node.value.value
                        if len(val_str) > 6 and not val_str.startswith("{") and not val_str.endswith("}"):
                            self.vulnerabilities.append({
                                "severity": "High",
                                "line": node.lineno,
                                "category": "Hardcoded Credentials",
                                "title": "Hardcoded secret detected",
                                "description": f"Variable '{target.id}' appears to be assigned a hardcoded key/secret literal value.",
                                "recommendation": "Load credentials dynamically from secure environment variables or a vault."
                            })
        self.generic_visit(node)


class CodeAnalyzerService:
    @staticmethod
    def analyze_codebase(files: List[Any]) -> Dict[str, Any]:
        """Runs static analysis across all files and calculates metrics."""
        file_reports = []
        total_complexity = 0
        total_mi = 0
        total_loc = 0
        vulnerabilities = []

        for f in files:
            if isinstance(f, dict):
                content = f.get("content") or ""
                filename = f.get("filename") or ""
                language_orig = f.get("language") or ""
            else:
                content = f.content or ""
                filename = f.filename
                language_orig = f.language or ""
            language = language_orig.lower()

            # Clean and count lines of code
            lines = [line.strip() for line in content.splitlines()]
            non_empty_lines = [line for line in lines if line]
            loc = len(non_empty_lines)
            total_loc += loc

            # 1. Cyclomatic Complexity
            complexity = 1
            file_vulns = []

            if language == "python":
                try:
                    tree = ast.parse(content)
                    visitor = PythonASTVisitor()
                    visitor.visit(tree)
                    complexity = visitor.complexity
                    file_vulns = visitor.vulnerabilities
                except Exception:
                    # AST Parse fallback to Regex
                    complexity = CodeAnalyzerService._regex_complexity(content, language)
                    file_vulns = CodeAnalyzerService._regex_security(content, filename, language)
            else:
                complexity = CodeAnalyzerService._regex_complexity(content, language)
                file_vulns = CodeAnalyzerService._regex_security(content, filename, language)

            # Map filenames to vulnerability lists
            for v in file_vulns:
                v["file"] = filename
                vulnerabilities.append(v)

            # 2. Halstead Volume Approximation
            # Extract word-like operands and special character operators
            words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', content)
            operators = re.findall(r'[\+\-\*/%=&\|\^~<>!]+', content)
            
            total_tokens = len(words) + len(operators)
            unique_tokens = len(set(words)) + len(set(operators))
            
            volume = 1.0
            if total_tokens > 0 and unique_tokens > 1:
                volume = total_tokens * math.log2(unique_tokens)

            # 3. Maintainability Index calculation
            if loc > 0:
                # Standard MI Formula bounds checked
                raw_mi = 171 - 5.2 * math.log(volume) - 0.23 * complexity - 16.2 * math.log(loc)
                mi = max(0, min(100, int((raw_mi / 171) * 100)))
            else:
                mi = 100

            total_complexity += complexity
            total_mi += mi

            file_reports.append({
                "file": filename,
                "language": language_orig,
                "loc": loc,
                "complexity": complexity,
                "maintainability": mi,
                "vulnerabilities_count": len(file_vulns)
            })

        num_files = len(files)
        avg_complexity = round(total_complexity / num_files, 1) if num_files > 0 else 1.0
        avg_mi = round(total_mi / num_files, 1) if num_files > 0 else 100.0

        # Security Risk evaluation based on vulns severity
        high_count = sum(1 for v in vulnerabilities if v["severity"] == "High")
        medium_count = sum(1 for v in vulnerabilities if v["severity"] == "Medium")
        
        if high_count > 0:
            security_rating = "CRITICAL"
        elif medium_count > 0:
            security_rating = "WARNING"
        elif len(vulnerabilities) > 0:
            security_rating = "LOW RISK"
        else:
            security_rating = "SECURE"

        # Complexity Rating
        if avg_complexity <= 4:
            complexity_rating = "LOW"
        elif avg_complexity <= 8:
            complexity_rating = "MODERATE"
        else:
            complexity_rating = "HIGH"

        # Maintainability Rating
        if avg_mi >= 80:
            mi_rating = "EXCELLENT"
        elif avg_mi >= 55:
            mi_rating = "MODERATE"
        else:
            mi_rating = "NEEDS REFACTORING"

        return {
            "summary": {
                "total_files": num_files,
                "total_loc": total_loc,
                "avg_complexity": avg_complexity,
                "complexity_rating": complexity_rating,
                "avg_maintainability": avg_mi,
                "maintainability_rating": mi_rating,
                "security_rating": security_rating,
                "vulnerabilities_count": len(vulnerabilities)
            },
            "files": file_reports,
            "vulnerabilities": vulnerabilities
        }

    @staticmethod
    def _regex_complexity(content: str, language: str) -> int:
        """Lexical analysis based cyclomatic complexity estimator."""
        # Baseline complexity is 1
        complexity = 1
        
        # Count decision keywords
        keywords = ["if", "for", "while", "catch"]
        if language == "java":
            keywords.append("case")
        elif language in ["javascript", "typescript"]:
            keywords.append("case")

        for kw in keywords:
            # Match word bound keyword
            complexity += len(re.findall(r'\b' + kw + r'\b', content))

        # Count logical operators
        complexity += len(re.findall(r'&&', content))
        complexity += len(re.findall(r'\|\|', content))

        # Python logical operator support (just in case)
        if language == "python":
            complexity += len(re.findall(r'\band\b', content))
            complexity += len(re.findall(r'\bor\b', content))

        return complexity

    @staticmethod
    def _regex_security(content: str, filename: str, language: str) -> List[Dict[str, Any]]:
        """Lexical pattern scanner to identify vulnerabilities in JS/TS/Java/Python fallback."""
        vulnerabilities = []
        lines = content.splitlines()

        for idx, line in enumerate(lines, 1):
            line_str = line.strip()

            if language == "go":
                # 1. Ignored error check
                if ":=" in line_str or "=" in line_str:
                    parts = line_str.split(":=") if ":=" in line_str else line_str.split("=")
                    if len(parts) > 1:
                        lhs, rhs = parts[0], parts[1]
                        lhs_vars = [v.strip() for v in lhs.split(",")]
                        if "_" in lhs_vars and "(" in rhs:
                            vulnerabilities.append({
                                "severity": "Medium",
                                "line": idx,
                                "category": "Bug",
                                "title": "Ignored error return value",
                                "description": "Go functions return errors that must be checked. Assigning error returns to blank identifier '_' bypasses safety error handling.",
                                "recommendation": "Check error explicitly: if err != nil { return err }"
                            })

                # 2. Mutex deadlock risk
                if ".Lock()" in line_str:
                    remaining_content = "\n".join(lines[idx:])
                    if ".Unlock()" not in remaining_content:
                        vulnerabilities.append({
                            "severity": "High",
                            "line": idx,
                            "category": "Bug",
                            "title": "Unreleased Mutex Lock (Deadlock Risk)",
                            "description": "Calling Mutex.Lock() without a corresponding defer or direct Mutex.Unlock() leaves locks unreleased, leading to deadlocks.",
                            "recommendation": "Add: defer mu.Unlock() immediately after mu.Lock()."
                        })

                # 3. Unbuffered channel
                if "make(chan " in line_str and "," not in line_str:
                    vulnerabilities.append({
                        "severity": "Medium",
                        "line": idx,
                        "category": "Performance",
                        "title": "Unbuffered channel creation",
                        "description": "Unbuffered channels block the sender until a receiver is ready, which can lead to goroutine blockages if not synchronized.",
                        "recommendation": "Provide a buffer size: make(chan Type, capacity), or ensure an active receiver goroutine is ready."
                    })

                # 4. Goroutine leak risk
                if "go " in line_str and "func(" in line_str:
                    if "ctx" not in line_str and "context" not in line_str:
                        vulnerabilities.append({
                            "severity": "Medium",
                            "line": idx,
                            "category": "Maintainability",
                            "title": "Uncontrolled goroutine execution (Leak Risk)",
                            "description": "Spawning a goroutine without passing a context or cancel channel makes it difficult to signal termination, risking goroutine leaks.",
                            "recommendation": "Pass a context.Context or cancellation channel to govern the lifecycle of the goroutine."
                        })

                # 5. HTTP context propagation
                if "http.Get(" in line_str or "http.Post(" in line_str or "http.PostForm(" in line_str:
                    vulnerabilities.append({
                        "severity": "Medium",
                        "line": idx,
                        "category": "Maintainability",
                        "title": "HTTP call without context propagation",
                        "description": "Making HTTP calls via the package-level http.Get/Post methods does not propagate request context, preventing timeout and cancellation signals.",
                        "recommendation": "Use http.NewRequestWithContext(ctx, ...) followed by client.Do(req) instead."
                    })

                # 6. SQL injection
                line_lower = line_str.lower()
                is_sql_keyword = any(k in line_lower for k in ["select ", "insert ", "update ", "delete "])
                if is_sql_keyword and ("+" in line_str or "%" in line_str or "fmt.sprintf" in line_lower):
                    vulnerabilities.append({
                        "severity": "High",
                        "line": idx,
                        "category": "Security",
                        "title": "Potential SQL Injection in query",
                        "description": "Constructing database queries via string concatenation or Sprintf allows raw user input to modify query structure, introducing SQL injection.",
                        "recommendation": "Use parameterized queries with placeholder arguments, e.g., db.Query('SELECT * FROM users WHERE id = ?', id)."
                    })

                # 7. Nil pointer risk
                if " := " in line_str and "nil" not in line_str:
                    match = re.search(r'\w+\([^)]*\)\.\w+', line_str)
                    if match:
                        vulnerabilities.append({
                            "severity": "Medium",
                            "line": idx,
                            "category": "Bug",
                            "title": "Chained method call/field access on function return (Nil Pointer Risk)",
                            "description": "Accessing a field or method directly on a function's return value without checking if the return is nil can trigger nil pointer panics.",
                            "recommendation": "Save the return value to a variable, check for nil, and then access its fields."
                        })

            # 1. Check for eval
            if "eval(" in line_str or "eval (" in line_str:
                vulnerabilities.append({
                    "severity": "High",
                    "line": idx,
                    "category": "Insecure Execution",
                    "title": "Dangerous usage of 'eval()'",
                    "description": "Executing code via eval() dynamically parses text inputs as active commands, introducing command injection vulnerabilities.",
                    "recommendation": "Use structural serializers, parsers (JSON.parse), or switch to safe arithmetic operators."
                })

            # 2. Check for innerHTML (JS/TS specific)
            if language in ["javascript", "typescript"] and ("innerHTML" in line_str or "dangerouslySetInnerHTML" in line_str):
                vulnerabilities.append({
                    "severity": "Medium",
                    "line": idx,
                    "category": "Cross-Site Scripting (XSS)",
                    "title": "Usage of innerHTML",
                    "description": "Direct write assignment to innerHTML bypasses DOM encoding and exposes clients to XSS input injection.",
                    "recommendation": "Use textContent, element.setAttribute, or utilize DOM purification libraries."
                })

            # 3. Check for hardcoded credentials / key assignments
            match = re.search(r'\b(key|secret|password|token|private_key|passwd)\s*=\s*[\'"`]([a-zA-Z0-9_\-\.]{8,})[\'"`]', line_str, re.IGNORECASE)
            if match:
                var_name = match.group(1)
                vulnerabilities.append({
                    "severity": "High",
                    "line": idx,
                    "category": "Hardcoded Credentials",
                    "title": "Hardcoded secret detected",
                    "description": f"Assigned literal string value to variable '{var_name}' matches patterns of high-entropy keys/secrets.",
                    "recommendation": "Remove hardcoded credentials. Store variables securely in the environment and inject dynamically."
                })

        return vulnerabilities