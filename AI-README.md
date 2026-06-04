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

## V1 — Complete (as of 2026-05-31)

V1 is the first fully working version of the app. All core workflows are functional.

### V1 component inventory

| Component | File(s) | Status |
|---|---|---|
| Database schema (releases + lists + list_releases) | `db.py`, `metal_releases.db` | ✅ |
| Bulk importer (from .txt) | `import_releases.py` | ✅ |
| Metal Archives scraper (Playwright, Cloudflare-safe) | `fetch_releases.py` | ✅ |
| Flask web app + routes | `app.py` | ✅ |
| VS Code-style tab navigation (Home, Releases, Lists) | `base.html`, `style.css` | ✅ |
| Home page (root, placeholder) | `templates/home.html` | ✅ |
| Releases — table, column filters (date/type/genre), checkboxes | `templates/index.html` | ✅ |
| Genre top-level classification (17 buckets, keyword mapping) | `app.py` | ✅ |
| Add selected releases to a named list | `templates/index.html` | ✅ |
| Lists page — create, delete, clickable rows | `templates/lists.html` | ✅ |
| List detail — pending/completed sections, circle/star | `templates/list_detail.html` | ✅ |
| Review sub-panel — play length, rating, notes (per list entry) | `partials/list_item.html` | ✅ |
| Get Releases — date picker + scraper trigger | `templates/get_releases.html` | ✅ |
| Album art + bio on demand (MusicBrainz/CAA + Last.fm) | `metadata.py` | ✅ |
| Slide-out release drawer | `templates/index.html` | ✅ |
| In-app debug log panel (backtick `` ` `` key) | `base.html`, `app.py` | ✅ |
| PyWebView native window + auto-git-pull on open | `launcher.py` | ✅ |
| Dev launcher (C:\, no VeraCrypt) | `dev.bat` | ✅ |
| Production launcher (A:\, Desktop shortcut, auto-update) | `ThePit.bat`, `create_shortcut.ps1` | ✅ |
| PyInstaller build pipeline | `ThePit.spec`, `build.bat` | ✅ |

---

## V2 — In Progress

V2 focuses on polish, usability, and richer content in the list experience.

### V2 changes

| Feature | Status |
|---|---|
| Circle / star sized to ~50% of bar height (28px / 24px) | ✅ Done |
| Slightly larger fonts in list items | ✅ Done |
| Compact / Full view toggle on list detail page | ✅ Done |
| Full view: album art thumbnail + bio inline per item | ✅ Done |
| Last.fm album.getInfo as art fallback (Phase 1 art) | ✅ Done |
| Metal Archives CDN image URL as art fallback (Phase 2) | ✅ Done |
| Store `ma_album_id` from scraper for MA image lookup | ✅ Done |
| Fix Get Releases 500 (stale url_for + subprocess Playwright) | ✅ Done |
| Bandcamp JSON-LD + og:image art fallback (Phase 3) | ✅ Done |
| Image proxy `/api/art-proxy` for CDN hotlink protection | ✅ Done |
| Fix art proxy crash (Unicode `→` in charmap stdout) | ✅ Done |
| Debug log Copy button | ✅ Done |
| Album art lightbox (click thumbnail in full view) | ✅ Done |
| Home page content (TBD) | Planned |
| listened/skipped/queued status on Releases table | Planned |
| Scraper scheduling (cron or in-app button) | Planned |

---

## Current State

### How to run — development (C:\)

1. Open VS Code from `C:\Users\ashwo\OneDrive\Documents\GitHub\ThePit`
2. Double-click **`dev.bat`** inside that folder (or run it from the VS Code terminal)
3. Browser opens at `http://127.0.0.1:5000` — runs against the local dev database
4. Close the window to stop the server

No VeraCrypt mount needed. Uses system Python and the `.env` in `C:\ThePit`.

### How to run — production (A:\)

1. Open VeraCrypt and mount your encrypted volume as **`A:\`** (must always be `A:\`)
2. Double-click **`ThePit.bat`** on the Desktop (`C:\Users\ashwo\Desktop\ThePit.bat`)
3. Browser opens automatically to `http://127.0.0.1:5000`
4. Close the black terminal window to stop the server

Uses `A:\ThePit\venv`, `A:\ThePit\browsers`, and `A:\ThePit\metal_releases.db`.

### One-time data import (existing .txt files)

```bash
# Dev
cd "C:\Users\ashwo\OneDrive\Documents\GitHub\ThePit"
python import_releases.py --txt may_releases_filtered.txt

# Production (A:\)
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

**Claude Code / VS Code sessions always open from `C:\Users\ashwo\OneDrive\Documents\GitHub\ThePit`.** That is the dev workspace. `A:\` only needs to be mounted when running the production app or doing a production update (`git pull`).

---

## Development Workflow

### The three-environment model

```
C:\Users\ashwo\OneDrive\Documents\GitHub\ThePit\   ← DEV (write code here)
        │
        │  git push (code only, never secrets or data)
        ▼
github.com/Aashworth0923/ThePit                    ← BRIDGE (version history + backup)
        │
        │  git pull (updates code files only)
        ▼
A:\ThePit\                                         ← PROD (app runs here, data lives here)
```

| | C:\ Dev | GitHub | A:\ Prod |
|---|---|---|---|
| Python source files | ✓ | ✓ | ✓ (via pull) |
| `.env` (API keys) | ✓ | **never** | ✓ (permanent) |
| `metal_releases.db` | dev copy | **never** | ✓ (permanent) |
| `venv\`, `browsers\` | system Python | **never** | ✓ (permanent) |

---

### A full development session

**1. Open workspace**
Open VS Code → `C:\Users\ashwo\OneDrive\Documents\GitHub\ThePit`
This is the only folder you ever open Claude Code or VS Code from.

**2. Start the dev app**
Double-click `dev.bat` in the folder, or from the VS Code terminal:
```
dev.bat
```
Browser opens at `http://127.0.0.1:5000`. Runs against the local dev database in `C:\ThePit\metal_releases.db`. `A:\` does not need to be mounted.

**3. Make and test changes**
Edit files in VS Code. To pick up changes, close the bat window and re-run it.

For live reload while editing, temporarily set `debug=True` in `app.py`:
```python
app.run(debug=True, port=5000)   # auto-reloads on file save
```
Switch back to `debug=False` before committing.

**4. Commit and push to GitHub**
From the VS Code terminal (or any PowerShell/Git Bash):
```bash
git add .
git commit -m "Short description of what changed"
git push
```
`.env`, `metal_releases.db`, `venv\`, and `browsers\` are all gitignored — they will never be included.

**5. Promote to production**
When ready to use the new version in the real app:
```bash
# 1. Mount VeraCrypt as A:\
# 2. Open any terminal:
cd A:\ThePit
git pull
# 3. Run ThePit.bat from Desktop as normal
```
`git pull` only touches code files. The `.env`, database, venv, and browsers on `A:\` are untouched.

---

### Quick reference

| Task | Command / Action |
|---|---|
| Start dev session | Double-click `dev.bat` in `C:\ThePit` |
| Commit a change | `git add .` → `git commit -m "..."` → `git push` |
| Update production | Mount `A:\` → `cd A:\ThePit` → `git pull` |
| Edit API keys (dev) | Edit `C:\ThePit\.env` |
| Edit API keys (prod) | Edit `A:\ThePit\.env` |
| Open Claude Code | Always from `C:\Users\ashwo\OneDrive\Documents\GitHub\ThePit` |

---

## File Structure

```
ThePit\                         (C:\ = dev workspace  |  A:\ = production)
├── app.py                      # Flask routes — all URL endpoints live here
├── db.py                       # All database reads/writes — one function per operation
├── fetch_releases.py           # Metal Archives scraper (Playwright headless browser)
├── import_releases.py          # One-shot importer for .txt files
├── metadata.py                 # Album art (MusicBrainz/CAA) + bio (Last.fm), cached
├── dev.bat                     # Dev launcher — runs from C:\, no VeraCrypt needed
├── ThePit.jpg                  # App icon / favicon
├── AI-README.md                # This file
├── .env                        # API keys — gitignored, never committed
├── .env.example                # Key template — safe to commit, no real values
├── .gitignore                  # Blocks .env, db, venv, browsers from git
│
├── metal_releases.db           # SQLite database (gitignored — stays local)
├── venv\                       # Python venv (gitignored — A:\ only)
├── browsers\                   # Playwright Chromium (gitignored — A:\ only)
│
├── templates\
│   ├── base.html               # Shared layout — every new page extends this
│   ├── index.html              # Home: releases table, live filter, slide-out drawer
│   └── get_releases.html       # Date picker form → triggers scraper
└── static\
    └── style.css               # Dark theme CSS (no external dependencies)

C:\Users\ashwo\Desktop\
└── ThePit.bat                  # Production launcher — requires A:\ mounted
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
| 2 | **Local App Shell** — Flask app, VS Code tabs, home/releases/lists pages | ✅ Done |
| 2b | **Rich Metadata Drawer** — album art + bio slide-out panel, stream not store | ✅ Done |
| 2c | **Native App** — PyWebView launcher, auto-updater, Desktop shortcut | ✅ Done |
| 3 | **Release Browser / To-Do View** — filters (date, type, genre), Lists tab, debug panel | 🔄 In progress |
| 3 cont | — genre top-level filter, mark listened/skipped/queued, starred, notes per album | Next |
| 4 | **Priority Flagging** — auto-flag by label or genre | Planned |
| 5 | **Scraper Scheduling** — weekly auto-fetch | Planned |
| 6 | **Notes & Ratings** — per-album after listening | Planned |
| 7 | **AI Integration** — Claude API priority scores | Planned |

---

## Filter System

### Architecture
Filters live in an inline panel that appears above the table when a filter icon (▼) in a column header is clicked. No floating/absolute positioning — the panel is in normal page flow so no z-index or overflow clipping issues.

- One panel open at a time (clicking a second filter icon swaps content)
- Save applies and closes; clicking same icon again toggles; Escape closes
- Active filters show as chips below the page header with individual × buttons
- All filters combine with AND logic and with the text search box
- Debug panel: press backtick `` ` `` on any page to see client + server logs

### Filter state (JavaScript)
```javascript
filters = { dateFrom, dateTo, types: [], search: '' }
// date comparison uses YYYY-MM-DD string comparison (stored format)
// display uses MM/DD/YYYY via fmt_date Jinja2 filter
```

### Planned: Top-level Genre Filter
Metal Archives uses compound genre strings (e.g. `Black/Death Metal`, `Melodic Death/Thrash Metal`). A deterministic keyword mapping classifies each release into one or more of 17 top-level buckets for filtering. Implemented as `data-primary-genre` attributes on table rows — no DB schema change needed.

**Top-level genre taxonomy:**

| Top Genre | Keywords to match in genre string |
|---|---|
| Black | `black` |
| Death | `death` |
| Doom/Stoner | `doom`, `stoner` |
| Sludge | `sludge` |
| Electronic/Industrial | `electronic`, `industrial` |
| Experimental/Avant-garde | `avant`, `experimental`, `noise`, `ambient` |
| Folk/Viking/Pagan | `folk`, `viking`, `pagan` |
| Gothic | `gothic` |
| Grindcore | `grindcore`, `grind` |
| Groove | `groove` |
| Heavy | `heavy metal` (exact phrase to avoid matching compound sub-genres) |
| Metalcore/Deathcore | `metalcore`, `deathcore` |
| Power | `power` |
| Progressive | `progressive`, `prog` |
| Speed | `speed` |
| Symphonic | `symphonic` |
| Thrash | `thrash` |

**Coverage on June 2026 sample (242 releases, 122 unique genre strings):**
- Top genres by release count: Black (37), Death (40), Thrash (18), Heavy (17), Power (9), Progressive (15)
- ~95%+ of releases map to at least one top genre
- Compound genres (e.g. Black/Death) correctly map to multiple buckets
- Electronic/Industrial: 0 matches in this sample (rare in MA data)

---

## Rich Metadata: Album Art & Bios (Built — Stream, Not Store)

Clicking any album name in the table opens a slide-out drawer from the right. Art and bio are fetched on demand and **never stored in SQLite** — data stays fresh, DB stays lean.

### API stack (researched and implemented 2026-05-31)

| Source | Used For | Auth | Metal Coverage | Notes |
|---|---|---|---|---|
| **MusicBrainz + Cover Art Archive** | Album art | None required | Good (community-curated) | Free, open, 250/500/1200px options |
| **Last.fm API** | Artist bio/description | Free API key | Decent (skews popular) | 5 req/sec, non-commercial only |
| **Discogs API** | Fallback art + underground coverage | Free token | Strong for indie/underground | 60 req/min authenticated |

**Ruled out:**
- Spotify: Feb 2026 terms require Premium subscription for app owner + 250K MAU for extended quota. Not viable.
- iTunes Search: No auth needed, but very poor underground metal coverage and promotional-only licensing.

### How it works

```
User clicks album name in table
    → JS event delegation fires openDrawer(id, artist, album)
    → Drawer slides in from right, shows loading state
    → fetch('/release/<id>/meta')
        → Flask looks up release in DB by id (includes ma_album_id)
        → metadata.get_release_meta(artist, album, ma_album_id):

            Art fallback chain (first hit wins):
              1. MusicBrainz search → Cover Art Archive (free, open)
              2. Last.fm album.getInfo (have API key, good underground coverage)
              3. Metal Archives CDN /images/{d1}/{d2}/{d3}/{d4}/{id}.jpg
                 (needs ma_album_id stored from scraper; may be Cloudflare-blocked)
              4. Bandcamp JSON-LD (best underground coverage, 1200px images)
                 → slugify artist/album → try {artist}.bandcamp.com/album/{album}
                 → parse <script type="application/ld+json"> for image URL

            Bio: Last.fm artist.getinfo
            Results cached in-process dict for the session

        → Returns JSON: {artist, album, type, genre, release_date, art_url, bio}
    → Drawer renders: art image, type/genre/date tags, bio text
    → Nothing written to SQLite
```

**Scraper subprocess fix:** `run_fetch()` / Playwright cannot run in a Flask worker thread
on Windows (asyncio ProactorEventLoop restriction). Flask now spawns `fetch_releases.py`
as a subprocess via `_scrape_subprocess()` in `app.py`. The child process has its own
main thread and event loop where Playwright works normally.

**Key implementation notes:**
- `data-id`, `data-artist`, `data-album` attributes on each button (not inline onclick) — avoids quoting issues with special characters in band names
- `img.onload` / `img.onerror` wired in JS just before `img.src` is set — avoids firing on empty src at page load
- `AbortController` cancels in-flight requests when a new album is clicked before the previous finishes
- In-process `_cache` dict in `metadata.py` — same artist/album never re-fetched within a session
- All steps emit `[ThePit]` console logs (browser) and `[mb]`/`[caa]`/`[lastfm]`/`[meta]` prints (server) for debugging

---

## Known Limitations & Future Decisions

- **Frontend:** currently browser-based (`http://127.0.0.1:5000`). Can be wrapped with **PyWebView** to become a native desktop window with no browser required. Can be packaged to a `.exe` with PyInstaller.
- **Phone access:** Flask can bind to `0.0.0.0` instead of `127.0.0.1`. On the same WiFi, a phone accesses it at `http://<your-local-ip>:5000`. For remote access, Tailscale is the cleanest option.
- **Date sorting:** `release_date` is stored as `YYYY-MM-DD` (normalised on scraper insert). The legacy .txt import files may have inconsistent formats — sort order may need manual cleanup.
- **Scraper fragility:** Playwright works but is slow (30–60s per fetch). If Metal Archives changes their AJAX URL or parameters, update `AJAX_URL` and `build_ajax_url()` in `fetch_releases.py`.
- **`ma_album_id` backfill:** releases imported from the original .txt files have `ma_album_id = NULL`. The MA CDN image fallback only works for releases scraped via the app (post Phase 2). A one-time backfill script is needed to populate IDs for existing releases.

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

---

## Active Issues (as of 2026-05-31)

### Album art not rendering for some releases

**Status:** In progress.

Some releases that have album art visible on Metal Archives and Bandcamp are showing "No art" in the app. The art IS found by the server (logged as `art=found`) but was silently failing to deliver to the browser.

**Root cause identified and fixed (not yet confirmed working in prod):**
The `/api/art-proxy` route fetched the CDN image successfully (HTTP 200) but then crashed on a `print()` statement containing the Unicode character `→` (U+2192). On Windows with the default `charmap`/cp1252 stdout encoding, this raised a `UnicodeEncodeError` inside the `try` block, which the `except` handler caught — causing the route to return `404` instead of the image bytes. Every proxied Last.fm and Bandcamp image was silently returning 404.

**Fixes applied:**
- Changed `→` to `->` in the art proxy log line
- Added `sys.stdout.reconfigure(encoding='utf-8')` at app startup to prevent this class of bug permanently
- Added `og:image` meta tag as a fallback within the Bandcamp fetcher (JSON-LD was inconsistently populated)
- Added image proxy `/api/art-proxy` for CDN hotlink-protected domains (Last.fm, Bandcamp CDN)

**Remaining gap:** Releases imported from the original .txt files have `ma_album_id = NULL`, so the Metal Archives CDN fallback cannot be used for them. The 4-tier fallback chain (MusicBrainz → Last.fm → MA CDN → Bandcamp) covers most releases once the proxy fix is deployed.

**Next steps if art is still missing after proxy fix:**
- Check debug panel for `[art-proxy] ... -> 200` (proxy working) vs `→ 200` (old broken code still running — needs `git pull` + restart)
- If Bandcamp finds a page (status 200) but `art=none`, the og:image tag may be missing; try fetching the page manually and inspecting its source
- Consider storing art URLs in the DB after first successful fetch to avoid repeated API calls
