@echo off
chcp 65001 >nul
echo ===== PrimeBB Setup =====
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found.
    echo Please install Python 3.11+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Install uv if not present
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing uv...
    pip install uv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install uv.
        pause
        exit /b 1
    )
)

:: Create data directory
if not exist "data" mkdir data

:: Copy .env if not exists
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo.
    echo [!] Created .env from .env.example
    echo [!] Please open .env and fill in your settings before running start.bat
    echo.
    notepad .env
)

:: Install Python dependencies
echo Installing Python dependencies...
uv sync
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

:: Install Playwright Chromium
echo Installing Playwright browser...
uv run playwright install chromium
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Playwright browser.
    pause
    exit /b 1
)

echo.
echo ===== Setup complete! =====
echo Run start.bat to launch PrimeBB.
echo.
pause
