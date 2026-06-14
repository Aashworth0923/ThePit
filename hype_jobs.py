"""
Background job manager for per-list "hype scan" runs.

One job per list_id at a time, running in a daemon thread. Supports
pause/resume/cancel via threading.Event. State is process-lifetime only
(in-memory) — fine for a local single-user app.
"""

import threading
import time

import db
import hype_scraper

_jobs = {}
_jobs_lock = threading.Lock()


def _new_job():
    return {
        "status": "idle",       # idle | running | paused | cancelled | done
        "total": 0,
        "done": 0,
        "current_artist": None,
        "results": {},          # release_id -> {tier, score}
        "pause_event": threading.Event(),
        "cancel_event": threading.Event(),
        "thread": None,
    }


def _worker(list_id, job, releases):
    job["pause_event"].set()  # start in "running" state
    total = len(releases)
    print(f"[hype-job] list {list_id}: starting scan of {total} release(s)", flush=True)

    for i, row in enumerate(releases, start=1):
        if job["cancel_event"].is_set():
            print(f"[hype-job] list {list_id}: cancelled at {i-1}/{total}", flush=True)
            break

        job["pause_event"].wait()  # blocks while paused

        if job["cancel_event"].is_set():
            print(f"[hype-job] list {list_id}: cancelled at {i-1}/{total}", flush=True)
            break

        release_id, artist = row["id"], row["artist"]
        job["current_artist"] = artist
        print(f"[hype-job] list {list_id}: ({i}/{total}) scanning {artist!r}", flush=True)

        try:
            result = hype_scraper.compute_band_hype(artist)
            db.save_release_hype(
                release_id,
                score=result["score"],
                tier=result["tier"],
                listeners=result["listeners"],
                playcount=result["playcount"],
                discog_count=result["discog_count"],
            )
            explain = hype_scraper.explain_hype(
                result["listeners"], result["playcount"], result["discog_count"],
                result["score"], result["tier"],
            )
            job["results"][release_id] = {
                "tier": result["tier"],
                "score": result["score"],
                "explain": explain,
            }
        except Exception as e:
            print(f"[hype-job] list {list_id}: error scanning {artist!r}: {e}", flush=True)

        job["done"] = i

        # Politeness delay for Last.fm + MusicBrainz (max ~1 req/sec)
        time.sleep(1.0)

    if not job["cancel_event"].is_set():
        job["status"] = "done"
        print(f"[hype-job] list {list_id}: done ({job['done']}/{total})", flush=True)
    else:
        job["status"] = "cancelled"

    job["current_artist"] = None


def start(list_id, force=False):
    with _jobs_lock:
        existing = _jobs.get(list_id)
        if existing and existing["status"] in ("running", "paused"):
            print(f"[hype-job] list {list_id}: already running, ignoring start", flush=True)
            return get_status(list_id)

        releases = db.get_releases_for_hype_scan(list_id, force=force)
        job = _new_job()
        job["total"] = len(releases)
        _jobs[list_id] = job

        if not releases:
            job["status"] = "done"
            print(f"[hype-job] list {list_id}: nothing to scan (force={force})", flush=True)
            return get_status(list_id)

        job["status"] = "running"
        t = threading.Thread(target=_worker, args=(list_id, job, releases), daemon=True)
        job["thread"] = t
        t.start()
        return get_status(list_id)


def pause(list_id):
    job = _jobs.get(list_id)
    if job and job["status"] == "running":
        job["pause_event"].clear()
        job["status"] = "paused"
        print(f"[hype-job] list {list_id}: paused", flush=True)
    return get_status(list_id)


def resume(list_id):
    job = _jobs.get(list_id)
    if job and job["status"] == "paused":
        job["status"] = "running"
        job["pause_event"].set()
        print(f"[hype-job] list {list_id}: resumed", flush=True)
    return get_status(list_id)


def cancel(list_id):
    job = _jobs.get(list_id)
    if job and job["status"] in ("running", "paused"):
        job["cancel_event"].set()
        job["pause_event"].set()  # unblock if paused so the thread can exit
        print(f"[hype-job] list {list_id}: cancel requested", flush=True)
    return get_status(list_id)


def get_status(list_id):
    job = _jobs.get(list_id)
    if not job:
        return {"status": "idle", "total": 0, "done": 0, "current_artist": None, "results": {}}
    return {
        "status": job["status"],
        "total": job["total"],
        "done": job["done"],
        "current_artist": job["current_artist"],
        "results": dict(job["results"]),
    }
