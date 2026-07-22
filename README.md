# AI Engine – Self-Healing Code Review & Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-8E75B2?logo=googlegemini&logoColor=white)](https://ai.google.dev/)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-Render-brightgreen?logo=render&logoColor=white)](https://ai-engine-0kvf.onrender.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**AI Engine** is an advanced, production-ready AI codebase analysis, self-healing code repair, and test orchestration platform built with **Python & FastAPI**. 

By pairing **deterministic AST (Abstract Syntax Tree) parsing** with **Multi-LLM intelligence (Google Gemini, OpenAI ChatGPT, Anthropic Claude)**, AI Engine goes beyond generic chat assistants—delivering line-level vulnerability scanning, automatic Cursor-style diff patch generation, sandboxed test execution, and full codebase semantic dependency graphs.

---

### 🌐 Links & Demos
* **Live Web Application:** [https://ai-engine-0kvf.onrender.com](https://ai-engine-0kvf.onrender.com)
* **GitHub Repository:** [https://github.com/dattu-codes/ai-engine](https://github.com/dattu-codes/ai-engine)
* **Author:** Dattatreya Teella ([@dattu-codes](https://github.com/dattu-codes))

---

## 🚀 Key Highlights & Core Capabilities

```
+-----------------------------------------------------------------------------------+
|                                  AI ENGINE PLATFORM                               |
+-----------------------------------------------------------------------------------+
|  [ Ingestion Layer ]     -> ZIP Uploads / Git Repositories / Code Editor Input    |
|  [ Static Intelligence ] -> AST Symbol Extractor, Cyclomatic & Security Analyzer  |
|  [ AI Orchestration ]    -> Gemini 2.5/3.5, GPT-4o, Claude 3.5 & AST Offline Engine|
|  [ Self-Healing Fixes ] -> Patch Diff Generator, Compiler Check, 1-Click Rollback |
|  [ Test Center ]         -> Automated Pytest Generation, Sandboxed Coverage Runner |
|  [ Collaboration ]       -> Shared Workspaces, RBAC Roles, Audit Timeline Logs    |
+-----------------------------------------------------------------------------------+
```

### 1. 🛡️ AST-Backed Static Security & Code Intelligence
* **Deterministic AST Scanning:** Parses Python and Go source code using language grammar trees to extract class hierarchies, function signatures, API routes, and imports.
* **Security & Vulnerability Detection:** Identifies execution threats (e.g. `eval()`, `exec()`), hardcoded credentials, unhandled exceptions, SQL injections, and mutex locks without needing an external API key.
* **Metrics Suite:** Programmatically calculates Cyclomatic Complexity, Maintainability Index, and Risk Scores.

### 2. 🤖 Multi-LLM Orchestration Engine
* **Flexible AI Providers:** Seamlessly switch between **Google Gemini 2.5 Flash / 3.5**, **OpenAI GPT-4o**, and **Anthropic Claude 3.5 Sonnet**.
* **Zero-Downtime Offline Fallback:** When no API key is provided, the platform automatically switches to an offline AST-based heuristic simulator to keep development uninterrupted.
* **Context-Aware Prompt Building:** Generates isolated, structured JSON prompts containing codebase topology, framework detection, and security alerts.

### 3. 🔧 AI Fix Center (Self-Healing Code Repairs)
* **Cursor-Style Patch Generation:** Automatically produces unified diff patches addressing detected vulnerabilities, formatting smells, and security risks.
* **Engineering Plan & Risk Score:** Evaluates technical risk rating, root cause, and confidence score before patch approval.
* **Validation & Rollback:** Applies patches directly to workspace files with 1-click revert safety.

### 4. 🧪 AI Test Center & Sandboxed Runner
* **Automated Regression Suite Generation:** Synthesizes complete `pytest` unit test files tailored to verified patches.
* **Sandboxed Execution:** Runs test suites dynamically in isolated sub-processes, extracting stdout, stderr, and failure tracebacks.
* **Coverage Telemetry:** Tracks line coverage percentages, pass/fail ratios, and execution latency.

### 5. 🕸️ Semantic Code Graph Visualizer
* **Cross-File Relationship Mapping:** Visualizes project symbol networks (class inheritance, method call chains, API endpoints).
* **Impact Analysis Engine:** Calculates dependency blast radius for file or symbol modifications before making changes.
* **Circular Dependency Detection:** Highlights import cycles and dead code symbols.

### 6. 🏢 Collaborative Workspaces & Team Governance
* **Multi-Tenant Workspaces:** Organizes engineering projects under shared team spaces.
* **Role-Based Access Control (RBAC):** Supports `Owner`, `Admin`, `Developer`, and `Viewer` permission scopes.
* **Audit Timeline & Discussion Threads:** Tracks workspace operations, finding assignments, and inline discussion comments.

### 7. 💬 Grounded RAG Project Assistant
* **Repository Grounded Chat:** Chat with your codebase via a conversational assistant grounded in local project files and reports.
* **Citation Inspector:** Interactive side panel detailing referenced versions, files, classes, and functions used in every response.

---

## 🏗️ Architecture & Project Structure

```
ai-engine/
├── app/
│   ├── admin/             # Operational telemetry dashboard & admin controls
│   ├── analytics/         # Insights aggregator & metric calculation
│   ├── api/v1/            # Public REST API v1 endpoints
│   ├── auth/              # JWT Security, bcrypt hashing & Session management
│   │   ├── config/        # JWT / DB configuration
│   │   ├── database/      # SQLAlchemy SQLite/PostgreSQL connection
│   │   ├── models/        # Database models (User, Session, ApiKey)
│   │   └── routes/        # Auth endpoints (/signup, /login, /profile)
│   ├── billing/           # Subscription tiers & Stripe gateways
│   ├── projects/          # Core Domain Logic
│   │   ├── models/        # Models (Project, Workspace, Finding, TestExecution)
│   │   ├── repositories/  # DB Data Access Repositories
│   │   ├── services/      # Code Graph, AST Parser, AI Fix, & Chat engines
│   │   └── routes/        # Router endpoints for analysis, chat, and fixes
│   ├── services/          # Multi-LLM Client (Gemini, OpenAI, Anthropic)
│   ├── static/            # Frontend Assets
│   │   ├── index.html     # Monaco-style Single Page App (SPA) Dashboard
│   │   ├── style.css      # Dark-mode Design System & Glassmorphism Tokens
│   │   └── app.js         # Interactive canvas graphs & API integrations
│   ├── config.py          # Environment loader (.env parser)
│   └── main.py            # FastAPI Application Entry point
├── verify_auth.py         # JWT Auth Verification Suite
├── verify_projects.py     # Project Ingestion & ZIP Loader Suite
├── verify_review_pipeline.py# AI Review Engine Test Suite
├── verify_versioning.py   # Version Control & AI Fix Revert Suite
├── .env.example           # Environment Configuration Template
├── requirements.txt       # Python Dependencies
└── README.md
```

---

## ⚡ Quickstart Guide

### 1. Prerequisites
* **Python 3.10+** installed.
* **Git** installed.

### 2. Clone the Repository
```bash
git clone https://github.com/dattu-codes/ai-engine.git
cd ai-engine
```

### 3. Create & Activate Virtual Environment
```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Mac / Linux
python -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env` and add your API keys (Optional for offline AST mode):
```bash
cp .env.example .env
```

Example `.env` file:
```env
DATABASE_URL=sqlite:///./auth.db
JWT_SECRET_KEY=your_jwt_secret_key_here
GEMINI_API_KEY=your_gemini_api_key_here
# OPENAI_API_KEY=your_openai_api_key_here
# ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### 6. Run the FastAPI Development Server
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 7. Access Web Dashboard
Open your browser and navigate to:
* **Interactive SPA Dashboard:** [`http://127.0.0.1:8000/dashboard`](http://127.0.0.1:8000/dashboard)
* **Swagger API Documentation:** [`http://127.0.0.1:8000/docs`](http://127.0.0.1:8000/docs)
* **Marketing Landing Page:** [`http://127.0.0.1:8000/`](http://127.0.0.1:8000/)

---

## 🧪 Verification & Integration Test Suite

The platform includes automated end-to-end integration test scripts to verify platform integrity:

```bash
# Verify JWT Auth, Password Hashing, & Refresh Rotation
python verify_auth.py

# Verify Project Ingestion, Workspace Isolation, & AST Scanning
python verify_projects.py

# Verify AI Review Engine & Quality Score Metrics
python verify_review_pipeline.py

# Verify Versioning, AI Patch Generation, & Rollback Safety
python verify_versioning.py
```

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for details.

---

<p align="center">
  Built by <strong>Dattatreya Teella</strong> using <strong>Python, FastAPI & Google Gemini</strong>.<br>
  © 2026 AI Engine. All rights reserved.
</p>
