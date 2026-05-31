"""
The Pit — native window launcher.
Starts Flask in a background thread, shows a loading splash,
then navigates to the app once Flask is ready.

Run without a console window:
    pythonw.exe launcher.py          (development / shortcut)
    ThePit.exe                       (after PyInstaller build)
"""

import os
import sys
import threading
import time
import urllib.request

import webview

# ── Path setup (handles both dev and PyInstaller frozen builds) ───────────────
if getattr(sys, "frozen", False):
    BUNDLE_DIR = sys._MEIPASS
    APP_DIR    = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR    = BUNDLE_DIR

os.environ["THEPIT_BUNDLE_DIR"] = BUNDLE_DIR
os.environ["THEPIT_APP_DIR"]    = APP_DIR
os.chdir(APP_DIR)

from app import app as flask_app
import db

PORT      = 5000
FLASK_URL = f"http://127.0.0.1:{PORT}"

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
.logo {
  color: #b91c1c;
  font-size: 36px;
  font-weight: 700;
  letter-spacing: 14px;
}
.sub {
  color: #444;
  font-size: 11px;
  letter-spacing: 4px;
  text-transform: uppercase;
  margin-top: 18px;
}
.dot { animation: blink 1.2s infinite; }
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%,80%,100% { opacity:0.2; } 40% { opacity:1; } }
</style>
</head>
<body>
  <div class="logo">THE PIT</div>
  <div class="sub">
    Loading
    <span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>
  </div>
</body>
</html>"""


def start_flask():
    db.init_db()
    flask_app.run(
        host="127.0.0.1",
        port=PORT,
        debug=False,
        use_reloader=False,
    )


def wait_and_navigate():
    """Start Flask, poll until ready, then load the real app."""
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()

    for _ in range(60):          # wait up to 15 seconds
        try:
            urllib.request.urlopen(f"{FLASK_URL}/health", timeout=0.5)
            break
        except Exception:
            time.sleep(0.25)

    window.load_url(FLASK_URL)


if __name__ == "__main__":
    window = webview.create_window(
        title="The Pit",
        html=LOADING_HTML,
        width=1400,
        height=900,
        min_size=(900, 600),
    )
    webview.start(wait_and_navigate, debug=False)
