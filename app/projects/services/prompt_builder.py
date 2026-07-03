from typing import List, Dict, Any

class PromptBuilder:
    @staticmethod
    def build_review_prompt(project_name: str, files: List[Dict[str, Any]]) -> str:
        """
        Builds a structured prompt for the Gemini AI Review Engine.
        Injects project source code, file metadata, and constraints.
        """
        # Format codebase files content
        codebase_str = ""
        for idx, f in enumerate(files, 1):
            codebase_str += f"--- FILE #{idx}: {f['filename']} (Language: {f['language']}) ---\n"
            codebase_str += f"{f['content']}\n\n"

        prompt = f"""You are a professional software engineering code review agent analyzing the codebase for the project '{project_name}'.
Your task is to conduct an in-depth code review of the source files provided below.

Inspect the code for:
1. Logic bugs or crash vulnerabilities.
2. Common security risks (such as hardcoded credentials, SQL injections, or shell execution).
3. Code smells, formatting deviations, and style guide issues (e.g. PEP 8).
4. Lack of error handling or missing documentation/docstrings.
5. Inefficiencies or suboptimal logic.

--- SOURCE FILES ---
{codebase_str}
--------------------

### INSTRUCTIONS:
1. Analyze all files as a whole, looking at their structure, readability, and potential bugs.
2. Rate the project quality with a score between 0 and 100 (where 100 is excellent).
3. Provide an executive summary of your analysis.
4. Detail a list of strengths, weaknesses, and clear actionable recommendations.
5. Identify specific issues in the code, pointing out the exact file name and a specific description, severity, and recommendation to fix them.

You MUST return a valid JSON object ONLY. Do NOT wrap the JSON inside markdown blocks (such as ```json) or add other conversational text. Return only the raw JSON string matching this exact schema:

{{
  "score": <int, 0 to 100>,
  "summary": "<string, executive summary of the code quality>",
  "strengths": [
    "<string, strength description 1>"
  ],
  "weaknesses": [
    "<string, weakness description 1>"
  ],
  "recommendations": [
    "<string, recommendation 1>"
  ],
  "issues": [
    {{
      "category": "<Bug|Security|Performance|Maintainability|Readability|Architecture|Style|Documentation>",
      "severity": "<high|medium|low>",
      "file": "<string, filename where the issue is found>",
      "title": "<string, short description of the issue>",
      "description": "<string, detailed explanation of what is wrong>",
      "recommendation": "<string, how to fix the issue>",
      "confidence": <float, rating of your confidence in this finding between 0.0 and 1.0>
    }}
  ]
}}
"""
        return prompt

    @staticmethod
    def build_module_review_prompt_v3(
        project_name: str,
        project_type: str,
        framework: str,
        architecture: str,
        dependencies: List[str],
        entry_points: List[str],
        module_name: str,
        files: List[Dict[str, Any]],
        static_analysis: List[Dict[str, Any]]
    ) -> str:
        """
        Builds Prompt Builder v3 for a single isolated module.
        """
        codebase_str = ""
        for idx, f in enumerate(files, 1):
            codebase_str += f"--- FILE #{idx}: {f['filename']} (Language: {f['language']}) ---\n"
            codebase_str += f"{f['content']}\n\n"

        static_str = json.dumps(static_analysis, indent=2)

        prompt = f"""You are a professional software engineering code review agent performing a review on the project '{project_name}'.
You are reviewing the **{module_name}** module of the codebase.

--- PROJECT CONTEXT ---
Project Type: {project_type}
Framework: {framework}
Architecture: {architecture}
Entry Points: {', '.join(entry_points)}
Relevant Dependencies: {', '.join(dependencies)}
-----------------------

--- CURRENT MODULE FILES ({module_name}) ---
{codebase_str}
--------------------------------------------

--- STATIC CODE ANALYSIS ALERTS ---
{static_str}
-----------------------------------

### INSTRUCTIONS:
1. Analyze files in this module. Avoid generic suggestions and style-only comments.
2. Target high-confidence bugs, SQL injections, hardcoded credentials, logic flaws, and performance bottlenecks.
3. Every issue must include: category, severity, confidence (0.0 to 1.0), file, line (matching exact code line number), evidence (the exact code snippet showing the issue), explanation, and recommendation.
4. Ratings: rate this module's quality between 0 and 100.

Return a valid JSON object ONLY. Do NOT wrap the JSON inside markdown blocks (such as ```json) or add other conversational text. Return only the raw JSON string matching this exact schema:

{{
  "score": <int, 0 to 100>,
  "summary": "<string, module quality summary>",
  "strengths": [
    "<string>"
  ],
  "weaknesses": [
    "<string>"
  ],
  "recommendations": [
    "<string>"
  ],
  "issues": [
    {{
      "category": "<Bug|Security|Performance|Maintainability|Readability|Architecture|Style|Documentation>",
      "severity": "<critical|high|medium|low>",
      "file": "<string, filename where the issue is found>",
      "line": <int, 1-indexed line number where the issue resides>,
      "evidence": "<string, exact code snippet matching the line>",
      "explanation": "<string, detailed explanation>",
      "recommendation": "<string, how to fix it>",
      "confidence": <float, rating of your confidence in this finding between 0.0 and 1.0>
    }}
  ]
}}
"""
        return prompt

    @staticmethod
    def build_merge_prompt_v3(project_name: str, reports: List[Dict[str, Any]]) -> str:
        """
        Builds prompt template to consolidate modular reports.
        """
        reports_str = ""
        for idx, rep in enumerate(reports, 1):
            reports_str += f"--- MODULE REPORT #{idx} ---\n{json.dumps(rep, indent=2)}\n\n"

        prompt = f"""You are a senior engineering director consolidating code review findings for the project '{project_name}'.
Your task is to merge the individual module reports, remove duplicates, group related issues, and filter out low-confidence findings.

--- INDIVIDUAL MODULE REPORTS ---
{reports_str}
---------------------------------

### INSTRUCTIONS:
1. Merge the findings of all individual module reports.
2. Deduplicate issues that report the same issue in the same file/line.
3. Keep only high-confidence, evidence-backed findings. Discard style-only or generic comments.
4. Prioritize issues by sorting them by severity in this order: Critical, High, Medium, Low.
5. Calculate a single consolidated quality score between 0 and 100 based on the severities and number of issues found.
6. Summarize the overall codebase quality.

Return a valid JSON object ONLY. Do NOT wrap the JSON inside markdown blocks (such as ```json) or add other conversational text. Return only the raw JSON string matching this exact schema:

{{
  "score": <int, 0 to 100>,
  "summary": "<string, consolidated project quality summary>",
  "strengths": [
    "<string>"
  ],
  "weaknesses": [
    "<string>"
  ],
  "recommendations": [
    "<string>"
  ],
  "issues": [
    {{
      "category": "<Bug|Security|Performance|Maintainability|Readability|Architecture|Style|Documentation>",
      "severity": "<critical|high|medium|low>",
      "file": "<string, filename where the issue is found>",
      "line": <int, line number>,
      "evidence": "<string, exact code snippet>",
      "explanation": "<string, explanation>",
      "recommendation": "<string, recommendation>",
      "confidence": <float, between 0.0 and 1.0>
    }}
  ]
}}
"""
        return prompt
