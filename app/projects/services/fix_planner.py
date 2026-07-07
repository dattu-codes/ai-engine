import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.projects.models.project_models import ReviewFinding
from app.services.ai import GeminiClient

class FixPlanner:
    @staticmethod
    async def create_plan(db: Session, finding: ReviewFinding, api_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Creates a structured engineering fix plan for a finding.
        In Live Mode, it queries Gemini. In Offline Mode, it returns a deterministic simulated plan.
        """
        if api_key:
            prompt = f"""
You are an expert Lead Software Architect.
Analyze the following review finding and create a structured engineering plan to fix it.

File Path: {finding.file_path}
Line Number: {finding.line_number}
Category: {finding.category}
Severity: {finding.severity}
Title: {finding.title}
Description: {finding.description}
Recommendation: {finding.recommendation}
Downstream Risk: {finding.downstream_risk or "Low Risk"}

Output a JSON object ONLY. Do NOT output any markdown backticks, backslashes, or explainers.
The JSON object must contain exactly the following keys:
- root_cause: string description of the underlying issue
- technical_explanation: detailed explanation of why this happens
- affected_files: list of strings (file paths)
- dependencies: list of strings (dependency packages affected, if any)
- risk_analysis: string (estimated risk level: Low, Medium, High and explanation)
- expected_behaviour: string describing how the code will behave after the fix
- confidence: float between 0.0 and 1.0
- estimated_files_changed: integer (number of files to modify)
- impact_score: float between 0.0 and 1.0 (estimated impact rating)
"""
            try:
                plan_str = await GeminiClient.call_gemini(prompt, api_key=api_key)
                # Clean prompt formatting if markdown backticks were returned
                if plan_str.strip().startswith("```"):
                    lines = plan_str.strip().splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].startswith("```"):
                        lines = lines[:-1]
                    plan_str = "\n".join(lines).strip()
                
                plan_json = json.loads(plan_str)
                # Ensure all required fields exist
                return {
                    "root_cause": plan_json.get("root_cause", "Unvalidated code execution pattern."),
                    "technical_explanation": plan_json.get("technical_explanation", finding.description),
                    "affected_files": plan_json.get("affected_files", [finding.file_path]),
                    "dependencies": plan_json.get("dependencies", []),
                    "risk_analysis": plan_json.get("risk_analysis", f"Low risk fix in {finding.file_path}"),
                    "expected_behaviour": plan_json.get("expected_behaviour", finding.recommendation),
                    "confidence": float(plan_json.get("confidence", 0.9)),
                    "estimated_files_changed": int(plan_json.get("estimated_files_changed", 1)),
                    "impact_score": float(plan_json.get("impact_score", 0.8)),
                    "estimated_risk": plan_json.get("risk_analysis", "Low")
                }
            except Exception as e:
                print(f"Gemini planner API failed, falling back to mock planner: {e}")
                pass

        # Offline Mock Plan
        root_cause = f"Detected {finding.category} issue on line {finding.line_number} of {finding.file_path}."
        if finding.category == "Security":
            root_cause = f"Input validation bypass or insecure database operation on line {finding.line_number}."
        elif finding.category == "Maintainability":
            root_cause = "Suboptimal resource disposal or code style inconsistency."

        technical_explanation = finding.description
        affected_files = [finding.file_path]
        
        # Estimate risk based on severity
        estimated_risk = "Low"
        if finding.severity.lower() == "critical" or finding.severity.lower() == "high":
            estimated_risk = "High"
        elif finding.severity.lower() == "medium":
            estimated_risk = "Medium"

        return {
            "root_cause": root_cause,
            "technical_explanation": technical_explanation,
            "affected_files": affected_files,
            "dependencies": [],
            "risk_analysis": f"{estimated_risk} risk change targeting {finding.file_path}.",
            "expected_behaviour": f"Code will execute safely according to: {finding.recommendation}",
            "confidence": 0.85 if finding.severity.lower() == "medium" else 0.9,
            "estimated_files_changed": 1,
            "impact_score": 0.7 if estimated_risk == "Low" else (0.85 if estimated_risk == "Medium" else 0.95),
            "estimated_risk": estimated_risk
        }
