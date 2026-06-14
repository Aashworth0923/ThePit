# The Pit — AI Project Context & Documentation

> This file is written for both human reading and AI tool context (Claude Code, Cursor, etc.).
> Read this first in any new session — it should be enough to understand what the app
> is, how it's built, where things live, and what's already done vs. planned.

---

## What This Is

A personal, local desktop app for tracking weekly metal music releases.

**The workflow:**
1. Fetch new releases from Metal Archives for a date range (via a headless browser scraper)
2. Releases are stored in a local SQLite database (`metal_releases.db`)
3. Background **batch jobs** automatically backfill album art/bio and a "Hype Scale" score for newly fetched releases
4. Browse releases, filter by date/type/genre, check albums of interest
5. Add selected releases to named **Lists**, organise lists into **Folders**
6. Open a list to review: mark plays, rate, take notes; complete or star albums; see the Hype rating breakdown
7. Monitor background work in the **Jobs** tab
8. Recover or permanently delete lists/folders from a Toy Story recycling bin

**Non-commercial, personal use. No auth, no multi-user, no server.**

---

## Current State (as of 2026-06-14)

### How to run — development (C:\)

1. Open VS Code from `C:\Users\ashwo\OneDrive\Documents\GitHub\ThePit`
2. Double-click **`dev.bat`** (or run it from the VS Code terminal) — runs `app.py` directly with the local venv's Python
3. App opens at `http://127.0.0.1:5000` — runs against the local dev database
4. Press backtick `` ` `` to open the debug log panel at any time

### How to run — production (A:\)

Two ways to run the production copy, both at `A:\ThePit\`:

- **`ThePit.exe`** — a PyInstaller-frozen build (no console window). Templates/static/Python code are bundled inside the exe; `metal_releases.db`, `.env`, `venv\`, `browsers\`, and `fetch_releases.py` stay external on disk. **This exe does NOT auto-update from source changes — it must be rebuilt** (see "Building the .exe" below) whenever `app.py`/templates/etc. change.
- **`ThePit.bat`** / `launcher.py` (via Desktop shortcut, `pythonw.exe launcher.py`) — runs from live source, `git fetch`/`git pull`s from GitHub on every launch, then starts Flask + opens a native PyWebView window. Always reflects the latest pushed code.

Either way, `PLAYWRIGHT_BROWSERS_PATH=A:\ThePit\browsers` must be set (handled automatically by both launch paths).

### Building the .exe

```
cd A:\ThePit
python -m PyInstaller ThePit.spec --clean --noconfirm
copy /Y dist\ThePit.exe ThePit.exe
```
(`A:\ThePit\venv` does **not** have PyInstaller installed — use the system Python, which does. Close any running `ThePit.exe` first or the copy will fail with "Device or resource busy".)

---

## Storage & Portability

| Location | Contents |
|---|---|
| `A:\ThePit\` | All source code, database, templates, CSS, icon, resources, built exe |
| `A:\ThePit\venv\` | Python virtual environment (Flask app deps — no PyInstaller) |
| `A:\ThePit\browsers\` | Playwright Chromium (~300MB, required for scraper) |
| `A:\ThePit\metal_releases.db` | The SQLite database — all your data |
| `A:\ThePit\resources\` | Video files (`1666331258725097.webm` + `success recover/`) |
| `A:\ThePit\deleted_lists.json` | Backup of last 5 soft-deleted lists (written on delete) |
| Desktop shortcut "The Pit" | Primary launcher via `create_shortcut.ps1` (live-source path) |

---

## Development Workflow

```
C:\...\ThePit\  ← write code here (Claude Code / VS Code)
      │  git add / commit / push
      ▼
github.com/Aashworth0923/ThePit  ← version history
      │  git pull (auto on launcher.py launch, or manual)
      ▼
