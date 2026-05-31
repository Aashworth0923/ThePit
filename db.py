import sqlite3
import re
from datetime import datetime

DB_FILE = "metal_releases.db"


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the releases table if it doesn't exist yet."""
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
