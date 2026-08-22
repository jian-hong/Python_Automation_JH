@echo off
setlocal
cd /d "%~dp0"
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
echo ATE glass UI launching.
echo Worker: http://127.0.0.1:8766
echo UI:     http://127.0.0.1:5174
endlocal
