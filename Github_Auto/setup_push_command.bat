@echo off
echo Setting up push command for this repo...
set REPO_ROOT=%~dp0..
set BAT_PATH=%~dp0git-push.bat

rem Create a push.bat in the repo root so typing "push" works
echo @echo off > "%REPO_ROOT%\push.bat"
echo call "%BAT_PATH%" >> "%REPO_ROOT%\push.bat"

rem Add repo root to PATH for this session only (optional)
echo.
echo Done! You can now type:
echo   .\push      in PowerShell
echo   push        in Command Prompt (from repo root)
echo.
echo To make it work system-wide, add this folder to your PATH:
echo   %REPO_ROOT%
pause
