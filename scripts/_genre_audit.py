#!/usr/bin/env python3
"""One-off: look up each record on Discogs and dump current vs master genres.

Outputs .data-staging/genre-audit.json so the reconciliation can happen in a
review step rather than inline.
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORDS = REPO_ROOT / "records.json"
TOKEN = (REPO_ROOT / ".discogs-token").read_text().strip()
UA = "RecordCollectionBrowser/1.0 +https://github.com/Valerie-Freeman/record-collection"
API = "https://api.discogs.com"


def http_get(url):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Discogs token={TOKEN}",
        "User-Agent": UA,
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise


def strip_the(s):
    return re.sub(r"^(the|a|an)\s+", "", s.strip().lower())


def pick_master(results, artist, title, year_start):
    """Rank masters: prefer exact-ish artist+title match, then closest year."""
    def score(r):
        r_title = (r.get("title") or "").lower()
        r_artist_title = r_title
        artist_match = strip_the(artist) in r_artist_title
        title_match = strip_the(title) in r_artist_title
        year_diff = abs((int(r["year"]) if r.get("year") else 0) - year_start) if r.get("year") else 999
        return (not artist_match, not title_match, year_diff)

    masters = [r for r in results if r.get("type") == "master"]
    if not masters:
        return None
    masters.sort(key=score)
    return masters[0]


def lookup(record):
    q = urllib.parse.urlencode({
        "artist": record["artist"],
        "release_title": record["title"],
        "type": "master",
        "per_page": "5",
    })
    search = http_get(f"{API}/database/search?{q}")
    time.sleep(1.1)
    results = search.get("results", [])
    master = pick_master(results, record["artist"], record["title"], record["year"][0])
    if not master:
        return {"found": False, "candidates": [{"id": r.get("id"), "title": r.get("title"), "year": r.get("year")} for r in results[:3]]}
    master_id = master.get("master_id") or master.get("id")
    detail = http_get(f"{API}/masters/{master_id}")
    time.sleep(1.1)
    return {
        "found": True,
        "master_id": master_id,
        "master_url": f"https://www.discogs.com/master/{master_id}",
        "master_title": detail.get("title"),
        "master_year": detail.get("year"),
        "genres": detail.get("genres") or [],
        "styles": detail.get("styles") or [],
    }


def main():
    records = json.loads(RECORDS.read_text())
    out = []
    for i, r in enumerate(records, 1):
        print(f"[{i}/{len(records)}] {r['artist']} - {r['title']}", file=sys.stderr)
        try:
            info = lookup(r)
        except Exception as e:
            info = {"found": False, "error": str(e)}
        out.append({
            "index": i - 1,
            "artist": r["artist"],
            "title": r["title"],
            "year": r["year"],
            "current_genres": r["genres"],
            "discogs": info,
        })
    out_path = REPO_ROOT / ".data-staging" / "genre-audit.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"Wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
