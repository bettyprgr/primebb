@echo off
chcp 65001 >nul
echo ===== Starting PrimeBB =====
echo.

:: Check .env exists
if not exist ".env" (
    echo [ERROR] .env file not found. Please run setup.bat first.
    pause
    exit /b 1
)

:: Check uv exists
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] uv not found. Please run setup.bat first.
    pause
    exit /b 1
)

:: Create data dir if missing
if not exist "data" mkdir data

echo Starting server at http://localhost:8000
echo Press Ctrl+C to stop.
echo.

uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
