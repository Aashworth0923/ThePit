import sys
import os
import builtins
from collections import deque
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory, jsonify
import db
import metadata

# ── Server-side log capture ───────────────────────────────────────────────────
# All print() calls anywhere in the app are captured here and exposed
# via /api/logs so the in-app debug panel can display them.
_log_buffer = deque(maxlen=400)
_log_seq    = 0
_orig_print = builtins.print

def _capturing_print(*args, **kwargs):
    global _log_seq
    msg = " ".join(str(a) for a in args)
    _log_seq += 1
    _log_buffer.append({"seq": _log_seq, "level": "log", "msg": msg})
    _orig_print(*args, **kwargs)

builtins.print = _capturing_print

# ── Path setup for PyInstaller frozen builds ──────────────────────────────────
# When packaged as a .exe, templates/static live in the bundle (sys._MEIPASS).
# The database, .env, and external scripts live next to the .exe.
if getattr(sys, "frozen", False):
    _bundle = os.environ.get("THEPIT_BUNDLE_DIR", sys._MEIPASS)
    _data   = os.environ.get("THEPIT_APP_DIR",    os.path.dirname(sys.executable))
    app = Flask(__name__,
                template_folder=os.path.join(_bundle, "templates"),
                static_folder=os.path.join(_bundle, "static"))
else:
    app = Flask(__name__)

app.secret_key = "thepitlocal"


@app.template_filter("fmt_date")
def fmt_date(value):
    """Convert YYYY-MM-DD storage format to MM/DD/YYYY for display."""
    if not value:
        return value
    try:
        from datetime import datetime
        return datetime.strptime(value, "%Y-%m-%d").strftime("%m/%d/%Y")
    except ValueError:
        return value


@app.route("/favicon.ico")
def favicon():
    folder = os.environ.get("THEPIT_APP_DIR", ".")
    return send_from_directory(folder, "ThePit.ico", mimetype="image/x-icon")


@app.route("/health")
def health():
    return "ok", 200


@app.route("/api/logs")
def api_logs():
    since = int(request.args.get("since", 0))
    new_entries = [e for e in _log_buffer if e["seq"] > since]
    return jsonify({"seq": _log_seq, "entries": new_entries})


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/releases")
def releases():
    all_releases = db.get_all_releases()
    type_values  = db.get_release_types()
    return render_template("index.html", releases=all_releases, type_values=type_values)


@app.route("/lists")
def lists():
    all_lists = db.get_all_lists()
    return render_template("lists.html", lists=all_lists)


@app.route("/lists/new", methods=["POST"])
def lists_new():
    name = request.form.get("name", "").strip()
    if not name:
        flash("List name cannot be empty.", "error")
        return redirect(url_for("lists"))
    try:
        db.create_list(name, request.form.get("description", ""))
        flash(f'List "{name}" created.', "success")
    except Exception:
        flash(f'A list named "{name}" already exists.', "error")
    return redirect(url_for("lists"))


@app.route("/lists/<int:list_id>/delete", methods=["POST"])
def lists_delete(list_id):
    db.delete_list(list_id)
    flash("List deleted.", "success")
    return redirect(url_for("lists"))


@app.route("/get-releases", methods=["GET", "POST"])
def get_releases():
    if request.method == "POST":
        date_from = request.form.get("date_from", "").strip()
        date_to   = request.form.get("date_to",   "").strip()

        if not date_from or not date_to:
            flash("Select both a start and end date.", "error")
            return redirect(url_for("get_releases"))
        if date_from > date_to:
            flash("Start date must be before end date.", "error")
            return redirect(url_for("get_releases"))

        try:
            from fetch_releases import run_fetch
            fetched  = run_fetch(date_from, date_to)
            inserted = db.insert_releases(fetched)
            flash(
                f"Done — {inserted} new release(s) added "
                f"({len(fetched)} fetched, {len(fetched) - inserted} already in DB).",
                "success",
            )
        except Exception as e:
            flash(f"Fetch failed: {e}", "error")

        return redirect(url_for("releases"))

    return render_template("get_releases.html")


@app.route("/release/<int:release_id>/meta")
def release_meta(release_id):
    print(f"[meta] request for id={release_id}", flush=True)
    try:
        release = db.get_release_by_id(release_id)
        if not release:
            print(f"[meta] id={release_id} not found in DB", flush=True)
            return jsonify({"error": "Release not found"}), 404

        print(f"[meta] found: {release['artist']} — {release['album']}", flush=True)
        meta = metadata.get_release_meta(release["artist"], release["album"])
        print(f"[meta] art={'found' if meta['art_url'] else 'none'} | "
              f"bio={'found' if meta['bio'] else 'none'} | "
              f"cached={meta['cached']}", flush=True)

        return jsonify({
            "artist":       release["artist"],
            "album":        release["album"],
            "type":         release["type"],
            "genre":        release["genre"],
            "release_date": release["release_date"],
            "art_url":      meta["art_url"],
            "bio":          meta["bio"],
            "cached":       meta["cached"],
        })
    except Exception as e:
        print(f"[meta] ERROR: {e}", flush=True)
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    db.init_db()
    print("The Pit running at http://127.0.0.1:5000")
    app.run(debug=False, port=5000)
