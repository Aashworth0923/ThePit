import sqlite3
import os
import sys
import argparse

TXT_FILE = "may_releases_filtered.txt"
DB_FILE = "metal_releases.db"


def init_db(conn):
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


def import_releases(txt_path=TXT_FILE, db_path=DB_FILE):
    if not os.path.exists(txt_path):
        sys.exit(f"Error: input file not found: {txt_path}")

    conn = sqlite3.connect(db_path)
    init_db(conn)
    cursor = conn.cursor()

    inserted = 0
    skipped = 0
    errors = 0

    with open(txt_path, encoding="utf-8", errors="replace") as f:
        for i, raw_line in enumerate(f):
            line = raw_line.rstrip("\r\n")
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) < 5:
                print(f"  Line {i + 1}: too few columns ({len(parts)}), skipping")
                errors += 1
                continue

            artist, album, type_, genre, release_date = (
                parts[0], parts[1], parts[2], parts[3], parts[4]
            )
            # parts[5] is timestamp — not stored per schema

            # Skip header row if present
            if i == 0 and artist.lower() in ("artist", "band"):
                continue

            cursor.execute(
                "INSERT OR IGNORE INTO releases (artist, album, type, genre, release_date)"
                " VALUES (?, ?, ?, ?, ?)",
                (artist, album, type_, genre, release_date),
            )
            if cursor.rowcount == 1:
                inserted += 1
            else:
                skipped += 1

    conn.commit()
    conn.close()

    print(f"Import complete -> {db_path}")
    print(f"  Inserted : {inserted}")
    print(f"  Skipped  : {skipped}  (duplicates, safe to re-run)")
    if errors:
        print(f"  Errors   : {errors}  (malformed lines)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import metal releases txt into SQLite")
    parser.add_argument("--txt", default=TXT_FILE, help="Path to tab-separated txt file")
    parser.add_argument("--db",  default=DB_FILE,  help="Path to SQLite database file")
    args = parser.parse_args()

    import_releases(args.txt, args.db)
