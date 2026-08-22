@echo off
setlocal
cd /d "%~dp0"

echo Stopping anything on port 8766...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8766" ^| findstr "LISTENING"') do (
  echo Killing PID %%P
  taskkill /F /PID %%P >nul 2>&1
)

timeout /t 1 /nobreak >nul

if exist "venv\Scripts\python.exe" (
  start "ATE Worker" /MIN "venv\Scripts\python.exe" -m ate.worker.server
) else (
  echo venv\Scripts\python.exe not found
  pause
  exit /b 1
)

echo Worker restarted on http://127.0.0.1:8766
endlocal