A:\ThePit\  ← production (data + secrets live here permanently)
```

**Session:**
1. Edit in C:\, test with `dev.bat`
2. `git add <files> && git commit -m "..." && git push` — **push must be run manually by the user** (a sandboxed/agent shell typically cannot complete GitHub auth — `git push` fails with an `/dev/tty` / "could not read Username" error)
3. `launcher.py`/`ThePit.bat` auto-pulls on next open. **`ThePit.exe` does NOT auto-pull — rebuild it manually after pushing if you want the frozen build updated.**
4. If A:\ThePit's working tree ever has uncommitted local edits that block a pull, diff them against recent dev commits first — they're often just an earlier manual sync that's already a subset of what's being pulled, in which case `git reset --hard origin/main` is safe.

**.env keys** — stored in `C:\...\ThePit\.env` (dev) and `A:\ThePit\.env` (prod). Never committed. Currently used for `LASTFM_API_KEY` (hype scoring).

---

## File Structure

```
ThePit\
├── app.py                      # All Flask routes + print()-capture debug log
├── db.py                       # All DB reads/writes (one function per operation)
├── fetch_releases.py           # Metal Archives scraper (Playwright, subprocess)
├── metadata.py                 # Art/bio API chain with in-process + DB caching
├── hype_scraper.py             # Hype Scale scoring (Last.fm + MusicBrainz heuristic)
├── hype_jobs.py                # Per-list "Scan Hype" job manager (pause/resume/cancel)
├── batch_jobs.py                # Auto-triggered batch jobs (art + hype) after Get Releases
├── import_releases.py          # One-shot .txt importer
├── launcher.py                 # PyWebView native window + git auto-update (live source)
├── dev.bat                      # Dev launcher (C:\, no VeraCrypt)
├── ThePit.bat                   # Production launcher (live source, no auto-update)
├── create_shortcut.ps1          # Creates Desktop shortcut (launcher.py path)
├── build.bat / ThePit.spec      # PyInstaller pipeline → dist\ThePit.exe
├── ThePit.exe                   # Frozen build (must be rebuilt manually — see above)
├── ThePit.ico / ThePit.jpg       # App icon
├── AI-README.md                 # This file
├── .env / .env.example          # API keys (gitignored) — LASTFM_API_KEY
├── .gitignore
│
├── resources\                   # Video files (gitignored)
│   ├── 1666331258725097.webm    # Permanent-delete confirmation video
│   └── success recover\
│       └── 1668404707031246.webm  # Recovery celebration video
│
├── templates\
│   ├── base.html                # Shared layout: nav (Home/Releases/Lists/Folders/Jobs),
│   │                             #   debug panel, trash bin, video popups
│   ├── home.html                # Home tab (placeholder)
│   ├── index.html                # Releases: table, filters, checkboxes, art drawer
│   ├── get_releases.html         # Date picker → scraper trigger
│   ├── lists.html                # Lists tab: unassigned lists + folder drag-drop panel
│   ├── list_detail.html          # List detail: pending/completed, review panel, full view
│   ├── folders.html              # Folders tab: Steam-style grid
│   ├── jobs.html                  # Batch Jobs tab: table + click-to-expand log
│   └── partials\
│       └── list_item.html        # Single item in a list (partial) — incl. Hype Rating panel
│
└── static\
    └── style.css                 # All styles (dark metal theme + kawaii + Toy Story overrides)
