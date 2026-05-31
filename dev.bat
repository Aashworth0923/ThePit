@echo off
title The Pit — DEV

echo.
echo  =============================================
echo    THE PIT  ^|  DEV  (C:\  local build)
echo  =============================================
echo.

REM Kill any leftover Flask instance on port 5000
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5000 "') do (
    taskkill /F /PID %%a >nul 2>&1
)

cd /d "%~dp0"

echo  Working directory: %CD%
echo  Database:          %CD%\metal_releases.db
echo  Opening browser in 3 seconds...
echo.
echo  To STOP: close this window or Ctrl+C
echo.

start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:5000"

python app.py
