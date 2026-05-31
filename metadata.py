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


def get_release_meta(artist, album):
    """
    Main entry point. Returns:
      {art_url: str|None, bio: str|None, cached: bool}
    Results are cached in-process for the session.
    """
    key = (artist.lower().strip(), album.lower().strip())
    if key in _cache:
        return {**_cache[key], "cached": True}

    result = {"art_url": None, "bio": None}

    release_mbid, rg_mbid = _search_mb(artist, album)
    if release_mbid or rg_mbid:
        result["art_url"] = _get_art_url(release_mbid, rg_mbid)

    # Brief pause — MusicBrainz asks for max 1 req/sec
    time.sleep(0.6)

    result["bio"] = _get_bio(artist)

    _cache[key] = result
    return {**result, "cached": False}
