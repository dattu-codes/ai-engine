# AI Engine – Self-Healing Code Review & Project Management Platform

A premium, production-ready AI Code Review and Project Management platform built on FastAPI. It allows developers to organize source code into multi-tenant Workspaces and Projects, ingest entire codebases via ZIP archives, Git repositories, or copy-pastes, construct a Semantic Code Graph of cross-file dependencies, run asynchronous AI Code Reviews using Gemini, track issues in a Review Quality Center, apply self-healing AI Fixes, and collaborate in real-time.

---

## Technical Architecture & Core Features

The platform follows clean architecture principles and isolates logic across separate Routes, Services, Repositories, Database Models, and Serializer Schemas.

### 1. Phase 1 – JWT Authentication & Account Security
- **Signup, Login, Profile Guards**: Authenticates requests using bearer JSON Web Tokens (JWT).
- **Password Protection**: Uses `bcrypt` hashing for password storage.
- **Refresh Token Rotation (RTR)**: Features RTR with automatic token reuse detection.
- **Rate Limiting & Account Lockout**: Limits login attempts (max 5/min) and locks accounts temporarily for 15 minutes after 10 consecutive failures.
- **Role-Based Guards**: Distinguishes between standard `user` and `admin` scopes.

### 2. Phase 2 – Project & Repository Ingestion
- **Multi-Tenant Database Design**: Relational SQLAlchemy mappings in SQLite.
- **Clean Sidebar Layout**: A left glassmorphic navigation sidebar to switch between Dashboard, Projects, Versions, Chat, Pull Requests, Semantic Graph, Workspaces, and Quality Center views.
- **ZIP & Paste Ingestion Engine**:
  - In-memory decompressor that extracts ZIP archives, automatically skips trash directories (`.git`, `node_modules`, `venv`, etc.), and filters only supported source code files (`.py`, `.java`, `.js`, `.ts`).
  - Identifies programming languages, tracks file sizes, and records SHA-256 integrity hashes.
- **Ownership Security Guards**: Checks ownership before any project CRUD operations.

### 3. Phase 3 – AI Review Engine & Code Intelligence
- **Prompt Builder Service**: Standardized prompt generator that feeds Gemini code samples and strict rules to output structured JSON.
- **Gemini Live Integration**: Targets the `gemini-2.5-flash` model for high-efficiency code analysis.
- **Offline Mock Simulator**: If a Gemini API Key is not configured, the engine automatically switches to a local mock parser to scan code files for common defects (eval commands, print statements, broad exception silencers, and TODO comments).
- **Code Intelligence Engine**: Automatically maps codebase topology (project type, frameworks, dependencies, entry points, and file priorities) using deterministic AST parsing.

### 4. Phase 4 – Pull Request Review Dashboard
- **PR Ingestion**: Parses Git diff files to run incremental code reviews.
- **Visual Diff Dashboard**: Highlights additions, deletions, and changed lines alongside file selection tabs.
- **Line-Level Comments**: Ingests and renders line-level quality feedback alongside changed code blocks.

### 5. Phase 5 – Semantic Code Graph & Cross-File Analysis
- **Graph Construction**: Deterministically parses files using abstract syntax trees (ASTs) to extract symbols (classes, interfaces, methods, functions, API routes, and imports).
- **Relationship Mapping**: Establishes links representing inheritance, call chains, imports, and definitions.
- **Interactive Visualizer**: Renders an interactive 2D node-link diagram mapping project topology, color-coded by symbol types.

### 6. Phase 6 – AI Fix Engine & Versioning
- **Project Versioning**: Creates baseline and incremental version snapshots of projects upon ingestion or refactoring.
- **Version Control Comparison**: Computes line change metrics, addition/deletion stats, and structural file diffs between versions.
- **Self-Healing Code Refactoring**: Automates code fix proposals, applies selected fixes directly to the workspace filesystem, and allows rollbacks.

### 7. Phase 7 – Review Quality Center
- **Deduplication & Match-Merging**: Match findings across multiple runs by checking file path, category, and line number or explanation/evidence text similarity.
- **Auto-Resolution**: Automatically marks resolved findings upon codebase sync.
- **Suppressions**: Supports ignoring findings with a documented reason.

