@echo off
setlocal
cd /d "%~dp0"
echo Starting CodePilot...
where node >nul 2>&1
if errorlevel 1 (
  echo Frontend failed to start.
  echo Check port 5174 and Node/npm installation.
  pause
  exit /b 1
)
node scripts\dev.js
if errorlevel 1 (
  echo.
  echo CodePilot failed to start.
  echo Run npm install in the project root, then try again.
  pause
)
endlocal
