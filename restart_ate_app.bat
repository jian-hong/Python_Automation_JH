@echo off
setlocal
cd /d "%~dp0"

echo Stopping ATE worker (8766) and UI (5174)...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8766" ^| findstr "LISTENING"') do (
  echo Killing PID %%P on 8766
  taskkill /F /PID %%P >nul 2>&1
)
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":5174" ^| findstr "LISTENING"') do (
  echo Killing PID %%P on 5174
  taskkill /F /PID %%P >nul 2>&1
)

timeout /t 1 /nobreak >nul 2>&1
if errorlevel 1 ping -n 2 127.0.0.1 >nul

if not exist "venv\Scripts\python.exe" (
  echo venv not found — run install.py first.
  pause
  exit /b 1
)

start "ATE Worker" /MIN "venv\Scripts\python.exe" -m ate.worker.server
set /a _wait=0
:wait_worker
netstat -ano | findstr "LISTENING" | findstr ":8766" >nul
if not errorlevel 1 goto worker_up
set /a _wait+=1
if %_wait% GEQ 15 (
  echo WARNING: worker not listening on 8766 yet — UI may show Failed to fetch until worker is up.
  goto worker_up
)
ping -n 2 127.0.0.1 >nul
goto wait_worker
:worker_up
start "ATE UI" "venv\Scripts\python.exe" ate\ui\dev_server.py
echo ATE restarted.
echo Worker: http://127.0.0.1:8766
echo UI:     http://127.0.0.1:5174
echo Ctrl+F5 the operator console if it was already open.
endlocal
