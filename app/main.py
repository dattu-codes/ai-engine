import asyncio
import os
import mimetypes
import app.projects.services.logging_service
from fastapi import FastAPI, HTTPException, Response, Depends

from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.models.schemas import CreateGraphRequest, RunGraphRequest
from app.db import GraphStore, RunStore
from app.workflows.code_review import build_code_review_graph
from app.engine.graph import Graph
from app.engine.runner import Runner

from app.auth.database.connection import Base, engine
from app.auth.routes.auth_routes import auth_router
from app.auth.dependencies import get_current_user

from app.projects.routes.project_routes import project_router
from app.projects.routes.analysis_routes import analysis_router
from app.projects.routes.version_routes import version_router
from app.projects.routes.chat_routes import chat_router
from app.projects.routes.pr_routes import pr_router
from app.projects.routes.review_finding_routes import finding_router
from app.projects.routes.workspace_routes import workspace_router
from app.projects.routes.comment_routes import comment_router
from app.projects.routes.activity_routes import activity_router
from app.projects.routes.fix_routes import fix_router
from app.projects.routes.test_routes import test_router
from app.projects.routes.health_routes import health_router
from app.projects.models.project_models import Project, Analysis, AnalysisFile, Report, ReviewFinding, SemanticNode, SemanticEdge, Workspace, WorkspaceMember, FindingComment, ActivityLog, FixExecution, TestExecution


# Run production diagnostics and environment validation checks on startup
from app.startup_validator import run_startup_validation
run_startup_validation()

# Create database tables automatically on startup
Base.metadata.create_all(bind=engine)

# Start the background job worker daemon thread
from app.projects.services.worker_service import start_worker
start_worker()



# FastAPI app
app = FastAPI(title="Mini Workflow Engine")

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(project_router)
app.include_router(analysis_router)
app.include_router(version_router)
app.include_router(chat_router)
app.include_router(pr_router)
app.include_router(finding_router)
app.include_router(workspace_router)
app.include_router(comment_router)
app.include_router(activity_router)
app.include_router(fix_router)
app.include_router(test_router)
app.include_router(health_router)


# In-memory stores
graph_store = GraphStore()
run_store = RunStore()
runner = Runner(graph_store, run_store)

# Custom static file endpoints to avoid aiofiles/starlette async file dependencies
@app.get("/")
async def read_index():
    path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>AI Engine UI not found.</h1><p>Please create the app/static folder structure.</p>")

@app.get("/static/{file_path:path}")
async def get_static_file(file_path: str):
    path = os.path.join(os.path.dirname(__file__), "static", file_path)
    if os.path.exists(path) and os.path.isfile(path):
        mime_type, _ = mimetypes.guess_type(path)
        with open(path, "rb") as f:
            return Response(content=f.read(), media_type=mime_type)
    raise HTTPException(status_code=404, detail="File not found")

@app.post("/graph/create")
async def create_graph(req: CreateGraphRequest):
    """
    Create a graph from a preset or a provided definition.
    """
    if req.preset == "code_review":
        graph = build_code_review_graph()
    elif req.graph_def:
        graph = Graph.from_dict(req.graph_def)
    else:
        raise HTTPException(status_code=400, detail="provide preset or graph_def")

    graph_id = graph_store.save_graph(graph)
    return {"graph_id": graph_id}


@app.post("/graph/run")
async def run_graph(req: RunGraphRequest):
    """
    Start a run and schedule it asynchronously.
    """
    graph = graph_store.get_graph(req.graph_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="graph not found")

    run_id = run_store.create_run(req.graph_id, req.initial_state)

    # Schedule async execution
    asyncio.create_task(runner.run(run_id))

    return {"run_id": run_id}


@app.get("/graph/state/{run_id}")
async def get_state(run_id: str):
    """
    Get the state of a workflow run.
    """
    run = run_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    return {
        "run_id": run_id,
        "state": run["state"],
        "logs": run["logs"],
        "status": run["status"]
    }
