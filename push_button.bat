@echo off
cd /d "%~dp0"
set PYTHONW=%~dp0venv\Scripts\pythonw.exe
set PYW=%~dp0Github_Auto\push_button.pyw

if not exist "%PYTHONW%" (
    echo ERROR: venv not found. Run: python install.py
    pause
    exit /b 1
)

if not exist "%PYW%" (
    echo ERROR: push_button.pyw not found in Github_Auto\
    pause
    exit /b 1
)

start "" "%PYTHONW%" "%PYW%"
exit /b 0
