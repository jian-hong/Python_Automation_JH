@echo off
setlocal
cd /d "%~dp0"
if exist "venv\Scripts\pythonw.exe" (
  start "ATE Worker" /MIN "venv\Scripts\pythonw.exe" -m ate.worker.server
) else if exist "venv\Scripts\python.exe" (
  start "ATE Worker" /MIN "venv\Scripts\python.exe" -m ate.worker.server
) else (
  echo venv not found
  pause
  exit /b 1
)
echo Worker started on http://127.0.0.1:8766
endlocal