### 8. Phase 8 – Team Collaboration & Review Workflow
- **Shared Workspaces**: Groups projects and members under a collaborative organization unit.
- **Role-Based Access Control (RBAC)**: Enforces RBAC permissions (`Owner`, `Admin`, `Developer`, `Viewer`) for all API and frontend operations.
- **Discussion Threads**: Threaded live chat and comments directly attached to review findings.
- **Finding Assignment**: Allows assigning issue cards to workspace members.
- **Audit Logging**: Logs all actions (creations, members, analyses, comments, edits, resolves) to a workspace audit timeline.

### 9. Phase 9 – AI Test Generation & Validation Center (v2.5)
- **Automated Test Suite Creation**: Dynamically constructs unit, integration, and regression test suites for every generated code patch.
- **Pytest Sandboxed Executor**: Runs tests in a isolated runner environment, parsing standard stdout and stderr streams.
- **Coverage Analytics**: Programmatically parses test coverage metrics and stores execution metadata in `TestExecution` database tables.

### 10. Phase 10 – Complete Premium SaaS Frontend Redesign (v2.6)
- **Collapsible Side Navigation Cockpit**: Replaced standard top-header margins with a collapsible developer-tools panel layout (`#0F1722`).
- **SaaS Dark Mode Design System**: Standardized styling variables to match world-class developer tools like Linear, GitHub, and Cursor (base background `#0B0F14`, borders `#2A3441`, and accent badges).
- **Split-Screen Authentication Gateway**: Clean Clerk/Stripe-style secure login portal featuring feature checklists, uppercase form controls, and an "Authenticate" trigger.

---

## Project Structure

```
ai-engine/
│
├── app/
│   ├── auth/              # Authentication System (Clean Architecture)
│   │   ├── config/        # JWT / DB configuration & settings
│   │   ├── database/      # SQLite DB connection details
│   │   ├── models/        # SQLAlchemy tables (User, RefreshToken, Session)
│   │   ├── schemas/       # Input validation schemas (Signup, Login, etc.)
│   │   ├── services/      # Password hashing, JWT generation, & rate-limiting
│   │   └── routes/        # Router endpoints (/auth/signup, /auth/login)
│   │
│   ├── projects/          # Project & Workspace System (Clean Architecture)
│   │   ├── models/        # Tables (Project, Workspace, WorkspaceMember, ReviewFinding, Comment, ActivityLog, etc.)
│   │   ├── repositories/  # Database session queries (Repository Pattern)
│   │   ├── schemas/       # Input validators and output serializers
│   │   ├── services/      # Code Graph, AI Fix, Quality, Permissions, Workspaces, and Comments services
│   │   └── routes/        # Endpoints for projects, workspaces, findings, comments, and activities
│   │
│   ├── static/            # Static Web Assets
│   │   ├── index.html     # Main Glassmorphic SPA Dashboard layout
│   │   ├── style.css      # Custom styling rules and variables
│   │   └── app.js         # Event listeners, API fetches, and UI rendering logic
│   │
│   └── main.py            # FastAPI entry point & custom file endpoints
│
├── verify_auth.py         # Automated JWT authentication test script
├── verify_projects.py     # Automated project CRUD and ZIP loader test script
├── verify_review_pipeline.py# Automated AI review engine and report test script
├── verify_versioning.py   # Automated versioning and AI Fix engine test script
├── verify_team_collaboration.py# Automated workspace collaboration and audit log test script
├── requirements.txt
└── README.md
```

---

## Running the Application

### 1. Set Up the Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Activate virtual environment (Mac/Linux)
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Server
```bash
uvicorn app.main:app --port 8000
```

### 4. Access the App
- Open your browser and navigate to: **`http://127.0.0.1:8000/`**
- Interactive API Documentation: **`http://127.0.0.1:8000/docs`**

---

## Running Verification Tests

The platform includes full integration test suites to assert correctness, security, and performance. Ensure the backend server is running on port 8000 before executing tests:

```bash
# 1. Verify Authentication
python verify_auth.py

# 2. Verify Projects
python verify_projects.py

# 3. Verify AI Review Pipeline
python verify_review_pipeline.py

# 4. Verify Versioning & AI Fix Rollbacks
python verify_versioning.py

# 5. Verify Workspace Collaboration, Assignment, and Timeline Audit logs
python verify_team_collaboration.py

# 6. Verify Automated Test Generation & Code Coverage validation
python verify_test_generation.py
```

---

## License

MIT License
