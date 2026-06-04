import sqlite3
import re
import sys
import os
from datetime import datetime

# When frozen as .exe, database lives next to the executable, not in the bundle
if getattr(sys, "frozen", False):
    _dir = os.environ.get("THEPIT_APP_DIR", os.path.dirname(sys.executable))
    DB_FILE = os.path.join(_dir, "metal_releases.db")
else:
    DB_FILE = "metal_releases.db"


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist yet."""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS releases (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            artist       TEXT    NOT NULL,
            album        TEXT    NOT NULL,
            type         TEXT,
            genre        TEXT,
            release_date TEXT,
            starred      INTEGER DEFAULT 0,
            listened     INTEGER DEFAULT 0,
            rating       INTEGER,
            notes        TEXT,
            UNIQUE(artist, album)
        )
    """)
    # Safe migrations — only add new columns, never drop
    for col, defn in [
        ("ma_album_id", "TEXT"),
        ("art_url",     "TEXT"),   # NULL=never fetched  ''=fetched/not-found  URL=found
        ("bio_text",    "TEXT"),   # NULL or ''=none found  text=found
    ]:
        try:
            conn.execute(f"ALTER TABLE releases ADD COLUMN {col} {defn}")
        except Exception:
            pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS folders (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL UNIQUE,
            color      TEXT    DEFAULT '#7b1c1c',
            created_at TEXT    DEFAULT (date('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lists (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
            description TEXT,
            created_at  TEXT    DEFAULT (date('now'))
        )
    """)
    # Safe migration: add folder_id to lists
    try:
        conn.execute("ALTER TABLE lists ADD COLUMN folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL")
    except Exception:
        pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS list_releases (
            list_id    INTEGER NOT NULL REFERENCES lists(id)    ON DELETE CASCADE,
            release_id INTEGER NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
            added_at   TEXT    DEFAULT (datetime('now')),
            PRIMARY KEY (list_id, release_id)
        )
    """)
    # Migrate list_releases to add review columns (safe on existing databases)
    for col, defn in [
        ("listen_status", "TEXT"),
        ("rating",        "INTEGER"),
        ("thoughts",      "TEXT"),
        ("completed",     "INTEGER DEFAULT 0"),
        ("starred",       "INTEGER DEFAULT 0"),
        ("completed_at",  "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE list_releases ADD COLUMN {col} {defn}")
        except Exception:
            pass  # column already exists — safe to ignore

    conn.commit()
    conn.close()


def normalize_date(date_str):
    """
    Convert scraper dates like 'June 1st, 2026' to '2026-06-01'.
    Leaves already-normalized dates (YYYY-MM-DD) unchanged.
    """
    if not date_str:
        return date_str
    if re.match(r"\d{4}-\d{2}-\d{2}", date_str):
        return date_str
    cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", date_str)
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(cleaned.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str


def get_all_releases():
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM releases ORDER BY release_date, artist"
        ).fetchall()
    finally:
        conn.close()


def get_release_by_id(release_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM releases WHERE id = ?", (release_id,)
        ).fetchone()
    finally:
        conn.close()


def get_release_art_cache(release_id):
    """
    Return persisted art/bio if we have already fetched it for this release.
    Returns None if the release has never been looked up.
    Returns {"art_url": str|None, "bio": str|None} if it has been looked up
    (art_url/bio will be None when the lookup found nothing).
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT art_url, bio_text FROM releases WHERE id = ? AND art_url IS NOT NULL",
            (release_id,)
        ).fetchone()
        if row is None:
            return None   # Never fetched
        return {
            "art_url": row["art_url"]  or None,   # '' → None
            "bio":     row["bio_text"] or None,
        }
    finally:
        conn.close()


def save_release_art_cache(release_id, art_url, bio):
    """
    Persist the result of an art/bio lookup.
    Store empty string '' when nothing was found so future calls skip the APIs.
    Store the raw CDN URL (not the proxied version) so proxy logic can evolve.
    """
    conn = get_db()
    try:
        conn.execute(
            "UPDATE releases SET art_url = ?, bio_text = ? WHERE id = ?",
            (art_url or "", bio or "", release_id),
        )
        conn.commit()
        print(f"[db-art] saved for id={release_id}: "
              f"art={'yes' if art_url else 'none'} "
              f"bio={'yes' if bio else 'none'}", flush=True)
    finally:
        conn.close()


def get_release_types():
    """Return sorted list of distinct type values for filter dropdowns."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT DISTINCT type FROM releases WHERE type != '' ORDER BY type"
        ).fetchall()
        return [r["type"] for r in rows]
    finally:
        conn.close()


# ── Lists ──────────────────────────────────────────────────────────────────────

def get_all_lists():
    conn = get_db()
    try:
        return conn.execute(
            "SELECT l.*, COUNT(lr.release_id) AS release_count "
            "FROM lists l "
            "LEFT JOIN list_releases lr ON l.id = lr.list_id "
            "GROUP BY l.id ORDER BY l.created_at DESC"
        ).fetchall()
    except Exception:
        # list_releases table may not exist yet — return without count
        return conn.execute(
            "SELECT *, 0 AS release_count FROM lists ORDER BY created_at DESC"
        ).fetchall()
    finally:
        conn.close()


def create_list(name, description=""):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO lists (name, description) VALUES (?, ?)",
            (name.strip(), description.strip()),
        )
        conn.commit()
    finally:
        conn.close()


