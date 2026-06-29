# AI Engine Intern – Self-Healing Workflow Dashboard

A lightweight, premium workflow orchestration engine built on FastAPI that conducts automated, AI-driven Python code reviews. It features real-time graph visualization, self-healing execution loops, and an interactive, glassmorphic dark-mode web dashboard.

---

## New Feature: Production-Ready JWT Authentication System

We have added a secure, modular, and production-ready JSON Web Token (JWT) Authentication System following Clean Architecture principles:

- **User Signup & Login**: Secure registration and credential validation.
- **Password Hashing**: Uses `bcrypt` for industrial-strength password security.
- **JWT Access Tokens**: Issues short-lived access tokens (15-minute expiry) to secure API routes.
- **Refresh Token Rotation (RTR)**: Implements secure token rotation (7-day expiry) with automatic token reuse detection (to prevent session hijacking).
- **Logout & Session Auditing**: Invalidates tokens and logs logout/session activity in the database.
- **Account Lockout**: Tracks failed attempts and temporarily locks accounts for 15 minutes after 10 consecutive failures.
- **Failed Attempts Rate Limiting**: Limit check of 5 failed logins per minute per IP to prevent brute-force dictionary attacks.
- **Role-Based Access Control**: Configures standard `user` vs. `admin` permissions to protect sensitive API endpoints.
- **Email Stubs**: Prepares models and route endpoints for verification/reset password emails.

---

## Key Features

- **Interactive Visual Dashboard**: Input source code, tweak quality thresholds, watch pipeline stages execute in real-time, inspect security warnings, and review syntax-highlighted code recommendations.
- **Dual Review Engines**:
  - **Live API Mode**: Connects directly to the Gemini 1.5 Flash or Pro model for logical bug audits, security assessments, and custom refactoring.
  - **Offline AST Mode**: Uses Python's standard `ast` (Abstract Syntax Tree) module to structurally parse functions and run static code reviews locally with zero configuration.
- **Self-Healing Loop Routing**: If the estimated code quality score falls below the configured threshold on the first pass, the backend refactors the code and automatically loops back to the start node to re-verify the codebase's final quality.
- **Retro Log Terminal**: Displays real-time, chronological execution step logs synced directly with backend timestamps.

---

## Tech Stack

- **Backend**: FastAPI, Python 3.10+, Pydantic, SQLAlchemy, PyJWT, bcrypt
- **AI Integration**: Google Gemini API (standard HTTP/JSON client)
- **Frontend**: HTML5, Vanilla CSS, Javascript (Prism.js CDN for code highlighting)

---

## Project Structure

```
ai-engine-intern/
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
│   ├── engine/
│   │   ├── graph.py       # Graph and node structure definitions
│   │   └── runner.py      # Async graph step runner with logging
│   │
│   ├── models/
│   │   └── schemas.py     # Pydantic API request schemas
│   │
│   ├── services/
│   │   └── ai.py          # Gemini API client & offline AST simulator
│   │
│   ├── static/
│   │   ├── index.html     # Dashboard layout page
│   │   ├── style.css      # Glassmorphic dark-theme styles
│   │   └── app.js         # Frontend state, polling, & UI event listeners
│   │
│   ├── workflows/
│   │   └── code_review.py # Modular review nodes & self-healing logic
│   │
│   ├── db.py              # In-memory stores for graphs and executions
│   ├── main.py            # FastAPI entry point & custom file endpoints
│   └── registry.py        # Generic node function registry
│
├── auth.db                # Auto-generated SQLite Database
├── verify_auth.py         # Automated integration verification test script
├── run.bat                # Windows quick launcher
├── README.md
└── requirements.txt
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

To verify that the authentication system is operating correctly under load and adhering to security parameters:
1. Ensure the backend server is running on port 8000.
2. Run the integration test suite:
   ```bash
   python verify_auth.py
   ```
3. All tests (signup, login, role restrictions, rate limit lockout, token rotation, reuse check, and logout) will run sequentially and verify successful responses.

---

## Live vs. Offline Demo Mode

- **Demo Mode**: Keep the "Gemini API Key" field blank. The dashboard will run fully locally using the AST simulator to perform reviews.
- **Live Mode**: Paste your Gemini API Key in the Engine Configuration panel, select your model, and run reviews. Keys are passed safely in the request payload.

---

## License

MIT License
