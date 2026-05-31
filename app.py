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

# ── Genre taxonomy ────────────────────────────────────────────────────────────
# Each entry: (display_name, slug, [keywords_to_match_in_genre_string])
# Keyword matching is case-insensitive substring search.
GENRE_MAP = [
    ("Black",                  "black",        ["black"]),
    ("Death",                  "death",        ["death"]),
    ("Doom / Stoner",          "doom-stoner",  ["doom", "stoner"]),
    ("Sludge",                 "sludge",       ["sludge"]),
    ("Electronic / Industrial","electronic",   ["electronic", "industrial"]),
    ("Experimental",           "experimental", ["avant", "experimental", "noise"]),
    ("Folk / Viking / Pagan",  "folk",         ["folk", "viking", "pagan"]),
    ("Gothic",                 "gothic",       ["gothic"]),
    ("Grindcore",              "grindcore",    ["grindcore"]),
    ("Groove",                 "groove",       ["groove"]),
    ("Heavy",                  "heavy",        ["heavy metal"]),
    ("Metalcore / Deathcore",  "metalcore",    ["metalcore", "deathcore"]),
    ("Power",                  "power",        ["power"]),
    ("Progressive",            "progressive",  ["progressive", "prog"]),
    ("Speed",                  "speed",        ["speed"]),
    ("Symphonic",              "symphonic",    ["symphonic"]),
    ("Thrash",                 "thrash",       ["thrash"]),
]

def _map_primary_genres(genre_str):
    """Return space-separated slugs for the top-level genres that match."""
    if not genre_str:
        return ""
    lower = genre_str.lower()
    slugs = []
    for _, slug, keywords in GENRE_MAP:
        if any(kw in lower for kw in keywords):
            slugs.append(slug)
    return " ".join(slugs)


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


@app.template_filter("primary_genres")
def primary_genres_filter(genre_str):
    """Return space-separated top-level genre slugs for a raw genre string."""
    return _map_primary_genres(genre_str)


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
    all_lists    = db.get_all_lists()
    genre_map    = [(display, slug) for display, slug, _ in GENRE_MAP]
    return render_template("index.html",
                           releases=all_releases,
                           type_values=type_values,
                           lists=all_lists,
                           genre_map=genre_map)


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


@app.route("/lists/<int:list_id>/view")
def list_detail(list_id):
    lst = db.get_list_by_id(list_id)
    if not lst:
        flash("List not found.", "error")
        return redirect(url_for("lists"))
    releases = db.get_list_releases(list_id)
    return render_template("list_detail.html", lst=lst, releases=releases)


@app.route("/lists/<int:list_id>/release/<int:release_id>/update", methods=["POST"])
def list_release_update(list_id, release_id):
    data    = request.get_json(silent=True) or {}
    updates = {}
    if "listen_status" in data:
        updates["listen_status"] = data["listen_status"] or None
    if "rating" in data:
        updates["rating"] = int(data["rating"]) if data["rating"] is not None else None
    if "thoughts" in data:
        updates["thoughts"] = data["thoughts"] or None
    if "completed" in data:
        completed = 1 if data["completed"] else 0
        updates["completed"] = completed
        if completed:
            from datetime import datetime
            updates["completed_at"] = datetime.now().strftime("%Y-%m-%d")
        else:
            updates["completed_at"] = None
    if "starred" in data:
        updates["starred"] = 1 if data["starred"] else 0
    if updates:
        db.update_list_release(list_id, release_id, **updates)
        print(f"[list] updated release {release_id} in list {list_id}: {list(updates.keys())}", flush=True)
    return jsonify({"ok": True})


@app.route("/lists/<int:list_id>/add", methods=["POST"])
def lists_add(list_id):
    data        = request.get_json(silent=True) or {}
    release_ids = data.get("release_ids", [])
    if not release_ids:
        return jsonify({"error": "No release IDs provided"}), 400
    added = db.add_releases_to_list(list_id, release_ids)
    print(f"[lists] added {added} releases to list {list_id}", flush=True)
    return jsonify({"added": added})


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
