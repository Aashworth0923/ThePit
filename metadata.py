"""
Fetches album art and artist bios from external APIs on demand.
Nothing is stored in the database — data is streamed per request and cached in-process.

Sources:
  - MusicBrainz + Cover Art Archive: album art (free, no API key)
  - Last.fm: artist bio (free, requires API key)

To enable Last.fm bios:
  1. Get a free key at https://www.last.fm/api/account/create (takes 2 minutes)
  2. Set it in ThePit.bat:  set LASTFM_API_KEY=your_key_here
     OR paste it directly below: LASTFM_API_KEY = "your_key_here"
"""

import os
import re
import sys
import requests
import time
from dotenv import load_dotenv

# When frozen as .exe, .env lives next to the executable
if getattr(sys, "frozen", False):
    _dir = os.environ.get("THEPIT_APP_DIR", os.path.dirname(sys.executable))
    load_dotenv(os.path.join(_dir, ".env"))
else:
    load_dotenv()

LASTFM_API_KEY    = os.environ.get("LASTFM_API_KEY", "")
LASTFM_SECRET     = os.environ.get("LASTFM_SHARED_SECRET", "")  # needed if you add scrobbling later

MB_SEARCH_URL = "https://musicbrainz.org/ws/2/release/"
CAA_URL       = "https://coverartarchive.org"
LASTFM_URL    = "https://ws.audioscrobbler.com/2.0/"

MB_HEADERS = {
    "User-Agent": "ThePit/1.0 (personal-metal-tracker)",
    "Accept": "application/json",
}
TIMEOUT = 10

# In-process cache: (artist_lower, album_lower) -> result dict
# Persists for the lifetime of the Flask process (cleared on restart)
_cache = {}


def _search_mb(artist, album):
    """Search MusicBrainz for a release. Returns (release_mbid, release_group_mbid)."""
    print(f"[mb] searching: artist={artist!r} album={album!r}", flush=True)
    try:
        resp = requests.get(
            MB_SEARCH_URL,
            params={
                "query": f'release:"{album}" AND artist:"{artist}"',
                "fmt": "json",
                "limit": 3,
            },
            headers=MB_HEADERS,
            timeout=TIMEOUT,
        )
        print(f"[mb] search status: {resp.status_code}", flush=True)
        if resp.status_code == 200:
            releases = resp.json().get("releases", [])
            print(f"[mb] releases found: {len(releases)}", flush=True)
            if releases:
                r = releases[0]
                rid, rgid = r.get("id"), r.get("release-group", {}).get("id")
                print(f"[mb] best match: release={rid} release-group={rgid}", flush=True)
                return rid, rgid
        print("[mb] no match found", flush=True)
    except Exception as e:
        print(f"[mb] search error: {e}", flush=True)
    return None, None


def _get_art_url(release_mbid, rg_mbid):
    """Try Cover Art Archive for a release, then fall back to the release group."""
    def _try(endpoint):
        print(f"[caa] trying: {endpoint}", flush=True)
        try:
            r = requests.get(endpoint, timeout=TIMEOUT)
            print(f"[caa] status: {r.status_code}", flush=True)
            if r.status_code == 200:
                images = r.json().get("images", [])
                if images:
                    thumbs = images[0].get("thumbnails", {})
                    url = thumbs.get("500") or thumbs.get("large") or images[0].get("image")
                    print(f"[caa] art url: {url}", flush=True)
                    return url
        except Exception as e:
            print(f"[caa] error: {e}", flush=True)
        return None

    if release_mbid:
        url = _try(f"{CAA_URL}/release/{release_mbid}")
        if url:
            return url
    if rg_mbid:
        return _try(f"{CAA_URL}/release-group/{rg_mbid}")
    print("[caa] no art found", flush=True)
    return None


def _get_bio(artist):
    """Fetch and clean an artist bio from Last.fm."""
    if not LASTFM_API_KEY:
        print("[lastfm] no API key set — skipping bio", flush=True)
        return None
    print(f"[lastfm] fetching bio for: {artist!r}", flush=True)
    try:
        resp = requests.get(
            LASTFM_URL,
            params={
                "method": "artist.getinfo",
                "artist": artist,
                "api_key": LASTFM_API_KEY,
                "format": "json",
            },
            timeout=TIMEOUT,
        )
        print(f"[lastfm] status: {resp.status_code}", flush=True)
        if resp.status_code == 200:
            raw = resp.json().get("artist", {}).get("bio", {}).get("summary", "")
            clean = re.sub(r"<[^>]+>", "", raw)
            clean = re.sub(r"User-contributed text.*?under the.*?License.*$", "", clean, flags=re.S)
            clean = re.sub(r"Read more on Last\.fm\.*", "", clean)
            clean = re.sub(r"\s+", " ", clean).strip()
            if clean and len(clean) > 20:
                print(f"[lastfm] bio found, {len(clean)} chars", flush=True)
                return clean
            print("[lastfm] bio empty or too short", flush=True)
    except Exception as e:
        print(f"[lastfm] error: {e}", flush=True)
    return None


