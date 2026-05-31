@echo off
title Build ThePit.exe
cd /d "%~dp0"

echo.
echo  =============================================
echo    THE PIT  ^|  Building ThePit.exe
echo  =============================================
echo.
echo  This bundles the Flask app + PyWebView into a
echo  standalone .exe you can pin to the taskbar.
echo.
echo  Output: dist\ThePit.exe  (~50-80 MB)
echo.

python -m PyInstaller ThePit.spec --clean --noconfirm

echo.
if exist "dist\ThePit.exe" (
    echo  BUILD SUCCESSFUL
    echo  File: %~dp0dist\ThePit.exe
    echo.
    echo  Copy dist\ThePit.exe to A:\ThePit\ alongside:
    echo    - metal_releases.db
    echo    - .env
    echo    - fetch_releases.py
    echo    - venv\  and  browsers\
    echo.
    echo  Then right-click ThePit.exe ^> Pin to taskbar.
) else (
    echo  BUILD FAILED — see output above for errors.
)
echo.
pause
