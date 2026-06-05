import sys
import os
import builtins

# Force stdout/stderr to UTF-8 so Unicode characters in log lines
# never cause UnicodeEncodeError on Windows (charmap encoding default).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass  # pythonw.exe has no real stdout — safe to ignore
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


# ── Art image proxy ──────────────────────────────────────────────────────────
# Some CDNs (Last.fm, Bandcamp) use hotlink protection: the image returns 403
# when loaded directly from a browser pointing at localhost. Fetching server-side
# with the right Referer bypasses this, then we stream the bytes to the browser.

_PROXY_HOSTS = (
    "lastfm.freetls.fastly.net",  # Last.fm CDN
    "f4.bcbits.com",              # Bandcamp art CDN
)

_PROXY_REFERERS = {
    "lastfm.freetls.fastly.net": "https://www.last.fm/",
    "f4.bcbits.com":             "https://bandcamp.com/",
}


def _proxy_url(url):
    """Return a local proxy URL for CDN hosts known to use hotlink protection."""
    if not url:
        return url
    from urllib.parse import urlparse, quote
    if urlparse(url).netloc in _PROXY_HOSTS:
        return f"/api/art-proxy?url={quote(url, safe='')}"
    return url


@app.route("/api/art-proxy")
def art_proxy():
    """Fetch an external art image server-side and stream it to the browser."""
    import requests as req
    from urllib.parse import urlparse
    url  = request.args.get("url", "").strip()
    host = urlparse(url).netloc if url else ""

    if not url or not url.startswith("https://") or host not in _PROXY_HOSTS:
        return "", 400

    referer = _PROXY_REFERERS.get(host, "https://www.google.com/")
    try:
        resp = req.get(url, timeout=10, headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": referer,
        })
        # Use ASCII-safe arrow to avoid UnicodeEncodeError on Windows console
        print(f"[art-proxy] {host} -> {resp.status_code}", flush=True)
        if resp.status_code == 200:
            from flask import Response
            return Response(
                resp.content,
                content_type=resp.headers.get("Content-Type", "image/jpeg"),
            )
    except Exception as e:
        print(f"[art-proxy] error: {e}", flush=True)
    return "", 404


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


def _enrich_folders(folders):
    """Convert sqlite3.Row objects to plain dicts (no art pre-fetching — done async by JS)."""
    return [dict(f) for f in folders]


@app.route("/lists")
def lists():
    folder_id      = request.args.get("folder", type=int)
    current_folder = None
    if folder_id:
        current_folder = db.get_folder_by_id(folder_id)
        if not current_folder:
            return redirect(url_for("lists"))
        all_lists = db.get_lists_in_folder(folder_id)
    else:
        all_lists = db.get_unassigned_lists()
    all_folders = _enrich_folders(db.get_all_folders())
    return render_template("lists.html",
                           lists=all_lists,
                           folders=all_folders,
                           current_folder=current_folder)


@app.route("/folders")
def folders():
    all_folders = _enrich_folders(db.get_all_folders())
    return render_template("folders.html", folders=all_folders)


@app.route("/folders/<int:folder_id>/art-hint")
def folder_art_hint(folder_id):
    """Return a random release ID from this folder for client-side art loading."""
    conn = db.get_db()
    try:
        row = conn.execute("""
            SELECT r.id
            FROM   releases r
            JOIN   list_releases lr ON r.id = lr.release_id
            JOIN   lists l          ON l.id = lr.list_id
            WHERE  l.folder_id = ?
            ORDER BY RANDOM()
            LIMIT 1
        """, (folder_id,)).fetchone()
        return jsonify({"release_id": row["id"] if row else None})
    except Exception as e:
        print(f"[folder-art] hint error: {e}", flush=True)
        return jsonify({"release_id": None})
    finally:
        conn.close()


@app.route("/folders/new", methods=["POST"])
def folders_new():
    name = request.get_json(silent=True, force=True)
    if name is None:
        name = request.form.get("name", "")
    elif isinstance(name, dict):
        name = name.get("name", "")
    name = str(name).strip()
    if not name:
        return jsonify({"error": "Name required"}), 400
    try:
        folder = db.create_folder(name)
        return jsonify({"ok": True, "folder": {
            "id": folder["id"], "name": folder["name"],
            "color": folder["color"], "list_count": 0,
        }})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/folders/<int:folder_id>/delete", methods=["POST"])
def folders_delete_route(folder_id):
    # Legacy form-based route — kept for safety, redirects to AJAX endpoint behaviour
    db.unassign_lists_from_folder(folder_id)
    db.delete_folder(folder_id)
    flash("Folder deleted — lists moved back to unassigned.", "success")
    return redirect(url_for("folders"))


@app.route("/folders/<int:folder_id>/delete-confirm", methods=["POST"])
def folders_delete_confirm(folder_id):
    """
    AJAX endpoint used by the kawaii delete modal.
    Body: {"delete_lists": true|false}
      true  → soft-delete all lists in the folder, write backup JSON
      false → unassign lists (move to unassigned), keep them
    Always deletes the folder itself.
    """
    data         = request.get_json(silent=True) or {}
    delete_lists = bool(data.get("delete_lists", False))

    folder = db.get_folder_by_id(folder_id)
    if not folder:
        return jsonify({"error": "Folder not found"}), 404

    if delete_lists:
        deleted = db.soft_delete_lists_in_folder(folder_id)
        _write_deleted_lists_backup(deleted)
        print(f"[folder-del] soft-deleted {len(deleted)} lists from folder {folder_id}", flush=True)
    else:
        db.unassign_lists_from_folder(folder_id)
        print(f"[folder-del] unassigned lists from folder {folder_id}", flush=True)

    db.delete_folder(folder_id)
    return jsonify({"ok": True})