def _get_lastfm_album_art(artist, album):
    """Get album art from Last.fm album.getInfo (max 300px but good fallback coverage)."""
    if not LASTFM_API_KEY:
        return None
    print(f"[lastfm-art] searching: {artist!r} / {album!r}", flush=True)
    try:
        resp = requests.get(
            LASTFM_URL,
            params={
                "method": "album.getinfo",
                "artist": artist,
                "album":  album,
                "api_key": LASTFM_API_KEY,
                "format": "json",
            },
            timeout=TIMEOUT,
        )
        print(f"[lastfm-art] status: {resp.status_code}", flush=True)
        if resp.status_code == 200:
            images = resp.json().get("album", {}).get("image", [])
            # Last.fm returns sizes: small, medium, large, extralarge, mega
            # Prefer extralarge/mega, skip the blank placeholder hash
            BLANK = "2a96cbd8b46e442fc41c2b86b821562f.png"
            for size in ("mega", "extralarge", "large"):
                for img in images:
                    url = img.get("#text", "")
                    if img.get("size") == size and url and BLANK not in url:
                        print(f"[lastfm-art] found ({size}): {url}", flush=True)
                        return url
    except Exception as e:
        print(f"[lastfm-art] error: {e}", flush=True)
    return None


def _slugify(text):
    """Convert artist/album name to a Bandcamp-style URL slug."""
    import unicodedata
    # Normalise unicode (é → e), lowercase, keep only alphanumeric + spaces/hyphens
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "-", text.strip())
    return re.sub(r"-+", "-", text).strip("-")


def _get_bandcamp_art(artist, album):
    """
    Try to fetch album art from Bandcamp by constructing the probable URL
    and parsing the JSON-LD embedded in the page.

    URL pattern: https://{artist-slug}.bandcamp.com/album/{album-slug}

    Bandcamp embeds a <script type="application/ld+json"> block on every
    album page containing the image URL at full quality (~1200×1200).
    """
    artist_slug = _slugify(artist)
    album_slug  = _slugify(album)
    if not artist_slug or not album_slug:
        return None

    url = f"https://{artist_slug}.bandcamp.com/album/{album_slug}"
    print(f"[bandcamp] trying: {url}", flush=True)

    try:
        from bs4 import BeautifulSoup
        resp = requests.get(url, timeout=8, headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        print(f"[bandcamp] status: {resp.status_code}", flush=True)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # 1. Try JSON-LD structured data
        import json as _json
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = _json.loads(tag.string or "")
                if isinstance(data, list):
                    data = data[0]
                img = data.get("image") or data.get("thumbnailUrl")
                if img and isinstance(img, str) and img.startswith("http"):
                    print(f"[bandcamp] found art (ld+json): {img[:80]}", flush=True)
                    return img
            except Exception:
                continue

        # 2. Try Open Graph image tag (more consistent across Bandcamp pages)
        og = soup.find("meta", property="og:image")
        if og and og.get("content", "").startswith("http"):
            img = og["content"]
            print(f"[bandcamp] found art (og:image): {img[:80]}", flush=True)
            return img

    except Exception as e:
        print(f"[bandcamp] error: {e}", flush=True)

    return None


def _get_ma_art_url(ma_album_id):
    """
    Try to fetch album art directly from the Metal Archives CDN.
    URL pattern: /images/{d1}/{d2}/{d3}/{d4}/{id}.jpg
    Uses HEAD request — just checks existence, doesn't download the image.
    Returns the URL if the image exists, None otherwise.
    """
    if not ma_album_id:
        return None
    id_str = str(ma_album_id)
    if len(id_str) < 4:
        return None
    path = "/".join(id_str[:4])
    url  = f"https://www.metal-archives.com/images/{path}/{id_str}.jpg"
    print(f"[ma-art] trying: {url}", flush=True)
    try:
        r = requests.head(url, timeout=TIMEOUT, headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.metal-archives.com/",
        })
        print(f"[ma-art] status: {r.status_code}", flush=True)
        if r.status_code == 200:
            return url
    except Exception as e:
        print(f"[ma-art] error: {e}", flush=True)
    return None


def get_release_meta(artist, album, ma_album_id=None):
    """
    Main entry point. Returns:
      {art_url: str|None, bio: str|None, cached: bool}
    Results are cached in-process for the session.

    Fallback chain for art:
      1. MusicBrainz / Cover Art Archive
      2. Metal Archives CDN (if ma_album_id is provided)
    """
    key = (artist.lower().strip(), album.lower().strip())
    if key in _cache:
        return {**_cache[key], "cached": True}

    result = {"art_url": None, "bio": None}

    # 1. MusicBrainz / Cover Art Archive
    release_mbid, rg_mbid = _search_mb(artist, album)
    if release_mbid or rg_mbid:
        result["art_url"] = _get_art_url(release_mbid, rg_mbid)

    # 2. Last.fm album art (already have key, good underground coverage)
    if not result["art_url"]:
        result["art_url"] = _get_lastfm_album_art(artist, album)

    # 3. Metal Archives CDN (if ma_album_id stored from scraper)
    if not result["art_url"] and ma_album_id:
        result["art_url"] = _get_ma_art_url(ma_album_id)

    # 4. Bandcamp JSON-LD (best underground coverage, ~1200px images)
    if not result["art_url"]:
        result["art_url"] = _get_bandcamp_art(artist, album)

    # Brief pause — MusicBrainz asks for max 1 req/sec
    time.sleep(0.6)

    result["bio"] = _get_bio(artist)

    _cache[key] = result
    return {**result, "cached": False}
