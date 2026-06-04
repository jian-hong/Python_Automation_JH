@echo off
title PythonAutomation — Git Push
cd /d "%~dp0"

set VENV="%~dp0..\venv\Scripts\activate.bat"
set PIP="%~dp0..\venv\Scripts\pip.exe"
set PYTHON="%~dp0..\venv\Scripts\python.exe"

if not exist %VENV% (
    echo.
    echo ERROR: Virtual environment not found.
    echo Please run install.py first:
    echo   python install.py
    echo.
    pause
    exit /b 1
)

call %VENV%
echo Checking automation dependencies...
%PIP% install requests python-dotenv --quiet --disable-pip-version-check

echo.
%PYTHON% git_helper.py
if errorlevel 1 (
    echo.
    echo Something went wrong. Check the error above.
)
pause
