"""
The Pit — native window launcher + auto-updater.

On every launch:
  1. Show animated loading splash
  2. git fetch origin  (check GitHub for new commits)
  3. git pull          (apply them if any found)
  4. Start Flask in background thread
  5. Navigate to the app once Flask is ready

Run without a console window:
    pythonw.exe launcher.py          (via Desktop shortcut)
    ThePit.exe                       (after PyInstaller build — see build.bat)
"""

import os
import sys
import json
import threading
import time
import subprocess
import urllib.request

import webview

# ── Path setup (dev vs PyInstaller frozen) ────────────────────────────────────
if getattr(sys, "frozen", False):
    BUNDLE_DIR = sys._MEIPASS
    APP_DIR    = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR    = BUNDLE_DIR

os.environ["THEPIT_BUNDLE_DIR"]      = BUNDLE_DIR
os.environ["THEPIT_APP_DIR"]         = APP_DIR
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(APP_DIR, "browsers")
os.chdir(APP_DIR)

from app import app as flask_app
import db

PORT      = 5000
FLASK_URL = f"http://127.0.0.1:{PORT}"

# ── Loading splash HTML ───────────────────────────────────────────────────────
LOADING_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body {
  background: #0f0f0f;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  font-family: 'Segoe UI', sans-serif;
  user-select: none;
}
.logo  { color:#b91c1c; font-size:36px; font-weight:700; letter-spacing:14px; }
.status {
  color:#555;
  font-size:11px;
  letter-spacing:3px;
  text-transform:uppercase;
  margin-top:20px;
  min-height:16px;
  transition: color 0.3s;
}
.status.updated { color:#4ade80; }
.status.error   { color:#f87171; }
.dot { animation:blink 1.2s infinite; }
.dot:nth-child(2){ animation-delay:0.2s; }
.dot:nth-child(3){ animation-delay:0.4s; }
@keyframes blink{ 0%,80%,100%{opacity:0.2;} 40%{opacity:1;} }
</style>
</head>
<body>
  <div class="logo">THE PIT</div>
  <div class="status" id="status">
    Starting<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>
  </div>
</body>
</html>"""


# ── Helpers ───────────────────────────────────────────────────────────────────
def _git(*args, timeout=15):
    """Run a git command in APP_DIR. Returns stdout string or empty string on error."""
    try:
        r = subprocess.run(
            ["git", *args],
            capture_output=True, text=True,
            cwd=APP_DIR, timeout=timeout,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _set_status(msg, css_class=""):
    """Update the status line in the loading splash."""
    try:
        js = f"""
        var el = document.getElementById('status');
        el.className = 'status {css_class}';
        el.innerHTML = {json.dumps(msg)};
        """
        window.evaluate_js(js)
    except Exception:
        pass


def _check_and_update():
    """
    Fetch from GitHub, check for new commits, pull if any.
    Returns a summary string of what happened.
    """
    _set_status("Checking for updates...")

    # Fetch latest info from origin (timeout kept short — skip if no internet)
    fetch_out = _git("fetch", "origin", "main", timeout=8)

    # See how many commits we're behind
    behind = _git("log", "HEAD..origin/main", "--oneline")
    if not behind:
        _set_status("Up to date")
        return "up-to-date"

    commits = [l for l in behind.split("\n") if l.strip()]
    n = len(commits)
    label = f"{n} new commit{'s' if n > 1 else ''}"
    _set_status(f"Updating — {label}...")

    # Apply the update
    _git("pull", "origin", "main", timeout=30)
    _set_status(f"Updated ({label})", css_class="updated")
    time.sleep(1.2)   # let the user see the "Updated" confirmation briefly
    return f"updated:{n}"


def _start_flask():
    db.init_db()
    flask_app.run(
        host="127.0.0.1",
        port=PORT,
        debug=False,
        use_reloader=False,
    )


# ── Main launch sequence (runs in background thread via webview.start) ────────
def launch_sequence():
    # Start Flask immediately — runs in parallel with the update check
    flask_thread = threading.Thread(target=_start_flask, daemon=True)
    flask_thread.start()

    # Check for updates while Flask warms up
    try:
        _check_and_update()
    except Exception:
        _set_status("Starting...")   # No internet or git unavailable — proceed normally

    # Wait for Flask to be ready (up to 15 seconds)
    _set_status("Starting...")
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{FLASK_URL}/health", timeout=0.5)
            break
        except Exception:
            time.sleep(0.25)

    window.load_url(FLASK_URL)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    window = webview.create_window(
        title="The Pit",
        html=LOADING_HTML,
        width=1400,
        height=900,
        min_size=(900, 600),
    )
    webview.start(launch_sequence, debug=False)
