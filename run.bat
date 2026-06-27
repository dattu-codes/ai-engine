@echo off
echo ===================================================
echo   Starting AI Engine Intern Backend Server...
echo ===================================================
echo.

:: Activate the virtual environment
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo [OK] Virtual environment activated.
) else (
    echo [ERROR] Virtual environment 'venv' not found in this folder!
    echo Please make sure you run this script from the project root.
    pause
    exit /b 1
)

echo [OK] Starting Uvicorn server on http://127.0.0.1:8000 ...
echo Press Ctrl+C in this window to stop the server.
echo.

uvicorn app.main:app --reload --port 8000

pause
