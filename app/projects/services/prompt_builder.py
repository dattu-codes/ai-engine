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
    "<string, strength description 1>",
    "<string, strength description 2>"
  ],
  "weaknesses": [
    "<string, weakness description 1>",
    "<string, weakness description 2>"
  ],
  "recommendations": [
    "<string, recommendation 1>",
    "<string, recommendation 2>"
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
