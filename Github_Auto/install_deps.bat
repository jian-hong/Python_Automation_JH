@echo off
title Installing dependencies...
cd /d "%~dp0\.."
echo Installing from requirements.txt...
pip install -r requirements.txt
echo.
echo Done. All dependencies installed.
pause
