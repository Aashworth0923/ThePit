# The Pit — AI Project Context & Documentation

> This file is written for both human reading and AI tool context (Claude Code, Cursor, etc.).
> It describes the project state, decisions made, and where to go next.

---

## What This Is

A personal, local desktop app for tracking weekly metal music releases.

**The workflow:**
1. Fetch new releases from Metal Archives for a date range (via a headless browser scraper)
2. Releases are stored in a local SQLite database (`metal_releases.db`)
3. Open the app, see all releases as a filterable table
4. Mark albums as listened / starred / rated as you work through them each week

**Non-commercial, personal use. No auth, no multi-user, no server.**

---

## Current State (as of 2026-05-31)

### What is built and working

| Component | File(s) | Status |
|---|---|---|
| Database schema | `db.py`, `metal_releases.db` | Done |
| Bulk importer (from .txt) | `import_releases.py` | Done |
| Metal Archives scraper | `fetch_releases.py` | Done |
| Flask web app | `app.py` | Done |
| Home page — releases table | `templates/index.html` | Done |
| Get Releases page — date picker | `templates/get_releases.html` | Done |
| Dark theme UI | `static/style.css` | Done |

### How to run (canonical — from encrypted drive)

1. Open VeraCrypt and mount your encrypted volume as **`A:\`** (must always be `A:\`)
2. Double-click **`ThePit.bat`** on the Desktop (lives at `C:\Users\ashwo\Desktop\ThePit.bat`)
3. Browser opens automatically to `http://127.0.0.1:5000`
4. Close the black terminal window to stop the server

The `.bat` file activates the `A:\ThePit\venv` Python environment, sets `PLAYWRIGHT_BROWSERS_PATH=A:\ThePit\browsers`, and starts Flask from `A:\ThePit`.

### One-time data import (existing .txt files)

```bash
cd A:\ThePit
A:\ThePit\venv\Scripts\python import_releases.py --txt may_releases_filtered.txt
```

---

## Storage & Portability

The project lives entirely on an **encrypted VeraCrypt volume mounted as `A:\`**. Nothing sensitive is on the main computer.

| Location | Contents |
|---|---|
| `A:\ThePit\` | All source code, database, templates, CSS, icon |
| `A:\ThePit\venv\` | Python virtual environment (all packages self-contained) |
| `A:\ThePit\browsers\` | Playwright Chromium (~300MB, required for scraper) |
| `A:\ThePit\metal_releases.db` | The SQLite database — your data |
| `C:\Users\ashwo\Desktop\ThePit.bat` | Desktop launcher (not sensitive — just a shortcut) |
| `C:\...\Python312\` | Python interpreter — must stay on main computer |

**Drive letter must always be `A:\`.** The `.bat` launcher and `PLAYWRIGHT_BROWSERS_PATH` are hardcoded to `A:\`. If you ever need a different letter, edit all `A:\` references in `ThePit.bat`.

**Continuing development in Claude Code:** Open Claude Code sessions from `A:\ThePit` (not the old `C:\Users\ashwo\OneDrive\Documents\GitHub\ThePit` copy). The C:\ copy can be deleted once confirmed working.

---

## File Structure

```
A:\ThePit\
├── app.py                  # Flask routes — all URL endpoints live here
├── db.py                   # All database reads/writes — one function per operation
├── fetch_releases.py       # Metal Archives scraper (Playwright headless browser)
├── import_releases.py      # One-shot importer for .txt files
├── metal_releases.db       # SQLite database (single file, the whole DB)
├── ThePit.jpg              # App icon / favicon
├── AI-README.md            # This file
├── venv\                   # Python virtual environment (self-contained on drive)
├── browsers\               # Playwright Chromium browser (self-contained on drive)
├── templates\
│   ├── base.html           # Shared layout — every page extends this
│   ├── index.html          # Home: releases table with live text filter
│   └── get_releases.html   # Date picker form → triggers scraper
└── static\
    └── style.css           # Dark theme CSS (no external dependencies)