def _write_deleted_lists_backup(deleted_dicts):
    """Append newly soft-deleted lists to deleted_lists.json, keeping last 5."""
    if not deleted_dicts:
        return
    import json
    backup_path = os.path.join(os.environ.get("THEPIT_APP_DIR", "."), "deleted_lists.json")
    try:
        if os.path.exists(backup_path):
            with open(backup_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        else:
            existing = []
        existing.extend(deleted_dicts)
        existing = existing[-5:]          # keep only the last 5
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        print(f"[folder-del] backup written to {backup_path}", flush=True)
    except Exception as e:
        print(f"[folder-del] backup error: {e}", flush=True)


@app.route("/lists/<int:list_id>/assign", methods=["POST"])
def list_assign(list_id):
    data      = request.get_json(silent=True) or {}
    folder_id = data.get("folder_id")
    db.assign_list_to_folder(list_id, folder_id)
    print(f"[folders] list {list_id} assigned to folder {folder_id}", flush=True)
    return jsonify({"ok": True})


@app.route("/lists/new", methods=["POST"])
def lists_new():
    # Support both JSON (from the inline picker) and form POST (lists page form).
    # force=True parses JSON regardless of Content-Type quirks in some browsers.
    json_data = request.get_json(force=True, silent=True)
    if json_data is not None:
        name = str(json_data.get("name", "")).strip()
        if not name:
            return jsonify({"error": "Name required"}), 400
        try:
            db.create_list(name, "")
            conn = db.get_db()
            row  = conn.execute("SELECT id FROM lists WHERE name = ?", (name,)).fetchone()
            conn.close()
            print(f"[lists] created via picker: {name!r} id={row['id']}", flush=True)
            return jsonify({"ok": True, "id": row["id"], "name": name})
        except Exception as e:
            print(f"[lists] create error: {e}", flush=True)
            return jsonify({"error": str(e)}), 400

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


def _scrape_subprocess(date_from, date_to):
    """
    Run fetch_releases.py in a fresh subprocess so Playwright gets its own
    main thread and ProactorEventLoop — avoids the NotImplementedError that
    occurs when sync_playwright() is called from a Flask worker thread.
    """
    import subprocess, json, tempfile

    app_dir = os.environ.get("THEPIT_APP_DIR", os.path.dirname(os.path.abspath(__file__)))
    script  = os.path.join(app_dir, "fetch_releases.py")

    # Write output to a temp file so we don't have to parse stdout
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    out_path = tmp.name

    env = os.environ.copy()
    env.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.join(app_dir, "browsers"))

    cmd = [sys.executable, script,
           "--from", date_from, "--to", date_to, "--out", out_path]
    print(f"[scraper] starting subprocess: {' '.join(cmd)}", flush=True)
    print(f"[scraper] PLAYWRIGHT_BROWSERS_PATH={env['PLAYWRIGHT_BROWSERS_PATH']}", flush=True)

    proc = subprocess.run(
        cmd, env=env, cwd=app_dir,
        capture_output=True, text=True, timeout=300,
    )

    # Forward subprocess output to our debug log
    for line in (proc.stdout or "").splitlines()[-20:]:
        print(f"[scraper] {line}", flush=True)
    if proc.stderr:
        for line in proc.stderr.splitlines()[-10:]:
            print(f"[scraper] ERR: {line}", flush=True)

    if proc.returncode != 0:
        raise RuntimeError(
            f"Scraper exited {proc.returncode}: {(proc.stderr or '')[-300:]}"
        )

    try:
        with open(out_path, encoding="utf-8") as f:
            releases = json.load(f)
    finally:
        try:
            os.unlink(out_path)
        except Exception:
            pass

    print(f"[scraper] subprocess returned {len(releases)} releases", flush=True)
    return releases


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
            fetched  = _scrape_subprocess(date_from, date_to)
            inserted = db.insert_releases(fetched)
            flash(
                f"Done — {inserted} new release(s) added "
                f"({len(fetched)} fetched, {len(fetched) - inserted} already in DB).",
                "success",
            )
        except Exception as e:
            import traceback
            print(f"[get_releases] ERROR: {e}", flush=True)
            traceback.print_exc()
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

        print(f"[meta] found: {release['artist']} — {release['album']} (ma_id={release['ma_album_id']})", flush=True)

        # ── Fast path: serve from persisted DB cache ──────────────────────────
        db_cache = db.get_release_art_cache(release_id)
        if db_cache is not None:
            print(f"[meta] db-cache hit: art={'yes' if db_cache['art_url'] else 'none'} "
                  f"bio={'yes' if db_cache['bio'] else 'none'}", flush=True)
            return jsonify({
                "artist":       release["artist"],
                "album":        release["album"],
                "type":         release["type"],
                "genre":        release["genre"],
                "release_date": release["release_date"],
                "art_url":      _proxy_url(db_cache["art_url"]),
                "bio":          db_cache["bio"],
                "cached":       True,
            })

        # ── Slow path: call APIs, then persist result ─────────────────────────
        meta = metadata.get_release_meta(
            release["artist"],
            release["album"],
            ma_album_id=release["ma_album_id"],
        )
        print(f"[meta] api: art={'found' if meta['art_url'] else 'none'} | "
              f"bio={'found' if meta['bio'] else 'none'} | "
              f"in-mem-cached={meta['cached']}", flush=True)

        # Persist (raw URL, not proxied — so proxy logic can change without re-fetching)
        db.save_release_art_cache(release_id, meta["art_url"], meta["bio"])

        return jsonify({
            "artist":       release["artist"],
            "album":        release["album"],
            "type":         release["type"],
            "genre":        release["genre"],
            "release_date": release["release_date"],
            "art_url":      _proxy_url(meta["art_url"]),
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
