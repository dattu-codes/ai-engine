import os
import ast
import json
import asyncio
import urllib.request
import urllib.error
import time

class BaseLLMClient:
    async def call(self, prompt: str, api_key: str, model: str, json_mode: bool = False) -> dict:
        raise NotImplementedError()

class GeminiClient(BaseLLMClient):
    @staticmethod
    async def call_gemini(prompt: str, api_key: str, model: str = "gemini-2.5-flash", json_mode: bool = False) -> str:
        # Legacy backward compatible endpoint
        res = await LLMRouter.generate(prompt, api_key, model, json_mode)
        return res["output"]

    async def call(self, prompt: str, api_key: str, model: str, json_mode: bool = False) -> dict:
        model_name = model
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"
        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        
        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        if json_mode:
            data["generationConfig"] = {
                "responseMimeType": "application/json"
            }
            
        req_body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
        
        start_time = time.time()
        def _execute():
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    return response.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8")
                try:
                    error_json = json.loads(error_body)
                    error_msg = error_json.get("error", {}).get("message", str(e))
                except Exception:
                    error_msg = error_body or str(e)
                raise RuntimeError(f"Gemini API Error: {error_msg}")
            except Exception as e:
                raise RuntimeError(f"Network error calling Gemini: {str(e)}")
                
        response_text = await asyncio.to_thread(_execute)
        execution_time = time.time() - start_time
        
        try:
            res_json = json.loads(response_text)
            text_out = res_json["candidates"][0]["content"]["parts"][0]["text"]
            
            # Simple token estimation
            p_tokens = len(prompt) // 4
            c_tokens = len(text_out) // 4
            # Cost: Gemini 2.5 Flash input: $0.075/1M, output: $0.30/1M
            cost = ((p_tokens * 0.075) + (c_tokens * 0.30)) / 1000000
            
            return {
                "provider": "google",
                "model": model,
                "output": text_out.strip(),
                "prompt_tokens": p_tokens,
                "completion_tokens": c_tokens,
                "total_tokens": p_tokens + c_tokens,
                "cost_estimate": round(cost, 6),
                "execution_time": round(execution_time, 2),
                "finish_reason": "stop"
            }
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Failed to parse response from Gemini: {str(e)}. Response was: {response_text[:200]}")

