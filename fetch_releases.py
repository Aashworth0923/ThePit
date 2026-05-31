"""
Fetches upcoming metal releases from metal-archives.com and saves raw JSON.
Uses Playwright (real headless browser) to pass Cloudflare protection.

Requires:
    python -m pip install playwright beautifulsoup4
    python -m playwright install chromium

Usage:
    python fetch_releases.py                          # all upcoming releases
    python fetch_releases.py --from 2026-06-01 --to 2026-06-30
    python fetch_releases.py --out june_raw.json
"""

import json
import time
import argparse
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_URL  = "https://www.metal-archives.com"
PAGE_URL  = f"{BASE_URL}/release/upcoming"
AJAX_URL  = f"{BASE_URL}/release/ajax-upcoming/json/1"
PAGE_SIZE = 100
DELAY_SEC = 3.0   # robots.txt Crawl-delay: 3


def parse_cell(html):
    """Return (plain text, href) from an HTML cell that may contain an <a> tag."""
    if not html or not html.strip().startswith("<"):
        return html.strip(), None
    soup = BeautifulSoup(html, "html.parser")
    a = soup.find("a")
    return soup.get_text(strip=True), (a["href"] if a else None)


def build_ajax_url(start, date_from=None, date_to=None):
    # Parameters reverse-engineered from the actual browser request
    parts = [
        f"sEcho={start // PAGE_SIZE + 1}",
        "iColumns=6",
        "sColumns=",
        f"iDisplayStart={start}",
        f"iDisplayLength={PAGE_SIZE}",
        "mDataProp_0=0", "mDataProp_1=1", "mDataProp_2=2",
        "mDataProp_3=3", "mDataProp_4=4", "mDataProp_5=5",
        "iSortCol_0=4", "sSortDir_0=asc", "iSortingCols=1",
        "bSortable_0=true", "bSortable_1=true", "bSortable_2=true",
        "bSortable_3=true", "bSortable_4=true", "bSortable_5=true",
        "includeVersions=0",
        f"fromDate={date_from or ''}",
        f"toDate={date_to or '0000-00-00'}",
    ]
    return f"{AJAX_URL}?{'&'.join(parts)}"


def fetch_all(page, date_from=None, date_to=None):
    releases = []
    start = 0
    total = None

    while True:
        url = build_ajax_url(start, date_from, date_to)
        print(f"  Fetching records {start + 1}–{start + PAGE_SIZE}...", end="", flush=True)

        # Make the AJAX call from inside the already-verified browser session
        try:
            data = page.evaluate("""
                async (url) => {
                    const resp = await fetch(url, {
                        headers: {
                            "X-Requested-With": "XMLHttpRequest",
                            "Accept": "application/json, text/javascript, */*; q=0.01"
                        }
                    });
                    if (!resp.ok) throw new Error("HTTP " + resp.status);
                    return await resp.json();
                }
            """, url)
        except Exception as e:
            print(f"\n  AJAX error: {e}")
            break

        if total is None:
            total = int(data.get("iTotalRecords", 0))
            print(f"  (total on server: {total})")
        else:
            print()

        rows = data.get("aaData", [])
        if not rows:
            print("  No rows returned — done.")
            break

        for row in rows:
            artist, artist_url = parse_cell(row[0])
            album,  album_url  = parse_cell(row[1])
            releases.append({
                "artist":       artist,
                "album":        album,
                "type":         row[2].strip() if len(row) > 2 else "",
                "genre":        row[3].strip() if len(row) > 3 else "",
                "release_date": row[4].strip() if len(row) > 4 else "",
                "artist_url":   artist_url,
                "album_url":    album_url,
            })

        start += PAGE_SIZE
        if start >= total:
            break

        time.sleep(DELAY_SEC)

    return releases


def print_preview(releases, n=20):
    print(f"\n{'DATE':<18} {'ARTIST':<35} {'ALBUM':<35} {'TYPE':<14} GENRE")
    print("-" * 115)
    for r in releases[:n]:
        print(
            f"{r['release_date']:<18} "
            f"{r['artist'][:34]:<35} "
            f"{r['album'][:34]:<35} "
            f"{r['type']:<14} "
            f"{r['genre']}"
        )
    if len(releases) > n:
        print(f"  ... and {len(releases) - n} more")


def _launch_browser(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    )
    page = context.new_page()
    print("  Launching browser, loading page (Cloudflare handled automatically)...", flush=True)
    page.goto(PAGE_URL, wait_until="networkidle", timeout=60000)
    print("  Page loaded.", flush=True)
    time.sleep(2)
    return browser, page


def run_fetch(date_from=None, date_to=None):
    """
    Programmatic entry point — call this from Flask or other modules.
    Returns a list of release dicts.
    """
    with sync_playwright() as p:
        browser, page = _launch_browser(p)
        releases = fetch_all(page, date_from, date_to)
        browser.close()
    return releases


def main():
    parser = argparse.ArgumentParser(
        description="Fetch upcoming metal releases from metal-archives.com"
    )
    parser.add_argument("--from", dest="date_from", default=None,
                        help="Start date, e.g. 2026-06-01")
    parser.add_argument("--to",   dest="date_to",   default=None,
                        help="End date,   e.g. 2026-06-30")
    parser.add_argument("--out",  default="raw_releases.json",
                        help="Output JSON file (default: raw_releases.json)")
    parser.add_argument("--preview", type=int, default=20,
                        help="Rows to print as preview (default: 20)")
    args = parser.parse_args()

    print("Fetching releases from metal-archives.com")
    if args.date_from or args.date_to:
        print(f"  Date range: {args.date_from or 'any'} -> {args.date_to or 'any'}")
    print()

    releases = run_fetch(args.date_from, args.date_to)

    print(f"\nTotal fetched: {len(releases)}\n")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(releases, f, indent=2, ensure_ascii=False)
    print(f"Raw data saved to: {args.out}")

    print_preview(releases, args.preview)


if __name__ == "__main__":
    main()
