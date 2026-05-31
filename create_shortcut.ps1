# Creates Desktop shortcuts for The Pit.
# Run once: right-click -> Run with PowerShell
#
# Creates two shortcuts:
#   "The Pit"       -> production (A:\ThePit, auto-updates from GitHub on open)
#   "The Pit [DEV]" -> dev        (C:\ThePit, no auto-update)

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop    = [Environment]::GetFolderPath("Desktop")
$shell      = New-Object -ComObject WScript.Shell

function Make-Shortcut {
    param($name, $pythonw, $script, $workDir, $icon, $desc)

    $lnk = $shell.CreateShortcut((Join-Path $desktop "$name.lnk"))
    $lnk.TargetPath       = $pythonw
    $lnk.Arguments        = "`"$script`""
    $lnk.WorkingDirectory = $workDir
    $lnk.IconLocation     = "$icon,0"
    $lnk.Description      = $desc
    $lnk.WindowStyle      = 1
    $lnk.Save()
    Write-Host "  Created: $name.lnk" -ForegroundColor Green
}

# ── Production shortcut (A:\ThePit — requires VeraCrypt mounted as A:\) ───────
$prodPythonw = "A:\ThePit\venv\Scripts\pythonw.exe"
$prodScript  = "A:\ThePit\launcher.py"
$prodIcon    = "A:\ThePit\ThePit.ico"
$prodDir     = "A:\ThePit"

if (Test-Path $prodPythonw) {
    Make-Shortcut "The Pit" $prodPythonw $prodScript $prodDir $prodIcon `
        "The Pit - Metal Release Tracker (auto-updates on open)"
} else {
    Write-Host "  SKIP: A:\ not mounted or venv not set up (mount VeraCrypt first)" -ForegroundColor Yellow
}

# ── Dev shortcut (C:\ThePit — always available, no VeraCrypt needed) ──────────
$devPythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue)?.Source
if (-not $devPythonw) {
    $python    = (Get-Command python.exe -ErrorAction SilentlyContinue)?.Source
    if ($python) {
        $devPythonw = Join-Path (Split-Path $python) "pythonw.exe"
    }
}

if ($devPythonw -and (Test-Path $devPythonw)) {
    $devScript = Join-Path $projectDir "launcher.py"
    $devIcon   = Join-Path $projectDir "ThePit.ico"
    Make-Shortcut "The Pit [DEV]" $devPythonw $devScript $projectDir $devIcon `
        "The Pit DEV - runs from C:\ local repo, no auto-update"
} else {
    Write-Host "  SKIP: pythonw.exe not found" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  To pin to taskbar:" -ForegroundColor Yellow
Write-Host "    1. Double-click 'The Pit' on your Desktop to launch it"
Write-Host "    2. While it's running, right-click its icon in the taskbar"
Write-Host "    3. Select 'Pin to taskbar'"
Write-Host ""
pause
