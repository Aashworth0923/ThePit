"""
Computes a "hype scale" score for an artist — a rough heuristic for how likely
a release is to be an industry standout, based on:

  - Last.fm listener/playcount stats (popularity + fan-engagement signal)
  - MusicBrainz studio album count (discography depth — "this is their Nth album")

RateYourMusic would be ideal but is captcha-walled. Metal Archives' AJAX
endpoints are behind Cloudflare Turnstile and unusable without a full
Playwright browser, so they're not used here.

Nothing is stored here — callers persist results via db.save_release_hype().
"""

import os
import sys
import math
import requests
from dotenv import load_dotenv

if getattr(sys, "frozen", False):
    _dir = os.environ.get("THEPIT_APP_DIR", os.path.dirname(sys.executable))
    load_dotenv(os.path.join(_dir, ".env"))
else:
    load_dotenv()

LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY", "")

LASTFM_URL = "https://ws.audioscrobbler.com/2.0/"
MB_ARTIST_URL = "https://musicbrainz.org/ws/2/artist/"
MB_RG_URL     = "https://musicbrainz.org/ws/2/release-group"

LASTFM_TIMEOUT = 8
MB_TIMEOUT     = 6

MB_HEADERS = {
    "User-Agent": "ThePit/1.0 (personal-metal-tracker)",
    "Accept": "application/json",
}

TIERS = [
    (20, "frozen"),
    (40, "iced"),
    (60, "room_temp"),
    (80, "hot"),
    (101, "fire"),
]


def get_lastfm_artist_stats(artist):
    """Return {listeners, playcount} from Last.fm artist.getinfo, or both None."""
    if not LASTFM_API_KEY:
        print("[hype-lastfm] no API key set — skipping", flush=True)
        return {"listeners": None, "playcount": None}

    print(f"[hype-lastfm] fetching stats for: {artist!r}", flush=True)
    try:
        resp = requests.get(
            LASTFM_URL,
            params={
                "method": "artist.getinfo",
                "artist": artist,
                "api_key": LASTFM_API_KEY,
                "format": "json",
            },
            timeout=LASTFM_TIMEOUT,
        )
        print(f"[hype-lastfm] status: {resp.status_code}", flush=True)
        if resp.status_code == 200:
            stats = resp.json().get("artist", {}).get("stats", {})
            listeners = int(stats.get("listeners", 0) or 0)
            playcount = int(stats.get("playcount", 0) or 0)
            print(f"[hype-lastfm] listeners={listeners} playcount={playcount}", flush=True)
            return {"listeners": listeners, "playcount": playcount}
        print("[hype-lastfm] no stats found", flush=True)
    except Exception as e:
        print(f"[hype-lastfm] error: {e}", flush=True)
    return {"listeners": None, "playcount": None}


def get_mb_studio_album_count(artist):
    """
    Return the number of distinct studio albums (primary-type "Album",
    no secondary types — excludes Live/Compilation/Soundtrack/etc.)
    for this artist, via MusicBrainz. Returns None on lookup failure.
    """
    print(f"[hype-mb] searching artist: {artist!r}", flush=True)
    try:
        resp = requests.get(
            MB_ARTIST_URL,
            params={"query": f'artist:"{artist}"', "fmt": "json", "limit": 1},
            headers=MB_HEADERS,
            timeout=MB_TIMEOUT,
        )
        print(f"[hype-mb] artist search status: {resp.status_code}", flush=True)
        if resp.status_code != 200:
            return None
        artists = resp.json().get("artists", [])
        if not artists:
            print("[hype-mb] no artist match found", flush=True)
            return None
        mbid = artists[0]["id"]
        print(f"[hype-mb] matched mbid={mbid} name={artists[0].get('name')!r}", flush=True)
    except Exception as e:
        print(f"[hype-mb] artist search error: {e}", flush=True)
        return None

    try:
        resp = requests.get(
            MB_RG_URL,
            params={"artist": mbid, "type": "album", "fmt": "json", "limit": 100},
            headers=MB_HEADERS,
            timeout=MB_TIMEOUT,
        )
        print(f"[hype-mb] release-group status: {resp.status_code}", flush=True)
        if resp.status_code != 200:
            return None
        groups = resp.json().get("release-groups", [])
        titles = set()
        for g in groups:
            if g.get("primary-type") != "Album":
                continue
            if g.get("secondary-types"):
                continue
            titles.add(g.get("title", "").strip().lower())
        print(f"[hype-mb] studio albums found: {len(titles)}", flush=True)
        return len(titles)
    except Exception as e:
        print(f"[hype-mb] release-group error: {e}", flush=True)
        return None