```

---

## Database Schema (`metal_releases.db`)

### `releases`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| artist, album | TEXT | UNIQUE(artist, album) |
| type, genre, release_date | TEXT | |
| starred, listened | INTEGER | 0/1 |
| rating | INTEGER | Nullable |
| notes | TEXT | Nullable |
| ma_album_id | TEXT | MA album ID for CDN image fallback |
| art_url | TEXT | NULL=never fetched, ''=fetched/none, URL=found |
| bio_text | TEXT | NULL=none, text=found |
| hype_tier | TEXT | NULL=never scanned; frozen / iced / room_temp / hot / fire |
| hype_score | REAL | 0–100 |
| hype_listeners, hype_playcount, hype_discog_count | INTEGER | Raw inputs behind the score |
| hype_checked_at | TEXT | Timestamp of last hype scan |

### `lists`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | UNIQUE |
| description | TEXT | |
| created_at | TEXT | |
| folder_id | INTEGER | FK → folders.id; NULL = unassigned |
| deleted_at | TEXT | NULL = active; datetime = soft-deleted |

### `list_releases`
| Column | Type | Notes |
|---|---|---|
| list_id, release_id | INTEGER | PK composite |
| listen_status | TEXT | skip / one_song / partial / full |
| rating | INTEGER | -2 to 2 |
| thoughts | TEXT | |
| completed, starred | INTEGER | 0/1 |
| completed_at | TEXT | |

### `folders`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | UNIQUE |
| color | TEXT | Auto-assigned from 8-color palette |
| created_at | TEXT | |
| deleted_at | TEXT | NULL = active; datetime = soft-deleted |

Schema changes are applied via `ALTER TABLE ... ADD COLUMN` inside `db.init_db()`, wrapped in try/except so they're safe to re-run on an existing DB.

---

## Key Architecture Notes

### Scraper (`fetch_releases.py` + `_scrape_subprocess`)
Uses Playwright (headless Chromium) and **must run as a subprocess** — Playwright uses asyncio internally and `sync_playwright()` fails in a Flask worker thread (ProactorEventLoop restriction). `_scrape_subprocess()` in `app.py`:
- In dev, runs `sys.executable fetch_releases.py --from ... --to ... --out <tmpfile>`.
- In a **frozen build**, `sys.executable` is `ThePit.exe` itself (would just relaunch the whole app), so it instead calls `A:\ThePit\venv\Scripts\python.exe` explicitly.
- Passes `creationflags=CREATE_NO_WINDOW` / `STARTF_USESHOWWINDOW` so no console window pops up when spawned from the windowed (`console=False`) frozen exe.
- Output written to a temp JSON file (`--out`), last 20/10 lines of stdout/stderr forwarded into the `[scraper]` debug log.

### Get Releases → Batch Jobs pipeline
`POST /get-releases`:
1. `_scrape_subprocess()` fetches new releases for the date range.
2. `db.insert_releases(fetched)` → `(inserted_count, release_ids)` — `release_ids` covers **every** release in the fetch (new or already-present), so backfill works even for older releases that predate this feature.
3. `batch_jobs.record_fetch_releases(...)` — logs an immediate "done" job summarizing the fetch.
4. `batch_jobs.start_fetch_art(release_ids)` — background thread; for each release missing `art_url`, calls `metadata.get_release_meta()` and `db.save_release_art_cache()`.
5. `batch_jobs.start_hype_scan(release_ids)` — background thread; for each release missing `hype_tier`, calls `hype_scraper.compute_band_hype()` and `db.save_release_hype()` (1s delay between bands — Last.fm/MusicBrainz politeness).

### Batch Jobs registry (`batch_jobs.py`)
- In-memory only (`_jobs` list, process-lifetime), modeled on `hype_jobs.py` but simplified: status is just `running` → `done` | `error`, no pause/resume.
- Each job: `{id, type, label, status, total, done, current, log[], created_at, finished_at}`.
- `_log(job, msg)` appends to `job["log"]` and prints `[batch-<type>-<id>] <msg>` to the shared debug log.
- `get_all_jobs()` → summaries (no log) for the table; `get_job(id)` → full job incl. log.
- Routes: `GET /jobs` (page), `GET /api/jobs` (table refresh), `GET /api/jobs/<id>` (detail/log).
- **Jobs tab** (`templates/jobs.html`): manual refresh button (↻) re-fetches `/api/jobs` and re-renders rows; click a row to expand its log inline. No live polling.

### Hype Scale (`hype_scraper.py` + `hype_jobs.py`)
- `compute_band_hype(artist)` → `{listeners, playcount, discog_count, score, tier}`.
  - Score blends Last.fm listener/playcount stats (popularity + engagement) with MusicBrainz studio-album count (discography depth).
  - `TIERS`: score → `frozen` (<20) / `iced` (<40) / `room_temp` (<60) / `hot` (<80) / `fire` (≥80).
  - RateYourMusic and MA's AJAX endpoints are captcha/Cloudflare-walled and intentionally not used.
- `explain_hype(listeners, playcount, discog_count, score, tier)` → human-readable breakdown lines (Popularity/Engagement/Discography/Total), rendered via the `hype_explain` Jinja filter in the list-item review panel above "Play Length".
- `hype_jobs.py` — **per-list** "Scan Hype" manual job (pause/resume/cancel via `threading.Event`), used as a fallback/refresh inside a list (`/lists/<id>/hype/start|pause|resume|cancel|status`). Independent of `batch_jobs.py`'s automatic post-fetch scan.
- `db.save_release_hype()` sets `hype_checked_at = datetime('now')`; `hype_tier IS NULL` means never scanned.

### Art / Bio Lookup
`/release/<id>/meta` endpoint:
1. Check `releases.art_url` in DB → if not NULL, return immediately (zero API calls)
2. If NULL (never fetched): run 4-tier API chain, write result to DB
3. Art chain: MusicBrainz/CAA → Last.fm album.getInfo → MA CDN (if `ma_album_id`) → Bandcamp JSON-LD
4. CDN hotlink-protected images (Last.fm, Bandcamp) proxied through `/api/art-proxy`
5. In-process `_cache` dict in `metadata.py` deduplicates within a session
6. `metadata.get_release_meta()` already includes a 0.6s delay — `batch_jobs.start_fetch_art` needs no extra rate-limiting

### Soft Delete / Recycling
- Lists and folders have a `deleted_at` column; all queries filter `deleted_at IS NULL`
- Soft-delete prunes to keep ≤ 5 per type; also writes `deleted_lists.json` backup
- `GET /trash` → returns last 5 deleted lists + folders as JSON
- Recovery: `POST /trash/restore-list/<id>` or `POST /trash/restore-folder/<id>`
- Permanent delete: `POST /trash/delete-list/<id>` or `POST /trash/delete-folder/<id>`

### Video Popups
Two embedded video popups (same mechanism):
- **Permanent delete** (`resources/1666331258725097.webm`) — plays when skull-shirt kid button clicked
- **Recovery success** (`resources/success recover/1668404707031246.webm`) — plays when item is restored
- Both use blob URL via `fetch().then(r=>r.blob()).then(URL.createObjectURL)` to bypass Edge WebView2 MIME-type detection issues
- `_resources_dir()` resolves correctly in dev (`C:\...\ThePit\resources\`) and prod (`A:\ThePit\resources\`)

### Folder Icons
Steam-style jewel-case effect:
- `perspective(750px) rotateX(2deg)` at rest (tiny shelf angle)
- Hover: `rotateX(8deg) scale(1.04) translateY(-6px)` — bottom peeks forward
- `::before` / `::after` gradient cross-fade (0.45s) simulates light reflection moving
- Art loaded async via `/folders/<id>/art-hint` → `/release/<id>/meta`

### Debug Logging
- `builtins.print` is monkeypatched in `app.py` (`_capturing_print`) to capture all `print()` output app-wide into a ring buffer.
- Backtick `` ` `` opens the in-app debug panel (client + server logs); `GET /api/logs` returns the raw log.
- Convention: prefix log lines by subsystem — `[scraper]`, `[hype]`, `[hype-job]`, `[batch-<type>-<id>]`, `[db-art]`, `[db-hype]`, `[mb]`, `[lastfm...]`.

