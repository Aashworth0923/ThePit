@echo off
title The Pit — Metal Release Tracker

echo.
echo  =============================================
echo    THE PIT  ^|  Metal Release Tracker
echo  =============================================
echo.

if not exist "A:\ThePit\app.py" (
    echo  ERROR: Encrypted drive not mounted as A:\
    echo.
    echo  Steps to fix:
    echo    1. Open VeraCrypt
    echo    2. Mount your encrypted volume as drive A:\
    echo    3. Run this launcher again
    echo.
    pause
    exit /b 1
)

REM Kill any leftover Flask instance on port 5000 before starting fresh
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5000 "') do (
    taskkill /F /PID %%a >nul 2>&1
)

cd /d A:\ThePit
set PLAYWRIGHT_BROWSERS_PATH=A:\ThePit\browsers

echo  Starting from A:\ThePit ...
echo  Opening browser in 4 seconds...
echo.
echo  To STOP the app: close this window or press Ctrl+C
echo.

start "" cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:5000"

A:\ThePit\venv\Scripts\python.exe app.py
