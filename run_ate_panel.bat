@echo off
setlocal
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" ate_panel.py
) else (
    echo venv not found — run install.py first.
    pause
    exit /b 1
)
endlocal
