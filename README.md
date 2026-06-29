# AI Engine – Self-Healing Code Review & Project Management Platform

A premium, production-ready AI Code Review and Project Management platform built on FastAPI. It allows developers to organize source code into multi-tenant Projects, ingest entire codebases via ZIP archives or copy-pastes, run asynchronous AI Code Reviews using Gemini, and inspect detailed visual report cards on a glassmorphic dark-theme dashboard.

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
- **Multi-Tenant Database Design**: Relational SQLAlchemy mappings in SQLite:
  `User` $\rightarrow$ `Project` $\rightarrow$ `Analysis` $\rightarrow$ `AnalysisFile` $\rightarrow$ `Report`.
- **Clean Sidebar Layout**: A left glassmorphic navigation sidebar to switch between the Single Snippet Dashboard and the multi-tenant Projects tab.
- **ZIP & Paste Ingestion Engine**:
  - In-memory decompressor that extracts ZIP archives, automatically skips trash directories (`.git`, `node_modules`, `venv`, `build`, etc.), and filters only supported source code files (`.py`, `.java`, `.js`, `.ts`).
  - Identifies programming languages, tracks file sizes, and records SHA-256 integrity hashes.
- **Ownership Security Guards**: Checks ownership before any project CRUD operations.

### 3. Phase 3A – AI Review Engine (Production MVP)
- **Prompt Builder Service**: Standardized prompt generator that feeds Gemini code samples and strict rules to output structured JSON.
- **Hardcoded Model Logic**: Targets the `gemini-2.5-flash` model for high-efficiency code analysis.
- **Offline Mock Simulator**: If a Gemini API Key is not configured, the engine automatically switches to a local mock parser to scan code files for common defects (eval commands, print statements, broad exception silencers, and TODO comments).
- **Persistence & Polling**: Uses asynchronous execution tasks. The UI polls the run status and renders a comprehensive report card (executive summaries, quality score badges, strengths/weaknesses split grids, recommendations, and an issues catalog).

---

## Project Structure

```
ai-engine/
│
├── app/
│   ├── auth/              # Authentication System (Clean Architecture)
│   │   ├── config/        # JWT / DB configuration & settings
│   │   ├── database/      # SQLite / PostgreSQL DB connection details
│   │   ├── models/        # SQLAlchemy tables (User, RefreshToken, Session)
│   │   ├── schemas/       # Input validation schemas (Signup, Login, etc.)
│   │   ├── services/      # Password hashing, JWT generation, & rate-limiting
│   │   ├── dependencies.py# Route access guards and role authorizations
│   │   └── routes/        # Router endpoints (/auth/signup, /auth/login, etc.)
│   │
│   ├── projects/          # Project & Analysis System (Clean Architecture)
│   │   ├── models/        # Tables (Project, Analysis, AnalysisFile, Report)
│   │   ├── repositories/  # Database session queries (Repository Pattern)
│   │   ├── schemas/       # Input validators and output serializers
│   │   ├── services/      # ZIP processors, prompt builders, and orchestrators
│   │   └── routes/        # Endpoints for projects, uploads, and analyses
│   │
│   ├── engine/            # Phase 1 graph definitions and step runners
│   ├── models/            # Phase 1 schemas
│   ├── workflows/         # Phase 1 modular review nodes and graph workflows
│   │
│   ├── static/            # Static Web Assets
│   │   ├── index.html     # Main dashboard layout
│   │   ├── style.css      # Dark-mode styling rules
│   │   └── app.js         # Event listeners, API fetches, and rendering logic
│   │
│   ├── db.py              # Phase 1 in-memory stores
│   ├── main.py            # FastAPI entry point & custom file endpoints
│   └── registry.py        # Generic node function registry
│
├── auth.db                # Auto-generated SQLite Database
├── run.bat                # Windows quick launcher
├── verify_auth.py         # Automated JWT authentication test script
├── verify_projects.py     # Automated project CRUD and ZIP loader test script
├── verify_analysis.py     # Automated AI review engine and report test script
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
# Via Quick Launcher script (Windows)
.\run.bat

# Or run manually
uvicorn app.main:app --reload --port 8000
```

### 4. Access the App
- Open your browser and navigate to: **`http://127.0.0.1:8000/`**
- Interactive API Documentation: **`http://127.0.0.1:8000/docs`**

---

## Running Verification Tests

The platform includes full integration test suites to assert correctness, security, and performance. Ensure the backend server is running on port 8000 before executing tests:

```bash
# 1. Verify Authentication (JWT token rotation, rate limits, lockouts)
python verify_auth.py

# 2. Verify Projects (ZIP uploading, language parsers, project CRUD)
python verify_projects.py

# 3. Verify AI Reviews (Analysis polling, mock simulations, report saving)
python verify_analysis.py
```

---

## Live vs. Offline Demo Mode

- **Demo/Offline Mode**: Keep the "Gemini API Key" field blank inside the project details panel. The engine will run using the offline AST scanner to review codebases locally.
- **Live Mode**: Paste your Gemini API Key in the API Key input field, and the platform will trigger live reviews using the `gemini-2.5-flash` model.

---

## License

MIT License