def explain_hype(listeners, playcount, discog_count, score, tier):
    """
    Return a list of human-readable lines breaking down how a stored
    hype score was computed, for display as a tooltip.
    """
    pop_score = 0.0
    if listeners and listeners > 0:
        pop_score = max(0.0, min(50.0, (math.log10(listeners + 1) - 2.5) * 20))

    engagement_score = 0.0
    if listeners and playcount and listeners > 0:
        engagement_score = max(0.0, min(10.0, (playcount / listeners - 8) * 1.0))

    discog_score = 0.0
    if discog_count:
        discog_score = min(30.0, discog_count * 6.0)

    lines = []
    if listeners is not None:
        lines.append(f"Popularity: {listeners:,} Last.fm listeners → {pop_score:.0f}/50 pts")
    else:
        lines.append("Popularity: no Last.fm data → 0/50 pts")

    if listeners and playcount:
        ratio = playcount / listeners
        lines.append(f"Engagement: {ratio:.1f} plays per listener → {engagement_score:.0f}/10 pts")
    else:
        lines.append("Engagement: no playcount data → 0/10 pts")

    if discog_count is not None:
        lines.append(f"Discography: {discog_count} studio album(s) → {discog_score:.0f}/30 pts")
    else:
        lines.append("Discography: no MusicBrainz match → 0/30 pts")

    if score is not None:
        lines.append(f"Total: {score:.0f}/100 → {tier.replace('_', ' ').title() if tier else '?'}")

    return lines


def _score_to_tier(score):
    for threshold, tier in TIERS:
        if score < threshold:
            return tier
    return "fire"


def compute_band_hype(artist):
    """
    Compute a 0-100 hype score and tier for an artist.

    Returns:
        {listeners, playcount, discog_count, score, tier}
    """
    print(f"[hype] computing hype for {artist!r}", flush=True)

    lastfm = get_lastfm_artist_stats(artist)
    listeners = lastfm["listeners"]
    playcount = lastfm["playcount"]
    discog_count = get_mb_studio_album_count(artist)

    # Popularity: up to 50 pts. ~300 listeners = 0, ~100k+ listeners = max.
    pop_score = 0.0
    if listeners and listeners > 0:
        pop_score = max(0.0, min(50.0, (math.log10(listeners + 1) - 2.5) * 20))

    # Engagement: playcount/listener ratio above a baseline of 8, up to 10 pts.
    engagement_score = 0.0
    if listeners and playcount and listeners > 0:
        ratio = playcount / listeners
        engagement_score = max(0.0, min(10.0, (ratio - 8) * 1.0))

    # Discography depth: up to 30 pts (5+ studio albums = max — "established act")
    discog_score = 0.0
    if discog_count:
        discog_score = min(30.0, discog_count * 6.0)

    score = pop_score + engagement_score + discog_score
    tier = _score_to_tier(score)

    print(f"[hype] {artist!r} -> score={score:.1f} "
          f"(pop={pop_score:.1f} engagement={engagement_score:.1f} discog={discog_score:.1f}) "
          f"tier={tier}", flush=True)

    return {
        "listeners": listeners,
        "playcount": playcount,
        "discog_count": discog_count,
        "score": score,
        "tier": tier,
    }
