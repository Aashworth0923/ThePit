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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lists (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
            description TEXT,
            created_at  TEXT    DEFAULT (date('now'))
        )
    """)
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


def delete_list(list_id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM lists WHERE id = ?", (list_id,))
        conn.commit()
    finally:
        conn.close()


def insert_releases(releases):
    """
    Insert a list of release dicts (from fetch_releases.py).
    Returns the count of newly inserted rows.
    """
    conn = get_db()
    inserted = 0
    try:
        for r in releases:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO releases
                   (artist, album, type, genre, release_date)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    r["artist"].strip(),
                    r["album"].strip(),
                    r.get("type", "").strip(),
                    r.get("genre", "").strip(),
                    normalize_date(r.get("release_date", "")),
                ),
            )
            if cursor.rowcount == 1:
                inserted += 1
        conn.commit()
    finally:
        conn.close()
    return inserted
