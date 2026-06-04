@echo off
title PythonAutomation — Version History
cd /d "%~dp0"
call "%~dp0..\venv\Scripts\activate.bat"
"%~dp0..\venv\Scripts\python.exe" git_helper.py --history
pause
