# Creates a Desktop shortcut that launches The Pit without a console window.
# Uses pythonw.exe (the console-less Python runner built into every Python install).
# Run this once: right-click create_shortcut.ps1 -> Run with PowerShell

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw    = (Get-Command pythonw.exe -ErrorAction SilentlyContinue)?.Source

if (-not $pythonw) {
    # Fall back: find pythonw.exe next to python.exe
    $python = (Get-Command python.exe).Source
    $pythonw = Join-Path (Split-Path $python) "pythonw.exe"
}

if (-not (Test-Path $pythonw)) {
    Write-Host "ERROR: pythonw.exe not found. Make sure Python is installed." -ForegroundColor Red
    pause
    exit 1
}

$desktop  = [Environment]::GetFolderPath("Desktop")
$lnkPath  = Join-Path $desktop "The Pit.lnk"
$iconPath = Join-Path $projectDir "ThePit.ico"

$shell    = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnkPath)

$shortcut.TargetPath       = $pythonw
$shortcut.Arguments        = "`"$projectDir\launcher.py`""
$shortcut.WorkingDirectory = $projectDir
$shortcut.IconLocation     = "$iconPath,0"
$shortcut.Description      = "The Pit - Metal Release Tracker"
$shortcut.WindowStyle      = 1   # normal window
$shortcut.Save()

Write-Host ""
Write-Host "  Shortcut created: $lnkPath" -ForegroundColor Green
Write-Host ""
Write-Host "  To pin to taskbar:" -ForegroundColor Yellow
Write-Host "    1. Double-click 'The Pit' on your Desktop to launch it"
Write-Host "    2. Right-click its icon in the taskbar"
Write-Host "    3. Select 'Pin to taskbar'"
Write-Host ""
pause
