"""
In-memory registry + background workers for batch jobs triggered by
"Get Releases" (album art/bio fetch, hype scan). Process-lifetime only,
modeled on hype_jobs.py's threading pattern but simplified: no
pause/resume, just running -> done | error.
"""

import threading
import time

import db
import hype_scraper
import metadata

_jobs = []  # newest first
_next_id = 1
_lock = threading.Lock()

MAX_HISTORY = 50


def _new_job(job_type, label, total=0):
    global _next_id
    with _lock:
        job = {
            "id": _next_id,
            "type": job_type,
            "label": label,
            "status": "running",
            "total": total,
            "done": 0,
            "current": None,
            "log": [],
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": None,
        }
        _next_id += 1
        _jobs.insert(0, job)
        if len(_jobs) > MAX_HISTORY:
            del _jobs[MAX_HISTORY:]
    return job


def _log(job, msg):
    job["log"].append(msg)
    print(f"[batch-{job['type']}-{job['id']}] {msg}", flush=True)


def get_all_jobs():
    return [
        {k: v for k, v in job.items() if k != "log"}
        for job in _jobs
    ]


def get_job(job_id):
    for job in _jobs:
        if job["id"] == job_id:
            return job
    return None


def record_fetch_releases(date_from, date_to, fetched_count, inserted_count):
    job = _new_job("fetch_releases", f"Get Releases ({date_from} to {date_to})", total=1)
    _log(job, f"Fetched {fetched_count} release(s), {inserted_count} new "
               f"({fetched_count - inserted_count} already in DB).")
    job["done"] = 1
    job["status"] = "done"
    job["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return job


def record_batch_release(label, lines):
    job = _new_job("batch_release", label, total=1)
    for line in lines:
        _log(job, line)
    job["done"] = 1
    job["status"] = "done"
    job["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return job


def start_fetch_art(release_ids):
    releases = db.get_releases_missing_art(release_ids)
    job = _new_job("fetch_art", "Album Art & Bio", total=len(releases))

    if not releases:
        job["status"] = "done"
        job["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _log(job, "Nothing to fetch.")
        return job

    t = threading.Thread(target=_run_fetch_art, args=(job, releases), daemon=True)
    t.start()
    return job


def _run_fetch_art(job, releases):
    total = len(releases)
    had_error = False
    for i, r in enumerate(releases, start=1):
        try:
            meta = metadata.get_release_meta(r["artist"], r["album"], ma_album_id=r.get("ma_album_id"))
            db.save_release_art_cache(r["id"], meta.get("art_url"), meta.get("bio"))
            _log(job, f"({i}/{total}) {r['artist']} - {r['album']}: "
                       f"art={'yes' if meta.get('art_url') else 'none'}")
        except Exception as e:
            had_error = True
            _log(job, f"({i}/{total}) {r['artist']} - {r['album']}: ERROR {e}")
        job["done"] = i

    job["status"] = "error" if had_error else "done"
    job["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _log(job, f"Finished ({job['done']}/{total}).")


def start_hype_scan(release_ids):
    releases = db.get_releases_missing_hype(release_ids)
    job = _new_job("hype_scan", "Hype Scan", total=len(releases))

    if not releases:
        job["status"] = "done"
        job["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _log(job, "Nothing to scan.")
        return job

    t = threading.Thread(target=_run_hype_scan, args=(job, releases), daemon=True)
    t.start()
    return job


def _run_hype_scan(job, releases):
    total = len(releases)
    had_error = False
    for i, r in enumerate(releases, start=1):
        try:
            result = hype_scraper.compute_band_hype(r["artist"])
            db.save_release_hype(
                r["id"],
                score=result["score"],
                tier=result["tier"],
                listeners=result["listeners"],
                playcount=result["playcount"],
                discog_count=result["discog_count"],
            )
            _log(job, f"({i}/{total}) {r['artist']} -> {result['tier']} ({result['score']:.1f})")
        except Exception as e:
            had_error = True
            _log(job, f"({i}/{total}) {r['artist']}: ERROR {e}")
        job["done"] = i

        # Politeness delay for Last.fm + MusicBrainz (max ~1 req/sec)
        time.sleep(1.0)

    job["status"] = "error" if had_error else "done"
    job["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _log(job, f"Finished ({job['done']}/{total}).")