class OpenAIClient(BaseLLMClient):
    async def call(self, prompt: str, api_key: str, model: str, json_mode: bool = False) -> dict:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        data = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        
        if json_mode:
            data["response_format"] = {"type": "json_object"}
            
        req_body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
        
        start_time = time.time()
        def _execute():
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    return response.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8")
                try:
                    error_json = json.loads(error_body)
                    error_msg = error_json.get("error", {}).get("message", str(e))
                except Exception:
                    error_msg = error_body or str(e)
                raise RuntimeError(f"OpenAI API Error: {error_msg}")
            except Exception as e:
                raise RuntimeError(f"Network error calling OpenAI: {str(e)}")
                
        response_text = await asyncio.to_thread(_execute)
        execution_time = time.time() - start_time
        
        try:
            res_json = json.loads(response_text)
            text_out = res_json["choices"][0]["message"]["content"]
            
            p_tokens = res_json.get("usage", {}).get("prompt_tokens", len(prompt) // 4)
            c_tokens = res_json.get("usage", {}).get("completion_tokens", len(text_out) // 4)
            # Cost: GPT-4o input: $5.00/1M, output: $15.00/1M
            cost = ((p_tokens * 5.0) + (c_tokens * 15.0)) / 1000000
            
            return {
                "provider": "openai",
                "model": model,
                "output": text_out.strip(),
                "prompt_tokens": p_tokens,
                "completion_tokens": c_tokens,
                "total_tokens": p_tokens + c_tokens,
                "cost_estimate": round(cost, 6),
                "execution_time": round(execution_time, 2),
                "finish_reason": res_json["choices"][0].get("finish_reason", "stop")
            }
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Failed to parse response from OpenAI: {str(e)}. Response was: {response_text[:200]}")

class AnthropicClient(BaseLLMClient):
    async def call(self, prompt: str, api_key: str, model: str, json_mode: bool = False) -> dict:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
        
        data = {
            "model": model,
            "max_tokens": 4000,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        
        req_body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
        
        start_time = time.time()
        def _execute():
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    return response.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8")
                try:
                    error_json = json.loads(error_body)
                    error_msg = error_json.get("error", {}).get("message", str(e))
                except Exception:
                    error_msg = error_body or str(e)
                raise RuntimeError(f"Anthropic API Error: {error_msg}")
            except Exception as e:
                raise RuntimeError(f"Network error calling Anthropic: {str(e)}")
                
        response_text = await asyncio.to_thread(_execute)
        execution_time = time.time() - start_time
        
        try:
            res_json = json.loads(response_text)
            text_out = res_json["content"][0]["text"]
            
            p_tokens = res_json.get("usage", {}).get("input_tokens", len(prompt) // 4)
            c_tokens = res_json.get("usage", {}).get("output_tokens", len(text_out) // 4)
            # Cost: Claude 3.5 Sonnet input: $3.00/1M, output: $15.00/1M
            cost = ((p_tokens * 3.0) + (c_tokens * 15.0)) / 1000000
            
            return {
                "provider": "anthropic",
                "model": model,
                "output": text_out.strip(),
                "prompt_tokens": p_tokens,
                "completion_tokens": c_tokens,
                "total_tokens": p_tokens + c_tokens,
                "cost_estimate": round(cost, 6),
                "execution_time": round(execution_time, 2),
                "finish_reason": res_json.get("stop_reason", "stop")
            }
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Failed to parse response from Anthropic: {str(e)}. Response was: {response_text[:200]}")

class LLMRouter:
    @staticmethod
    async def generate(prompt: str, api_key: str, model: str, json_mode: bool = False) -> dict:
        # Route based on model prefix
        model_lower = model.lower()
        if model_lower.startswith("gpt-") or "openai" in model_lower:
            client = OpenAIClient()
        elif model_lower.startswith("claude-") or "anthropic" in model_lower:
            client = AnthropicClient()
        else:
            client = GeminiClient()
            
        return await client.call(prompt, api_key, model, json_mode)

    @staticmethod
    async def test_connection(provider: str, api_key: str) -> dict:
        if "mock" in api_key.lower():
            return {"status": "connected", "message": "Successfully verified connection via mock fallback."}
        test_prompt = "Hello"
        try:
            if provider == "google":
                res = await GeminiClient().call(test_prompt, api_key, model="gemini-2.5-flash")
            elif provider == "openai":
                res = await OpenAIClient().call(test_prompt, api_key, model="gpt-4o")
            elif provider == "anthropic":
                res = await AnthropicClient().call(test_prompt, api_key, model="claude-3-5-sonnet")
            else:
                return {"status": "invalid_provider", "error": "Unknown model provider"}
            
            if res.get("output"):
                return {"status": "connected"}
            return {"status": "error", "error": "Empty response received"}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class MockAISimulator:
    """
    Offline simulator that parses Python code using the standard AST module
    and applies heuristics to return detailed reviews, complexity ratings,
    and a refactored code block.
    """
    
    @staticmethod
    def extract_functions(code: str) -> dict:
        try:
            tree = ast.parse(code)
            funcs = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    args = [arg.arg for arg in node.args.args]
                    docstring = ast.get_docstring(node) or "No docstring provided."
                    funcs.append({
                        "name": node.name,
                        "args": args,
                        "line_no": node.lineno,
                        "docstring": docstring[:80] + "..." if len(docstring) > 80 else docstring
                    })
            return {
                "functions": funcs,
                "summary": f"Analyzed code structure and extracted {len(funcs)} functions. The module defines core logic for custom workflows and utility functions."
            }
        except SyntaxError as e:
            return {
                "functions": [],
                "summary": f"Could not parse code due to syntax error on line {e.lineno}: {e.msg}"
            }
        except Exception as e:
            return {
                "functions": [],
                "summary": f"Unable to parse functions structurally: {str(e)}"
            }

    @staticmethod
    def calculate_complexity(code: str) -> dict:
        lines = code.splitlines()
        line_count = len(lines)
        
        # Heuristics for complexity scoring
        nesting_levels = 0
        max_nesting = 0
        func_count = 0
        
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_count += 1
                if isinstance(node, (ast.For, ast.While, ast.If)):
                    # estimate depth via parent walk or simply assign standard weights
                    nesting_levels += 1
            
            # Simple complexity score formula
            comp_score = 10 + (line_count // 3) + (nesting_levels * 5)
            comp_score = min(max(comp_score, 15), 95)
        except Exception:
            comp_score = 45 # default average
            
        # Determine ratings
        readability = max(5, 10 - (line_count // 25) - (nesting_levels // 3))
        modularity = min(10, max(3, func_count * 2))
        maintainability = max(4, int((readability + modularity) / 2))
        
        complexity_label = "Low" if comp_score < 40 else "Medium" if comp_score < 70 else "High"
        
        return {
            "complexity_score": comp_score,
            "explanation": f"Readability is rated at {readability}/10. Code contains {line_count} lines of code and {func_count} function definitions. Complexity is {complexity_label}.",
            "metrics": {
                "readability": readability,
                "modularity": modularity,
                "maintainability": maintainability
            }
        }

    @staticmethod
    def detect_issues(code: str) -> list:
        issues = []
        lines = code.splitlines()
        seen_keys = set()
        
        # 1. Primary: Run comprehensive AST analysis via PythonASTVisitor
        try:
            from app.projects.services.code_analyzer import PythonASTVisitor
            tree = ast.parse(code)
            visitor = PythonASTVisitor()
            visitor.visit(tree)
            for v in visitor.vulnerabilities:
                line_no = v.get("line", 1)
                sev = v.get("severity", "High").lower()
                desc = v.get("description", "")
                cat = v.get("category", "Security")
                issue_type = "security" if cat in ["Insecure Execution", "Insecure Deserialization", "Command Injection", "SQL Injection", "Hardcoded Credentials"] else "bug"
                key = (line_no, issue_type)
                if key not in seen_keys:
                    seen_keys.add(key)
                    issues.append({
                        "type": issue_type,
                        "severity": sev,
                        "description": desc,
                        "location": f"Line {line_no}"
                    })
        except Exception:
            pass

        # 2. Check for empty except blocks via AST
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                # Empty except blocks
                if isinstance(node, ast.Try):
                    for handler in node.handlers:
                        is_silent = False
                        if len(handler.body) == 0:
                            is_silent = True
                        elif len(handler.body) == 1:
                            stmt = handler.body[0]
                            if isinstance(stmt, ast.Pass):
                                is_silent = True
                            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, (ast.Constant, ast.Ellipsis)):
                                is_silent = True
                        
                        if is_silent:
                            key = (handler.lineno, "security")
                            if key not in seen_keys:
                                seen_keys.add(key)
                                issues.append({
                                    "type": "security",
                                    "severity": "medium",
                                    "description": "Empty except block caught. Broad exceptions that silently pass can hide bugs.",
                                    "location": f"Line {handler.lineno}"
                                })
        except Exception:
            pass

        # 3. Text-based scans (fallback for non-AST / comment items)
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            if "TODO" in line:
                key = (i, "style_todo")
                if key not in seen_keys:
                    seen_keys.add(key)
                    issues.append({
                        "type": "style",
                        "severity": "low",
                        "description": f"Found pending development item: '{stripped}'",
                        "location": f"Line {i}"
                    })
            if "print(" in line and "logging" not in line:
                key = (i, "style_print")
                if key not in seen_keys:
                    seen_keys.add(key)
                    issues.append({
                        "type": "style",
                        "severity": "medium",
                        "description": "Uses direct 'print()' statements. Consider using a structured logger for production.",
                        "location": f"Line {i}"
                    })
            # Note: eval and pickle security detection uses ONLY the AST in Step 1 (PythonASTVisitor)
            # Text-based scans for eval and pickle are omitted to prevent false positives in strings, comments, and docstrings.
            if "yaml.load(" in line and "safeloader" not in line.lower():
                key = (i, "security")
                if key not in seen_keys:
                    seen_keys.add(key)
                    issues.append({
                        "type": "security",
                        "severity": "high",
                        "description": "yaml.load without SafeLoader allows arbitrary Python object instantiation and code execution.",
                        "location": f"Line {i}"
                    })
            if "os.system(" in line:
                key = (i, "security")
                if key not in seen_keys:
                    seen_keys.add(key)
                    issues.append({
                        "type": "security",
                        "severity": "high",
                        "description": "Executing arbitrary shell commands via os.system allows command injection.",
                        "location": f"Line {i}"
                    })
            if ("subprocess." in line or "popen(" in line.lower()) and "shell=true" in line.lower().replace(" ", ""):
                key = (i, "security")
                if key not in seen_keys:
                    seen_keys.add(key)
                    issues.append({
                        "type": "security",
                        "severity": "high",
                        "description": "Executing commands via system shell permits malicious command manipulation and input injection.",
                        "location": f"Line {i}"
                    })

        return issues

    @staticmethod
    def suggest_improvements(code: str, issues: list) -> dict:
        lines = code.splitlines()
        improvements = []
        needs_manual_fix = []
        
        # Parse AST to accurately identify syntax nodes and boundaries
        tree = None
        try:
            tree = ast.parse(code)
        except Exception:
            pass

        # Track which 1-based line numbers are to be modified
        lines_to_replace = {}  # 1-based line_no -> new string content
        inserted_header_lines = []

        # 1. Handle empty except blocks:
        # Edit ONLY the except line and the except body (pass -> logging).
        # NEVER touch the try body!
        has_except_issue = any("except" in str(iss.get("description", "")).lower() for iss in issues)
        if tree and has_except_issue:
            for node in ast.walk(tree):
                if isinstance(node, ast.Try):
                    for handler in node.handlers:
                        is_empty_or_pass = False
                        if len(handler.body) == 0:
                            is_empty_or_pass = True
                        elif len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
                            is_empty_or_pass = True
                        
                        if is_empty_or_pass:
                            # 1. Update the except line (handler.lineno) to 'except Exception as e:'
                            h_line_idx = handler.lineno - 1
                            if 0 <= h_line_idx < len(lines):
                                orig_h_line = lines[h_line_idx]
                                indent_h = len(orig_h_line) - len(orig_h_line.lstrip())
                                lines_to_replace[handler.lineno] = " " * indent_h + "except Exception as e:"
                            
                            # 2. Update the pass line inside handler.body (handler.body[0].lineno)
                            if handler.body:
                                pass_line_idx = handler.body[0].lineno - 1
                                if 0 <= pass_line_idx < len(lines):
                                    orig_p_line = lines[pass_line_idx]
                                    indent_p = len(orig_p_line) - len(orig_p_line.lstrip())
                                    lines_to_replace[handler.body[0].lineno] = " " * indent_p + 'logging.warning("An error occurred: %s", e)'
                            
                            if "import logging" not in code and "import logging" not in inserted_header_lines:
                                inserted_header_lines.append("import logging")
                            
                            improvements.append("Expanded empty except block to 'except Exception as e:' and logged error.")

        # 2. Handle eval() calls:
        # Replace with ast.literal_eval(...) when safe; otherwise mark 'needs manual fix'
        has_eval_issue = any("eval" in str(iss.get("description", "")).lower() for iss in issues)
        if tree and has_eval_issue:
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "eval":
                    is_safe_literal = False
                    if node.args:
                        arg0 = node.args[0]
                        if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                            try:
                                ast.literal_eval(arg0.value)
                                is_safe_literal = True
                            except Exception:
                                is_safe_literal = False
                    
                    if is_safe_literal:
                        line_idx = node.lineno - 1
                        if 0 <= line_idx < len(lines):
                            orig_line = lines[line_idx]
                            lines_to_replace[node.lineno] = orig_line.replace("eval(", "ast.literal_eval(")
                            if "import ast" not in code and "import ast" not in inserted_header_lines:
                                inserted_header_lines.append("import ast")
                            improvements.append("Replaced safe eval() with ast.literal_eval().")
                    else:
                        needs_manual_fix.append({
                            "line": node.lineno,
                            "type": "security",
                            "severity": "high",
                            "description": f"Dangerous usage of eval() on line {node.lineno}: dynamic argument cannot be safely auto-fixed and requires manual remediation."
                        })

        # 3. Handle pickle.loads() / pickle.load():
        # Insecure deserialization cannot be safely auto-fixed without protocol redesign; mark 'needs manual fix'
        has_pickle_issue = any("pickle" in str(iss.get("description", "")).lower() for iss in issues)
        if tree and has_pickle_issue:
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    is_pickle = False
                    if isinstance(node.func, ast.Attribute) and node.func.attr in ["loads", "load"]:
                        if isinstance(node.func.value, ast.Name) and node.func.value.id in ["pickle", "_pickle"]:
                            is_pickle = True
                    elif isinstance(node.func, ast.Name) and node.func.id in ["loads", "load"]:
                        is_pickle = True
                    if is_pickle:
                        needs_manual_fix.append({
                            "line": node.lineno,
                            "type": "security",
                            "severity": "high",
                            "description": f"Unsafe pickle deserialization on line {node.lineno}: requires manual migration to safe serialization (e.g. JSON)."
                        })

        # 4. Handle direct print statements:
        has_print_issue = any("print" in str(iss.get("description", "")).lower() for iss in issues)
        if has_print_issue:
            for i, line in enumerate(lines, 1):
                if i not in lines_to_replace and "print(" in line and not line.strip().startswith("#"):
                    lines_to_replace[i] = line.replace("print(", "logging.info(")
                    if "import logging" not in code and "import logging" not in inserted_header_lines:
                        inserted_header_lines.append("import logging")
                    improvements.append("Replaced standard print statements with structured logging.")

        # Reconstruct refactored code preserving unmodified lines exactly
        refactored_lines = []
        for imp_header in inserted_header_lines:
            refactored_lines.append(imp_header)
        
        for i, line in enumerate(lines, 1):
            if i in lines_to_replace:
                refactored_lines.append(lines_to_replace[i])
            else:
                refactored_lines.append(line)

        refactored_code = "\n".join(refactored_lines)

        # Deduplicate improvements preserving exact order
        deduped_improvements = list(dict.fromkeys(improvements))

        return {
            "refactored_code": refactored_code,
            "improvements": deduped_improvements,
            "needs_manual_fix": needs_manual_fix
        }

    @staticmethod
    def verify_patch(original_code: str, patched_code: str) -> dict:
        """
        Re-scans the patched code with the exact same AST analyzer in memory (nothing saved).
        Computes resolved vs remaining findings by comparing before and after.
        Also checks compile()/ast.parse() syntax on the patched code.
        Returns: {resolved: [...], remaining: [...], syntax_ok: bool, summary: str}
        """
        # 1. Compile and parse check
        syntax_ok = True
        syntax_error = None
        try:
            compile(patched_code, "<patched_code>", "exec")
            ast.parse(patched_code)
        except Exception as e:
            syntax_ok = False
            syntax_error = str(e)

        # 2. In-memory re-scan using the same AST analyzer
        before_issues = MockAISimulator.detect_issues(original_code)
        after_issues = MockAISimulator.detect_issues(patched_code) if syntax_ok else before_issues

        # 3. Match and classify findings into resolved vs remaining
        def get_signature(issue):
            desc = issue.get("description", "").lower()
            if "eval" in desc:
                return "eval"
            if "pickle" in desc:
                return "pickle"
            if "except" in desc:
                return "except"
            if "yaml" in desc:
                return "yaml"
            if "os.system" in desc or "system" in desc:
                return "os_system"
            if "subprocess" in desc or "popen" in desc or "shell=true" in desc:
                return "subprocess"
            if "print" in desc:
                return "print"
            if "sql" in desc:
                return "sql"
            if "mktemp" in desc:
                return "mktemp"
            return issue.get("description", "")

        after_signatures = {get_signature(iss) for iss in after_issues}
        
        resolved = []
        for b_iss in before_issues:
            sig = get_signature(b_iss)
            if sig not in after_signatures:
                resolved.append(b_iss)
        
        # Correlate remaining findings with original line numbers from before_issues
        before_by_sig = {get_signature(b): b for b in before_issues}
        remaining = []
        for a_iss in after_issues:
            sig = get_signature(a_iss)
            orig = before_by_sig.get(sig)
            item = dict(a_iss)
            if orig and orig.get("location"):
                orig_loc = orig.get("location")
                patched_loc = a_iss.get("location")
                item["original_location"] = orig_loc
                item["patched_location"] = f"{patched_loc} in patched code"
                item["location"] = f"{orig_loc} ({patched_loc} in patched code)"
            else:
                item["patched_location"] = f"{a_iss.get('location', '')} in patched code"
            remaining.append(item)

        # 4. Generate summary text derived strictly from this result
        if not syntax_ok:
            summary = f"Verification failed: Patched code syntax error ({syntax_error})."
        elif resolved and remaining:
            summary = f"Re-scan complete: {len(resolved)} finding(s) resolved, {len(remaining)} finding(s) remaining (manual fix required)."
        elif resolved and not remaining:
            summary = f"Re-scan complete: All {len(resolved)} finding(s) resolved successfully. Syntax verified."
        elif not resolved and remaining:
            summary = f"Re-scan complete: 0 findings resolved. {len(remaining)} finding(s) remaining (manual fix required)."
        else:
            summary = "Re-scan complete: 0 findings detected in codebase. Syntax verified."

        return {
            "resolved": resolved,
            "remaining": remaining,
            "syntax_ok": syntax_ok,
            "summary": summary
        }
