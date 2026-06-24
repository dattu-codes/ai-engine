# AI Engine Intern – Self-Healing Workflow Dashboard

A lightweight, premium workflow orchestration engine built on FastAPI that conducts automated, AI-driven Python code reviews. It features real-time graph visualization, self-healing execution loops, and an interactive, glassmorphic dark-mode web dashboard.

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

- **Backend**: FastAPI, Python 3.10+, Pydantic
- **AI Integration**: Google Gemini API (standard HTTP/JSON client)
- **Frontend**: HTML5, Vanilla CSS, Javascript (Prism.js CDN for code highlighting)

---

## Project Structure

```
ai_engine_intern/
│
├── app/
│   ├── engine/
│   │   ├── graph.py       # Graph and node structure definitions
│   │   └── runner.py      # Async graph step runner with timestamped logging
│   │
│   ├── models/
│   │   └── schemas.py     # Pydantic API request schemas
│   │
│   ├── services/
│   │   └── ai.py          # Gemini API client & offline AST simulator
│   │
│   ├── static/
│   │   ├── index.html     # Dashboard layout page
│   │   ├── style.css      # Glassmorphic dark-theme styles & animations
│   │   └── app.js         # Frontend state, polling, & UI event listeners
│   │
│   ├── workflows/
│   │   └── code_review.py # Modular review nodes & self-healing logic
│   │
│   ├── db.py              # In-memory stores for graphs and executions
│   ├── main.py            # FastAPI entry point & custom file endpoints
│   └── registry.py        # Generic node function registry
│
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
uvicorn app.main:app --reload
```

### 4. Access the App
- Open your browser and navigate to: **`http://127.0.0.1:8000/`**
- Interactive API Documentation: **`http://127.0.0.1:8000/docs`**

---

## Live vs. Offline Demo Mode

- **Demo Mode**: Keep the "Gemini API Key" field blank. The dashboard will run fully locally using the AST simulator to perform reviews.
- **Live Mode**: Paste your Gemini API Key in the Engine Configuration panel, select your model, and run reviews. Keys are passed safely in the request payload.

---

## License

MIT License