---

## Epic Roadmap

| # | Epic | Status |
|---|---|---|
| 1 | Data Ingestion | ✅ Done |
| 2 | Local App Shell + Native Window | ✅ Done |
| 2b | Rich Metadata (art drawer, art persistence) | ✅ Done |
| 2c | Folders, Lists, Soft Delete, Recycling Bin | ✅ Done |
| 3 | Release Browser refinements (filters, row click, date picker) | ✅ Done |
| 3b | List review UI (play/rate/notes, compact/full view) | ✅ Done |
| 4 | Hype Scale scoring + review-panel breakdown | ✅ Done |
| 4b | Automated batch jobs (art + hype) on Get Releases + Jobs tab | ✅ Done |
| 5 | PyInstaller `.exe` build for taskbar pinning | ✅ Done (manual rebuild required) |
| 6 | Priority Flagging — auto-flag by label or genre | Planned |
| 7 | Scraper Scheduling — weekly auto-fetch | Planned |
| 8 | Home page content | Planned |
| 9 | AI Integration — Claude API priority scores | Planned |

---

## Known Limitations

- **`ma_album_id` backfill:** releases from the original .txt import have `ma_album_id = NULL` — MA CDN fallback can't be used for them until re-scraped through the app.
- **Art coverage gaps:** some underground releases have no art in any of the 4 sources. Verified via debug panel; `art_url = ''` in DB means "checked, nothing found — don't retry."
- **Scraper speed:** Playwright + Cloudflare bypass takes 30–60s per fetch and runs as a separate process. Progress visible in the debug panel via `[scraper]` log lines.
- **Hype scoring coverage:** small/underground bands often return 0 listeners/playcount from Last.fm and no MusicBrainz match — they'll score `frozen` by default, which is expected (not a bug).
- **`ThePit.exe` is not self-updating:** `launcher.py`/`ThePit.bat` auto-pull from GitHub, but the frozen `.exe` bundles its own copy of the code and must be rebuilt + copied over manually after any source change you want reflected in it.
- **PyWebView video:** WebM playback in Edge WebView2 required blob URL approach (raw bytes bypasses MIME-type rejection). `_resources_dir()` must be correct for both environments.

---

## Dependencies

App deps live in `A:\ThePit\venv` (and `C:\...\ThePit\venv` for dev). Key ones:
- `flask`, `playwright`, `beautifulsoup4`, `requests`, `cloudscraper`
- `pywebview`, `python-dotenv`, `pillow`

PyInstaller is **not** in either app venv — use the system Python (`python -m PyInstaller ...`) to build `ThePit.exe`.

Python 3.12. Playwright Chromium at `A:\ThePit\browsers\`.

### Re-install on a new machine
```bash
python -m venv A:\ThePit\venv
A:\ThePit\venv\Scripts\pip install flask playwright beautifulsoup4 requests cloudscraper pywebview python-dotenv pillow
set PLAYWRIGHT_BROWSERS_PATH=A:\ThePit\browsers
A:\ThePit\venv\Scripts\python -m playwright install chromium
```
