import json
import re
import asyncio
import urllib.request
import urllib.error
from typing import AsyncGenerator, Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.projects.services.retrieval_service import RetrievalService
from app.projects.services.conversation_service import ConversationService
from app.projects.models.project_models import ChatMessage

class ProjectChatService:
    @staticmethod
    async def chat_stream(
        db: Session,
        project_id: int,
        user_query: str,
        api_key: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        Retrieves context, constructs prompt, calls LLM, yields streaming tokens,
        and saves message history with references upon completion.
        """
        # 1. Retrieve codebase context & recent conversation history
        context = RetrievalService.retrieve_context(db, project_id, user_query)
        recent_messages = ConversationService.get_context_history(db, project_id, limit=8)

        # 2. Get project intelligence parameters
        project = context["files"][0].version.project if context["files"] else None
        framework = getattr(project, "framework", None) or "Unknown"
        architecture = getattr(project, "architecture", None) or "Unknown"
        dependencies = getattr(project, "dependencies_json", None) or "[]"
        project_type = getattr(project, "project_type", None) or "Unknown"
        total_lines = getattr(project, "total_lines", 0) or 0

        # Construct version history text
        version_history_text = "No version snapshots available."
        if context["version_history"]:
            version_history_text = "\n".join([
                f"- Version {v.version_number}: {v.summary} (Created: {v.created_at.isoformat()})"
                for v in context["version_history"]
            ])

        # Construct semantic graph text context
        semantic_graph_text = "No semantic code graph context available."
        try:
            from app.projects.models.project_models import SemanticNode, SemanticEdge
            nodes = db.query(SemanticNode).filter(SemanticNode.project_id == project_id).all()
            edges = db.query(SemanticEdge).filter(SemanticEdge.project_id == project_id).all()
            if nodes:
                node_map = {n.id: n for n in nodes}
                nodes_desc = []
                for n in nodes:
                    nodes_desc.append(f"- {n.node_type.upper()}: '{n.name}' in file '{n.file_path}' (lines {n.start_line}-{n.end_line})")
                
                edges_desc = []
                for e in edges:
                    src = node_map.get(e.source_node_id)
                    tgt = node_map.get(e.target_node_id)
                    if src and tgt:
                        edges_desc.append(f"- '{src.name}' ({src.node_type}) {e.relationship} -> '{tgt.name}' ({tgt.node_type})")
                
                semantic_graph_text = "Nodes:\n" + "\n".join(nodes_desc)
                if edges_desc:
                    semantic_graph_text += "\nRelationships:\n" + "\n".join(edges_desc)
        except Exception as ge:
            semantic_graph_text = f"Error retrieving semantic graph: {ge}"

        # Construct findings text from persistent database ReviewFinding model
        try:
            from app.projects.models.project_models import ReviewFinding
            findings = db.query(ReviewFinding).filter(ReviewFinding.project_id == project_id).all()
            findings_text = "No persistent review findings available."
            if findings:
                findings_text = "\n".join([
                    f"- [ID: {f.id}] Category: {f.category} | Severity: {f.severity} | File: {f.file_path}#L{f.line_number} | Title: {f.title} | Status: {f.status} | Description: {f.description} (Assigned to: {f.assigned_to or 'Unassigned'}, Created: {f.created_at.isoformat() if f.created_at else 'Unknown'}, Resolved: {f.resolved_at.isoformat() if f.resolved_at else 'N/A'}, Ignored Reason: {f.ignored_reason or 'N/A'})"
                    for f in findings
                ])
        except Exception as fe:
            findings_text = f"Error loading persistent findings context: {fe}"

        # Construct fix executions history context
        try:
            from app.projects.models.project_models import FixExecution
            fixes = db.query(FixExecution).filter(FixExecution.project_id == project_id).all()
            fixes_text = "No AI Fix executions recorded for this project."
            if fixes:
                fixes_text = "\n".join([
                    f"- [FixExecution ID: {fx.id}] Finding ID: {fx.finding_id} | Status: {fx.status} | "
                    f"AI Model: {fx.ai_model} | Files Modified: {fx.files_modified or '[]'} | "
                    f"Lines Added: {fx.lines_added} | Lines Removed: {fx.lines_removed} | "
                    f"Plan: {fx.fix_plan_json or 'None'} | Patch: {fx.patch_summary or 'None'} | "
                    f"Verification Score: {fx.verification_score if fx.verification_score is not None else 'N/A'} | "
                    f"Failure Reason: {fx.failure_reason or 'None'}"
                    for fx in fixes
                ])
        except Exception as fe:
            fixes_text = f"Error loading fix executions context: {fe}"

        # Construct test executions history context
        try:
            from app.projects.models.project_models import TestExecution
            tests = db.query(TestExecution).filter(TestExecution.project_id == project_id).all()
            tests_text = "No automated test executions recorded for this project."
            if tests:
                tests_text = "\n".join([
                    f"- [TestExecution ID: {t.id}] Fix ID: {t.fix_execution_id} | Status: {t.status} | "
                    f"Language: {t.language} | Framework: {t.framework} | Test Type: {t.test_type} | "
                    f"Total Tests: {t.total_tests} | Passed: {t.passed_tests} | Failed: {t.failed_tests} | "
                    f"Coverage: {t.coverage_percentage}% | Time: {t.execution_time or 0.0}s | "
                    f"Log Summary: {t.execution_log[:200] if t.execution_log else 'None'}..."
                    for t in tests
                ])
        except Exception as te:
            tests_text = f"Error loading test executions context: {te}"

        # Construct repository insights context
        insights_text = "No Repository Insights generated yet."
        try:
            from app.projects.models.project_models import RepositoryInsight, RepositoryInsightHistory
            insight = db.query(RepositoryInsight).filter(RepositoryInsight.project_id == project_id).first()
            if insight:
                strengths = json.loads(insight.strengths_json)
                weaknesses = json.loads(insight.weaknesses_json)
                roadmap = json.loads(insight.roadmap_json)
                
                history = db.query(RepositoryInsightHistory).filter(
                    RepositoryInsightHistory.project_id == project_id
                ).order_by(RepositoryInsightHistory.version_number.asc()).all()
                history_text = ", ".join([f"v{h.version_number}: Score {h.repository_score}" for h in history])
                
                roadmap_items = "\n".join([
                    f"  - Order {r.get('recommended_order')}: {r.get('title')} ({r.get('priority')} priority, effort: {r.get('effort')}, impact: {r.get('business_impact')}, time: {r.get('estimated_time')}) - {r.get('description')}"
                    for r in roadmap
                ])
                
                insights_text = (
                    f"- Overall Repository Score: {insight.repository_score}/100\n"
                    f"- Architecture Quality Score: {insight.architecture_score}/100\n"
                    f"- Security Quality Score: {insight.security_score}/100\n"
                    f"- Testing Quality Score: {insight.testing_score}/100\n"
                    f"- Deployment Readiness Score: {insight.deployment_score}/100\n"
                    f"- Maintainability Score: {insight.maintainability_score}/100\n"
                    f"- Documentation Score: {insight.documentation_score}/100\n"
                    f"- Technical Debt Level: {insight.technical_debt_score}\n"
                    f"- Engineering Maturity Level: {insight.engineering_maturity}\n"
                    f"- Strengths: {', '.join(strengths)}\n"
                    f"- Weaknesses: {', '.join(weaknesses)}\n"
                    f"- Evolution Roadmap:\n{roadmap_items}\n"
                    f"- Score History Trend: {history_text}\n"
                    f"- Assessment Summary: {insight.summary}"
                )
        except Exception as ie:
            insights_text = f"Error loading Repository Insights context: {ie}"

        # Construct source files text context
        source_files_text = "No relevant source files retrieved for this query context."
        if context["files"]:
            source_files_text = ""
            for f in context["files"]:
                source_files_text += f"\n=== File: {f.filename} ({f.language}) ===\n{f.content}\n"

        # 3. Assemble Prompt Template
        system_instructions = (
            "You are a highly experienced Lead Software Architect and technical teammate.\n"
            "Answer the user's question about the software project using ONLY the provided project information, source files context, review reports, and version details.\n\n"
            "Rules:\n"
            "1. Grounding: Answer only from the supplied context. Never invent files, directories, functions, or classes.\n"
            "2. Citations: Cite relevant filenames, classes, and functions. Cite line numbers whenever available in standard format [filename:Lline_no] (e.g. [auth.py:L12]).\n"
            "3. Uncertainty: If you cannot find the answer in the provided context, explain that you do not have enough information and specify what is missing. Do not guess or hallucinate.\n"
            "4. Format: Use clean, professional markdown with syntax highlighted code blocks if writing code.\n"
        )

        context_prompt = (
            f"Project Metadata Context:\n"
            f"- Project Type: {project_type}\n"
            f"- Framework: {framework}\n"
            f"- Architecture: {architecture}\n"
            f"- Dependencies: {dependencies}\n"
            f"- Total Code Lines: {total_lines}\n\n"
            f"Semantic Graph & Architectural Context:\n{semantic_graph_text}\n\n"
            f"Chronological Evolution Versions:\n{version_history_text}\n\n"
            f"Latest AI Review Findings:\n{findings_text}\n\n"
            f"AI Fix Center Executions Context:\n{fixes_text}\n\n"
            f"AI Test Center Executions Context:\n{tests_text}\n\n"
            f"Repository Insights & Evolution Roadmap:\n{insights_text}\n\n"
            f"Relevant Source Files Context:\n{source_files_text}\n"
        )

        # Build prompt payload list (messages history)
        prompt_parts = []
        prompt_parts.append(f"{system_instructions}\n{context_prompt}")
        
        for msg in recent_messages:
            prompt_parts.append(f"{msg.role.upper()}: {msg.content}")
            
        prompt_parts.append(f"USER: {user_query}")
        
        full_prompt = "\n\n".join(prompt_parts)

        # Save user message to database
        ConversationService.add_message(
            db=db,
            project_id=project_id,
            role="user",
            content=user_query,
            referenced_version=context.get("version_number", 1),
            user_id=user_id
        )

        # Log Activity
        try:
            from app.projects.models.project_models import Project
            from app.projects.services.activity_service import ActivityService
            project_obj = db.query(Project).filter(Project.id == project_id).first()
            ActivityService.log_activity(
                db=db,
                workspace_id=project_obj.workspace_id if project_obj else None,
                project_id=project_id,
                user_id=user_id,
                activity_type="Chat Message Sent",
                entity_type="chat",
                entity_id=None,
                description=f"User sent a chat query: '{user_query[:60]}...'"
            )
        except Exception as ae:
            print(f"Error logging chat message activity: {ae}")

        # 4. Stream response candidate generator
        generated_text = ""
        
        if api_key:
            # LIVE MODE: streamGenerateContent call
            model_name = "models/gemini-2.5-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:streamGenerateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            
            data = {
                "contents": [{
                    "parts": [{"text": full_prompt}]
                }]
            }
            req_body = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")

            def _get_stream():
                return urllib.request.urlopen(req, timeout=30)

            try:
                response = await asyncio.to_thread(_get_stream)
                buffer = ""
                yielded_len = 0
                
                # Yield tokens incrementally reading from the thread-bound stream
                while True:
                    chunk = await asyncio.to_thread(response.readline)
                    if not chunk:
                        break
                    
                    buffer += chunk.decode("utf-8")
                    matches = re.findall(r'"text":\s*"((?:[^"\\]|\\.)*)"', buffer)
                    if matches:
                        parts = []
                        for m in matches:
                            try:
                                parts.append(json.loads(f'"{m}"'))
                            except Exception:
                                parts.append(m)
                        cumulative_text = "".join(parts)
                        if len(cumulative_text) > yielded_len:
                            delta = cumulative_text[yielded_len:]
                            yielded_len = len(cumulative_text)
                            generated_text += delta
                            # SSE format output
                            yield f"data: {json.dumps({'text': delta})}\n\n"
                            
            except Exception as e:
                err_msg = f"Gemini stream failure: {str(e)}"
                yield f"data: {json.dumps({'text': err_msg})}\n\n"
                generated_text += err_msg
        else:
            # OFFLINE MOCK SIMULATOR MODE
            await asyncio.sleep(0.5)
            query_lower = user_query.lower()
            ver_num = context.get("version_number", 1)

            if "explain this project" in query_lower or "explain project" in query_lower:
                response_text = (
                    f"This project is a '{framework}' application structured around a '{architecture}' architecture patterns. "
                    f"It defines core routes for API handlers and data access models. The total code volume measures {total_lines} lines "
                    f"and we are currently at Version {ver_num} workspace snapshot state."
                )
            elif "architecture" in query_lower:
                response_text = (
                    f"The project architecture follows a '{architecture}' structure with clean separation of layers. "
                    f"Dependencies are handled via standard configuration files. We can see main handlers registered at the entry point."
                )
            elif "auth" in query_lower or "login" in query_lower or "session" in query_lower:
                response_text = (
                    "The authentication module flow resides inside `app/auth.py` (referenced in [app/auth.py:L12]). It features a "
                    "`check_session(token)` function which inspects session state signatures and validates security credentials."
                )
            elif "db" in query_lower or "database" in query_lower or "model" in query_lower:
                response_text = (
                    "Database models are defined in [app/projects/models/project_models.py:L74] as SQLAlchemy database class schemas. "
                    "It has tables for version control (`project_versions`) and workspace files (`project_version_files`)."
                )
            elif "api documentation" in query_lower or "api doc" in query_lower:
                response_text = (
                    f"# API Documentation v{ver_num}\n\n"
                    f"- `POST /projects/{{id}}/chat`: real-time project chat streaming\n"
                    f"- `GET /projects/{{id}}/versions`: version snapshots history list\n"
                    f"- `POST /projects/{{id}}/versions/apply-fix`: applies AI code fixes"
                )
            elif "api" in query_lower or "route" in query_lower:
                response_text = (
                    "API routes are managed by FastAPI APIRouter handlers. The project exposes version listings, code fixes, "
                    "and project chat endpoints, mounted inside `app/projects/routes/version_routes.py` and `app/projects/routes/chat_routes.py`."
                )
            elif "math" in query_lower or "sum" in query_lower or "calculate" in query_lower:
                response_text = (
                    "The mathematical logic resides inside `app/math.py` (referenced in [app/math.py:L2]). "
                    "It implements the `calculate_sum(a, b)` function to perform addition operations."
                )
            elif "readme" in query_lower:
                response_text = (
                    f"# Project README Documentation\n\n"
                    f"This is a {framework} web service utilizing a {architecture} design pattern.\n\n"
                    f"## Running the code\n"
                    f"Install requirements and run via Uvicorn:\n"
                    f"```bash\nvenv\\Scripts\\python -m uvicorn app.main:app\n```"
                )
            elif "suggest refactoring" in query_lower or "refactor" in query_lower:
                response_text = (
                    "Based on findings, we suggest refactoring the exception ignore handlers: "
                    "replace empty broad `pass` statements in [app/auth.py:L22] with explicit structured logging logging statements."
                )
            elif "version" in query_lower or "changes" in query_lower:
                response_text = (
                    f"Looking at version details, the current state is Version {ver_num}. "
                    f"The recent actions timeline includes: {version_history_text.replace('- ', '')}."
                )
            else:
                response_text = (
                    f"Based on the analysis of the {framework} workspace context, the codebase structure maps out "
                    f"key utility helper handlers for your query. Let me know if you want me to explain any classes or functions."
                )

            # Stream words with delay to simulate real LLM responses
            words = response_text.split(" ")
            for w in words:
                word_chunk = w + " "
                generated_text += word_chunk
                yield f"data: {json.dumps({'text': word_chunk})}\n\n"
                await asyncio.sleep(0.04)

        # 5. Extract citations from full generated response and save assistant message
        citations = ProjectChatService.extract_citations(generated_text, context)
        ConversationService.add_message(
            db=db,
            project_id=project_id,
            role="assistant",
            content=generated_text,
            referenced_files=citations["files"],
            referenced_classes=citations["classes"],
            referenced_functions=citations["functions"],
            referenced_reports=citations["reports"],
            referenced_version=citations["version"],
            user_id=user_id
        )
        yield "data: [DONE]\n\n"

    @staticmethod
    def extract_citations(text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses response text to extract matched file names, classes, functions, reports.
        """
        referenced_files = []
        referenced_classes = []
        referenced_functions = []

        # Find files matching filename boundaries
        for f in context["files"]:
            filename_base = f.filename.split("/")[-1]
            if filename_base in text or f.filename in text:
                referenced_files.append(f.filename)

        # Match PascalCase classes
        classes_found = re.findall(r'\b[A-Z][a-zA-Z0-9_]+\b', text)
        for cls_name in classes_found:
            if cls_name in ["Project", "Analysis", "Report", "ProjectVersion", "ChatMessage", "ProjectVersionFile"] and cls_name not in referenced_classes:
                referenced_classes.append(cls_name)

        # Match camelCase/snake_case functions (followed by optional parens)
        funcs_found = re.findall(r'\b[a-z_][a-z0-9_]+(?=\s*\()', text)
        for fn_name in funcs_found:
            if fn_name not in ["print", "eval", "append", "get", "loads", "dumps", "split"] and fn_name not in referenced_functions:
                referenced_functions.append(fn_name)

        # Referenced version number
        referenced_version = context.get("version_number", 1)

        # Referenced reports
        referenced_reports = []
        if context.get("report"):
            referenced_reports.append(context["report"].id)

        return {
            "files": list(set(referenced_files)),
            "classes": list(set(referenced_classes)),
            "functions": list(set(referenced_functions)),
            "version": referenced_version,
            "reports": referenced_reports
        }
