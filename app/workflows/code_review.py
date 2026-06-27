import json
import asyncio
from app.engine.graph import Graph, Node
from app.services.ai import GeminiClient, MockAISimulator

def clean_json_response(text: str) -> str:
    text = text.strip()
    # Strip markdown block formatting if present
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text

# Node: extract_functions
async def extract_functions(state):
    code = state.get("code", "")
    api_key = state.get("api_key", "").strip()
    model = state.get("model", "gemini-2.5-flash")
    
    # 1. Structural extraction is always best done via AST (100% accurate)
    ast_res = MockAISimulator.extract_functions(code)
    state["functions"] = ast_res["functions"]
    
    # 2. Get code summary (via Gemini if API key is provided, else fallback)
    if api_key:
        try:
            prompt = (
                "Summarize the purpose of the following Python code in one clean, professional paragraph. "
                "Do not include any formatting or other text, just the paragraph itself.\n\n"
                f"{code}"
            )
            summary = await GeminiClient.call_gemini(prompt, api_key, model=model)
            state["summary"] = summary
        except Exception as e:
            state["summary"] = f"AI summary failed: {str(e)}. Fallback: {ast_res['summary']}"
    else:
        state["summary"] = ast_res["summary"]
        
    log = {
        "node": "extract",
        "message": f"Extracted {len(state['functions'])} functions successfully.",
        "summary": state["summary"]
    }
    return state, log

# Node: check_complexity
async def check_complexity(state):
    code = state.get("code", "")
    api_key = state.get("api_key", "").strip()
    model = state.get("model", "gemini-2.5-flash")
    
    if api_key:
        try:
            prompt = (
                "Analyze the complexity of this Python code. You MUST return a JSON object ONLY, "
                "with no markdown formatting or tags. The JSON structure MUST match exactly:\n"
                '{"complexity_score": <int 1-100>, "explanation": "<string description>", '
                '"metrics": {"readability": <int 1-10>, "modularity": <int 1-10>, "maintainability": <int 1-10>}}\n\n'
                f"Code:\n{code}"
            )
            raw_res = await GeminiClient.call_gemini(prompt, api_key, model=model, json_mode=True)
            clean_res = clean_json_response(raw_res)
            res_dict = json.loads(clean_res)
            
            state["complexity"] = {
                "complexity_score": int(res_dict.get("complexity_score", 50)),
                "explanation": str(res_dict.get("explanation", "")),
                "metrics": res_dict.get("metrics", {"readability": 5, "modularity": 5, "maintainability": 5})
            }
        except Exception as e:
            fallback = MockAISimulator.calculate_complexity(code)
            state["complexity"] = fallback
            state["complexity"]["explanation"] = f"AI Analysis failed ({str(e)}). Fallback: {fallback['explanation']}"
    else:
        state["complexity"] = MockAISimulator.calculate_complexity(code)
        
    state["complexity_score"] = state["complexity"]["complexity_score"]
    
    log = {
        "node": "complexity",
        "message": f"Calculated complexity score: {state['complexity_score']}/100",
        "explanation": state["complexity"]["explanation"],
        "metrics": state["complexity"]["metrics"]
    }
    return state, log

# Node: detect_issues
async def detect_issues(state):
    code = state.get("code", "")
    api_key = state.get("api_key", "").strip()
    model = state.get("model", "gemini-2.5-flash")
    
    if api_key:
        try:
            prompt = (
                "Analyze this Python code for bugs, security risks, empty try-except blocks, or code style issues. "
                "You MUST return a JSON object ONLY, with no markdown formatting. The JSON structure MUST match exactly:\n"
                '{"issues": [{"type": "<bug|security|style>", "severity": "<high|medium|low>", '
                '"description": "<text>", "location": "<line or function>"}]}\n\n'
                f"Code:\n{code}"
            )
            raw_res = await GeminiClient.call_gemini(prompt, api_key, model=model, json_mode=True)
            clean_res = clean_json_response(raw_res)
            res_dict = json.loads(clean_res)
            state["issues"] = res_dict.get("issues", [])
        except Exception as e:
            fallback = MockAISimulator.detect_issues(code)
            state["issues"] = fallback
            state["issues"].append({
                "type": "style",
                "severity": "low",
                "description": f"AI Scanning encountered an error, fallbacks loaded. Error: {str(e)}",
                "location": "System Scanner"
            })
    else:
        state["issues"] = MockAISimulator.detect_issues(code)
        
    state["issues_count"] = len(state["issues"])
    
    log = {
        "node": "detect",
        "message": f"Found {state['issues_count']} issues in codebase.",
        "issues": state["issues"]
    }
    return state, log