def get_list_by_id(list_id):
    conn = get_db()
    try:
        return conn.execute("SELECT * FROM lists WHERE id = ?", (list_id,)).fetchone()
    finally:
        conn.close()


def get_list_releases(list_id):
    """Return all releases in a list with their review data.
    Sorted: pending (date asc) first, completed (completed_at desc) last."""
    conn = get_db()
    try:
        return conn.execute("""
            SELECT r.id, r.artist, r.album, r.type, r.genre, r.release_date,
                   lr.listen_status, lr.rating, lr.thoughts,
                   COALESCE(lr.completed, 0) AS completed,
                   COALESCE(lr.starred,   0) AS starred,
                   lr.completed_at, lr.added_at
            FROM list_releases lr
            JOIN releases r ON r.id = lr.release_id
            WHERE lr.list_id = ?
            ORDER BY COALESCE(lr.completed, 0) ASC,
                     r.release_date ASC,
                     r.artist ASC
        """, (list_id,)).fetchall()
    finally:
        conn.close()


def update_list_release(list_id, release_id, **fields):
    """Update review fields on a list_releases row. Only touches listed columns."""
    allowed = {"listen_status", "rating", "thoughts", "completed", "starred", "completed_at"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [list_id, release_id]
    conn = get_db()
    try:
        conn.execute(
            f"UPDATE list_releases SET {set_clause} WHERE list_id = ? AND release_id = ?",
            values,
        )
        conn.commit()
    finally:
        conn.close()


def add_releases_to_list(list_id, release_ids):
    """Add a batch of release IDs to a list. Returns count of newly added rows."""
    if not release_ids:
        return 0
    conn = get_db()
    added = 0
    try:
        for rid in release_ids:
            conn.execute(
                "INSERT OR IGNORE INTO list_releases (list_id, release_id) VALUES (?, ?)",
                (list_id, int(rid)),
            )
            if conn.execute("SELECT changes()").fetchone()[0]:
                added += 1
        conn.commit()
    finally:
        conn.close()
    return added


def delete_list(list_id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM lists WHERE id = ?", (list_id,))
        conn.commit()
    finally:
        conn.close()


# ── Folders ────────────────────────────────────────────────────────────────────

_FOLDER_COLORS = [
    "#7b1c1c", "#1a2a6e", "#1a4a2a", "#4a1a6a",
    "#1a4a4a", "#6a3a00", "#4a1a1a", "#1a1a4a",
]


def get_all_folders():
    conn = get_db()
    try:
        return conn.execute("""
            SELECT f.*, COUNT(l.id) AS list_count
            FROM folders f
            LEFT JOIN lists l ON l.folder_id = f.id
            GROUP BY f.id
            ORDER BY f.created_at ASC
        """).fetchall()
    finally:
        conn.close()


def get_folder_art_urls(folder_id, limit=4):
    """Return up to `limit` distinct art URLs from releases in a folder's lists."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT DISTINCT r.art_url
            FROM   releases r
            JOIN   list_releases lr ON r.id   = lr.release_id
            JOIN   lists         l  ON l.id   = lr.list_id
            WHERE  l.folder_id = ?
              AND  r.art_url IS NOT NULL
              AND  r.art_url != ''
            ORDER BY RANDOM()
            LIMIT ?
        """, (folder_id, limit)).fetchall()
        return [r["art_url"] for r in rows]
    finally:
        conn.close()


def get_folder_by_id(folder_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM folders WHERE id = ?", (folder_id,)
        ).fetchone()
    finally:
        conn.close()


def create_folder(name):
    conn = get_db()
    try:
        count = conn.execute("SELECT COUNT(*) FROM folders").fetchone()[0]
        color = _FOLDER_COLORS[count % len(_FOLDER_COLORS)]
        conn.execute(
            "INSERT INTO folders (name, color) VALUES (?, ?)",
            (name.strip(), color),
        )
        conn.commit()
        return conn.execute(
            "SELECT * FROM folders WHERE name = ?", (name.strip(),)
        ).fetchone()
    finally:
        conn.close()


def delete_folder(folder_id):
    """Delete a folder; its lists become unassigned (folder_id = NULL)."""
    conn = get_db()
    try:
        conn.execute("UPDATE lists SET folder_id = NULL WHERE folder_id = ?", (folder_id,))
        conn.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
        conn.commit()
    finally:
        conn.close()


def get_unassigned_lists():
    """Return lists not assigned to any folder, with release counts."""
    conn = get_db()
    try:
        return conn.execute("""
            SELECT l.*, COUNT(lr.release_id) AS release_count
            FROM lists l
            LEFT JOIN list_releases lr ON l.id = lr.list_id
            WHERE l.folder_id IS NULL
            GROUP BY l.id ORDER BY l.created_at DESC
        """).fetchall()
    finally:
        conn.close()


def get_lists_in_folder(folder_id):
    """Return lists assigned to a specific folder, with release counts."""
    conn = get_db()
    try:
        return conn.execute("""
            SELECT l.*, COUNT(lr.release_id) AS release_count
            FROM lists l
            LEFT JOIN list_releases lr ON l.id = lr.list_id
            WHERE l.folder_id = ?
            GROUP BY l.id ORDER BY l.created_at DESC
        """, (folder_id,)).fetchall()
    finally:
        conn.close()


def assign_list_to_folder(list_id, folder_id):
    """Assign list to a folder. Pass folder_id=None to unassign."""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE lists SET folder_id = ? WHERE id = ?",
            (folder_id, list_id),
        )
        conn.commit()
    finally:
        conn.close()


def _extract_ma_id(album_url):
    """Extract the numeric ID from a Metal Archives album URL.
    e.g. .../albums/Acid_Row/Magic/1441159  ->  '1441159'
    """
    if not album_url:
        return None
    last = album_url.rstrip("/").split("/")[-1]
    return last if last.isdigit() else None


def insert_releases(releases):
    """
    Insert a list of release dicts (from fetch_releases.py).
    Returns the count of newly inserted rows.
    """
    conn = get_db()
    inserted = 0
    try:
        for r in releases:
            ma_id = _extract_ma_id(r.get("album_url", ""))
            cursor = conn.execute(
                """INSERT OR IGNORE INTO releases
                   (artist, album, type, genre, release_date, ma_album_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    r["artist"].strip(),
                    r["album"].strip(),
                    r.get("type", "").strip(),
                    r.get("genre", "").strip(),
                    normalize_date(r.get("release_date", "")),
                    ma_id,
                ),
            )
            if cursor.rowcount == 1:
                inserted += 1
        conn.commit()
    finally:
        conn.close()
    return inserted
