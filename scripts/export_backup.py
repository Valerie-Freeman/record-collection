#!/usr/bin/env python3
"""Export the full collection from Supabase to a single JSON snapshot.

Reads every table over the public REST endpoint (anon key, public-read RLS) and
writes a deterministic, restorable snapshot to backup/collection.json. Run by
.github/workflows/backup.yml on a schedule; the workflow commits the file only
when its contents change, so the snapshot doubles as a git-versioned audit log
of the collection.

Deterministic ordering (records by artist/title/year, lists sorted, genres and
tracks sorted within each record) is the point: it means the file changes only
when the data changes, not when rows come back from Postgres in a different
order. No surrogate ids are stored; the (artist, title, year) tuple identifies a
record, and ids regenerate on restore.

Uses only the standard library. Requires SUPABASE_URL and SUPABASE_ANON_KEY in
the environment.
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "backup" / "collection.json"

URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_ANON_KEY", "")
if not URL or not KEY:
    sys.exit("SUPABASE_URL and SUPABASE_ANON_KEY must be set in the environment.")

RECORDS_SELECT = (
    "artist,title,year_start,year_end,rating,notes,discogs_url,artwork,"
    "record_genres(genre),tracks(side,position,title)"
)


def get(path, extra_headers=None):
    """GET /rest/v1/<path>, returning (parsed_json, content_range_header)."""
    req = urllib.request.Request(f"{URL}/rest/v1/{path}")
    req.add_header("apikey", KEY)
    req.add_header("Authorization", f"Bearer {KEY}")
    for key, value in (extra_headers or {}).items():
        req.add_header(key, value)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8")), resp.headers.get("Content-Range")


def casefold(value):
    return value.casefold()


def main():
    records_raw, content_range = get(
        f"records?select={RECORDS_SELECT}", {"Prefer": "count=exact"}
    )

    # Truncation guard: PostgREST caps a response at ~1000 rows. If the table
    # holds more than we fetched, the snapshot would be silently incomplete.
    if content_range and "/" in content_range:
        total = content_range.rsplit("/", 1)[-1]
        if total != "*" and int(total) != len(records_raw):
            sys.exit(
                f"Fetched {len(records_raw)} records but the table has {total}. "
                "Add pagination to export_backup.py before trusting this snapshot."
            )

    artists_raw, _ = get("artists?select=name")
    genres_raw, _ = get("genres?select=name")

    records = []
    for row in records_raw:
        record = {
            "artist": row["artist"],
            "title": row["title"],
            "year": [row["year_start"], row["year_end"]],
            "rating": row["rating"],
        }
        if row.get("notes"):
            record["notes"] = row["notes"]
        record["discogs_url"] = row["discogs_url"]
        record["artwork"] = row["artwork"]
        record["genres"] = sorted(
            (g["genre"] for g in row.get("record_genres", [])), key=casefold
        )
        tracks = sorted(
            row.get("tracks", []), key=lambda t: (t["side"], t["position"])
        )
        if tracks:
            record["tracks"] = [
                {"side": t["side"], "position": t["position"], "title": t["title"]}
                for t in tracks
            ]
        records.append(record)

    records.sort(
        key=lambda r: (r["artist"].casefold(), r["title"].casefold(), r["year"][0], r["year"][1])
    )
    artists = sorted((a["name"] for a in artists_raw), key=casefold)
    genres = sorted((g["name"] for g in genres_raw), key=casefold)

    snapshot = {
        "_comment": (
            "Generated backup of the Supabase collection. Do not edit by hand; this "
            "file is overwritten by .github/workflows/backup.yml. It is a restore "
            "artifact and a git-versioned audit log, not the source of truth (the "
            "database is). No timestamp is stored here so the file changes only when "
            "the collection changes; the commit date records when."
        ),
        "counts": {
            "records": len(records),
            "artists": len(artists),
            "genres": len(genres),
        },
        "artists": artists,
        "genres": genres,
        "records": records,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(
        f"Wrote {OUT.relative_to(REPO_ROOT)}: "
        f"{len(records)} records, {len(artists)} artists, {len(genres)} genres."
    )


if __name__ == "__main__":
    main()