# Node: suggest_improvements (looping)
async def suggest_improvements(state):
    code = state.get("code", "")
    api_key = state.get("api_key", "").strip()
    model = state.get("model", "gemini-2.5-flash")
    issues = state.get("issues", [])
    
    # Calculate quality score
    comp_score = state.get("complexity", {}).get("complexity_score", 30)
    penalty = sum(15 if iss.get("severity") == "high" else 8 if iss.get("severity") == "medium" else 4 for iss in issues)
    quality = max(0, min(100, 100 - comp_score - penalty))
    state["quality_score"] = quality
    
    threshold = int(state.get("threshold", 80))
    attempts = state.get("refactor_attempts", 0)
    
    log = {
        "node": "suggest_improvements",
        "message": f"Code quality assessed at {quality}%. Target threshold is {threshold}%.",
        "quality_score": quality,
        "refactor_attempts": attempts
    }
    
    # Loop condition
    if quality < threshold and attempts < 1:
        state["refactor_attempts"] = attempts + 1
        state["original_code"] = state.get("original_code", code) # save original code before first edit
        
        # Get refactored code
        if api_key:
            try:
                issues_str = json.dumps(issues, indent=2)
                prompt = (
                    "Refactor this Python code to resolve the issues listed below. Keep function names and core functionality "
                    "exactly the same, but improve modularity, PEP 8 styling, error handling, and formatting. "
                    "You MUST return a JSON object ONLY, with no markdown formatting. The JSON structure MUST match exactly:\n"
                    '{"refactored_code": "<raw refactored Python code string with quotes and newlines escaped>", '
                    '"improvements": ["<description list element 1>", "<description list element 2>"]}\n\n'
                    f"Original Code:\n{code}\n\n"
                    f"Issues to Resolve:\n{issues_str}"
                )
                raw_res = await GeminiClient.call_gemini(prompt, api_key, model=model, json_mode=True)
                clean_res = clean_json_response(raw_res)
                res_dict = json.loads(clean_res)
                
                state["code"] = res_dict.get("refactored_code", code)
                state["improvements"] = res_dict.get("improvements", ["Re-structured code for optimized complexity."])
            except Exception as e:
                # Fallback to mock refactoring
                fallback_res = MockAISimulator.suggest_improvements(code, issues)
                state["code"] = fallback_res["refactored_code"]
                state["improvements"] = fallback_res["improvements"]
                state["improvements"].append(f"AI Refactoring error: {str(e)}")
        else:
            fallback_res = MockAISimulator.suggest_improvements(code, issues)
            state["code"] = fallback_res["refactored_code"]
            state["improvements"] = fallback_res["improvements"]
            
        # Re-run pipeline on the new code to verify quality improvement!
        state["next"] = "extract"
        log["action"] = "Looping back to 'extract' with refactored code to re-evaluate quality score."
        log["improvements"] = state["improvements"]
    else:
        # Done! If we looped once, we are now finished.
        log["action"] = "Workflow complete. Final quality checks passed or retry budget exhausted."
        log["improvements"] = state.get("improvements", ["Code layout matches targeted guidelines."])
        
    return state, log

def build_code_review_graph():
    nodes = {
        "extract": Node("extract", extract_functions),
        "complexity": Node("complexity", check_complexity),
        "detect": Node("detect", detect_issues),
        "suggest_improvements": Node("suggest_improvements", suggest_improvements),
    }
    edges = {
        "extract": "complexity",
        "complexity": "detect",
        "detect": "suggest_improvements",
        "suggest_improvements": None
    }
    start = "extract"
    return Graph(nodes=nodes, edges=edges, start=start)