```

---

## Tech Stack & Why

| Layer | Choice | Why |
|---|---|---|
| Database | SQLite (`metal_releases.db`) | Single file, zero config, Python built-in, handles 100k+ rows easily |
| Backend | Python / Flask | Same language as the scraper, no build step, trivial to extend |
| Scraper | Playwright (headless Chromium) | Metal Archives is behind Cloudflare — requires a real browser |
| Frontend | Jinja2 HTML templates | No build step, no Node.js, works for a personal local tool |
| Styling | Vanilla CSS | No CDN dependencies, loads instantly, easy to modify |

---

## Database Schema

**Table: `releases`**

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| artist | TEXT | |
| album | TEXT | |
| type | TEXT | Full-length, EP, Demo, etc. |
| genre | TEXT | |
| release_date | TEXT | Stored as YYYY-MM-DD (normalised on insert) |
| starred | INTEGER | 0/1 — priority flag |
| listened | INTEGER | 0/1 — tracking flag |
| rating | INTEGER | Nullable, 1–10 |
| notes | TEXT | Nullable, personal notes |

`UNIQUE(artist, album)` — prevents duplicates on re-fetch. `INSERT OR IGNORE` is used throughout.

---

## How the Scraper Works

1. `fetch_releases.py` launches a headless Chromium browser (via Playwright)
2. Navigates to `metal-archives.com/release/upcoming` — this passes Cloudflare's JS challenge
3. Makes AJAX calls to `metal-archives.com/release/ajax-upcoming/json/1` from within the browser context (inheriting the Cloudflare clearance cookies)
4. Paginates at 100 records/request with a 3-second delay between pages (respects `robots.txt` Crawl-delay)
5. Returns a list of dicts: `{artist, album, type, genre, release_date, artist_url, album_url}`

**Calling it from Flask:** `from fetch_releases import run_fetch` → `releases = run_fetch(date_from, date_to)`

**Calling it from the CLI:** `python fetch_releases.py --from 2026-06-01 --to 2026-06-30`

---

## Adding New Features (for AI context)

The architecture is intentionally simple and additive:

- **New page:** add a route in `app.py` + a template in `templates/` that `{% extends "base.html" %}`
- **New DB operation:** add a function to `db.py`, import it in `app.py`
- **New column/data:** add the column to the schema in `db.py:init_db()`, update `insert_releases()`
- **New CSS:** add to `static/style.css` using the existing CSS variable set in `:root {}`

---

## Epic Roadmap

Epics are numbered in intended build order:

| # | Epic | Status |
|---|---|---|
| 1 | **Data Ingestion** — import .txt files, scraper from Metal Archives | ✅ Done |
| 2 | **Local App Shell** — Flask app, home table, get releases page | ✅ Done |
| 3 | **Release Browser / To-Do View** — filter by type/genre/date, mark listened/skipped/queued | Next |
| 4 | **Priority Flagging** — star releases, auto-flag by label or genre | Planned |
| 5 | **Scraper Scheduling** — weekly auto-fetch via cron or in-app refresh | Planned |
| 6 | **Notes & Ratings** — per-album after listening | Planned |
| 7 | **AI Integration** — Claude API auto-researches releases, writes priority scores | Planned |

---

## Rich Metadata: Album Art & Bios (Planned — Stream, Not Store)

The plan is to display album art and artist/album descriptions when a user clicks a release — fetched on demand, **not stored in SQLite**. This keeps the DB lean and the data always fresh.

### Recommended API stack (researched 2026-05-31)

| Source | Used For | Auth | Metal Coverage | Notes |
|---|---|---|---|---|
| **MusicBrainz + Cover Art Archive** | Album art | None required | Good (community-curated) | Free, open, 250/500/1200px options |
| **Last.fm API** | Artist bio/description | Free API key | Decent (skews popular) | 5 req/sec, non-commercial only |
| **Discogs API** | Fallback art + underground coverage | Free token | Strong for indie/underground | 60 req/min authenticated |

**Ruled out:**
- Spotify: Feb 2026 terms require Premium subscription for app owner + 250K MAU for extended quota. Not viable.
- Bandcamp: No public API. Scraping is legal gray area.
- iTunes Search: No auth needed, high-quality art, but very poor underground metal coverage.

### Architecture (stream not store)

```
User clicks release
    → Flask route: GET /release/<id>/meta
    → Try MusicBrainz for album art URL
    → Try Last.fm for artist bio
    → Return JSON to frontend
    → Frontend renders art + bio in a slide-out panel
    → Nothing written to SQLite
```

A simple in-memory cache (`functools.lru_cache` or a Python dict) prevents re-fetching the same release during a session.

**What gets stored in SQLite:** nothing new. Art URLs and bios are transient.
**What gets displayed:** art image (via `<img src="...">` pointing at Cover Art Archive CDN), Last.fm bio text.

---

## Known Limitations & Future Decisions

- **Frontend:** currently browser-based (`http://127.0.0.1:5000`). Can be wrapped with **PyWebView** to become a native desktop window with no browser required. Can be packaged to a `.exe` with PyInstaller.
- **Phone access:** Flask can bind to `0.0.0.0` instead of `127.0.0.1`. On the same WiFi, a phone accesses it at `http://<your-local-ip>:5000`. For remote access, Tailscale is the cleanest option.
- **Date sorting:** `release_date` is stored as `YYYY-MM-DD` (normalised on scraper insert). The legacy .txt import files may have inconsistent formats — sort order may need manual cleanup.
- **Scraper fragility:** Playwright works but is slow (30–60s per fetch). If Metal Archives changes their AJAX URL or parameters, update `AJAX_URL` and `build_ajax_url()` in `fetch_releases.py`.

---

## Dependencies

### Running from A:\ (normal usage)
All packages are in `A:\ThePit\venv` — no separate install needed. The `.bat` launcher activates this automatically.

### Setting up on a new machine (if re-installing)
```bash
python -m venv A:\ThePit\venv
A:\ThePit\venv\Scripts\pip install flask playwright beautifulsoup4 requests cloudscraper
set PLAYWRIGHT_BROWSERS_PATH=A:\ThePit\browsers
A:\ThePit\venv\Scripts\python -m playwright install chromium
```

Python 3.12 must be installed on the host computer.
