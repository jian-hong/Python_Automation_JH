@echo off
cd /d "%~dp0"
set PYTHONW=%~dp0venv\Scripts\pythonw.exe
set PYW=%~dp0Github_Auto\push_button.pyw

if exist "%PYTHONW%" (
    start "" /b "%PYTHONW%" "%PYW%"
    exit /b 0
)
echo WARNING: venv not found. Run python install.py first.
pause
