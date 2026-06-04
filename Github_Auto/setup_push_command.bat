@echo off
title Setting up push command...
cd /d "%~dp0.."
set REPO_ROOT=%CD%
set "REPO_ROOT_SETUP=%REPO_ROOT%"

echo Creating push.bat in repo root...
(
echo @echo off
echo call "%REPO_ROOT%\Github_Auto\git-push.bat"
) > "%REPO_ROOT%\push.bat"

echo Adding push alias to PowerShell profile...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$repo = $env:REPO_ROOT_SETUP; ^
   $profile_dir = Split-Path $PROFILE; ^
   if (!(Test-Path $profile_dir)) { New-Item -ItemType Directory -Path $profile_dir -Force | Out-Null }; ^
   if (!(Test-Path $PROFILE)) { New-Item -ItemType File -Path $PROFILE -Force | Out-Null }; ^
   $alias = \"function push { & `\"$repo\push.bat`\" }\"; ^
   $content = Get-Content $PROFILE -Raw -ErrorAction SilentlyContinue; ^
   if ($content -notlike '*function push*') { Add-Content -Path $PROFILE -Value $alias }; ^
   Write-Host 'PowerShell profile updated.'"

echo.
echo Done! Close this terminal and open a new one.
echo Then type:  push
echo (works from any folder, no .\ needed)
echo.
if /i not "%~1"=="silent" pause
