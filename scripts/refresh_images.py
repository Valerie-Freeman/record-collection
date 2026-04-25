#!/usr/bin/env python3
"""Refresh cover-art images for every record by re-fetching from Discogs.

Two subcommands:

  propose
    Walk records.json. For each record without a discogs_url, search Discogs
    by artist + title + year and propose a release URL match. Write a report
    to .data-staging/refresh-proposals.json so the user can spot-check and
    correct any wrong matches before applying.

  apply
    Read .data-staging/refresh-proposals.json. For each entry, download the
    primary image from its discogs_url, run optimize_image (the fixed
    version, no cropping), and replace the image in images/. Write the
    discogs_url back into records.json. Run the validator at the end.

Workflow:

  1. python3 scripts/refresh_images.py propose
  2. Open .data-staging/refresh-proposals.json. Fix any wrong proposed_url
     entries by replacing them with a Discogs /release/<id> URL.
  3. python3 scripts/refresh_images.py apply
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_records import (
    REPO_ROOT,
    RECORDS_JSON,
    discogs_get,
    download_image,
    optimize_image,
    pick_primary_image,
    resolve_to_release_id,
)

PROPOSALS_PATH = REPO_ROOT / ".data-staging" / "refresh-proposals.json"
KNOWN_URLS_FROM_STAGING = REPO_ROOT / ".data-staging" / "staging.json"

# Stay under Discogs unauthenticated rate limit (25 req/min).
THROTTLE_SECONDS = 2.5

# Records where the user explicitly chose the release image over the master.
# Keyed by discogs_url. Apply skips the master-image swap for these.
PREFER_RELEASE_IMAGE = {
    "https://www.discogs.com/release/1953621-John-Mayer-Continuum",
}


def throttle():
    time.sleep(THROTTLE_SECONDS)


def load_known_urls():
    """Pull URLs from any leftover .data-staging/staging.json (today's batch)."""
    if not KNOWN_URLS_FROM_STAGING.exists():
        return {}
    try:
        data = json.loads(KNOWN_URLS_FROM_STAGING.read_text())
    except Exception:
        return {}
    out = {}
    for r in data.get("records", []):
        artwork = r.get("artwork")
        url = (r.get("_discogs") or {}).get("vinyl_url")
        if artwork and url:
            out[artwork] = url
    return out


def search_discogs(artist, title, year):
    """Search Discogs for releases matching artist + title; return raw results list.
    Falls back from strict (year + Vinyl format) to broader queries on no-match."""
    from urllib.parse import urlencode

    def query(params):
        qs = urlencode(params)
        return discogs_get(f"/database/search?{qs}").get("results", []) or []

    base = {
        "type": "release",
        "artist": artist,
        "release_title": title,
        "per_page": "10",
    }

    # Attempt 1: year + Vinyl
    if year:
        results = query({**base, "format": "Vinyl", "year": str(year)})
        if results:
            return results
        throttle()
    # Attempt 2: Vinyl only (compilations: year[0] is source year, not release year)
    results = query({**base, "format": "Vinyl"})
    if results:
        return results
    throttle()
    # Attempt 3: no format filter
    return query(base)


def best_match(results, year):
    """Pick the top-scoring result. Prefer year match, then format=Vinyl, then community count."""
    if not results:
        return None

    def score(r):
        s = 0
        if year and r.get("year") and str(r["year"]) == str(year):
            s += 100
        formats = r.get("format") or []
        if "Vinyl" in formats:
            s += 50
        if "LP" in formats:
            s += 10
        community = r.get("community") or {}
        s += min(community.get("have", 0) // 10, 30)
        return s

    return max(results, key=score)


def result_url(r):
    uri = r.get("uri") or ""
    if uri.startswith("/"):
        return f"https://www.discogs.com{uri}"
    return uri


def cmd_propose(args):
    records = json.loads(RECORDS_JSON.read_text())
    known_urls = load_known_urls()

    # Reuse any existing proposals that already have a URL.
    prior_by_artwork = {}
    if PROPOSALS_PATH.exists():
        try:
            prior = json.loads(PROPOSALS_PATH.read_text())
            for p in prior.get("proposals", []):
                if p.get("discogs_url"):
                    prior_by_artwork[p["artwork"]] = p
        except Exception:
            pass

    PROPOSALS_PATH.parent.mkdir(parents=True, exist_ok=True)

    proposals = []
    for i, r in enumerate(records, 1):
        artwork = r["artwork"]
        artist = r["artist"]
        title = r["title"]
        year_range = r.get("year") or [None, None]
        year_for_search = year_range[0] if year_range and year_range[0] not in (0, None) else None

        if artwork in prior_by_artwork:
            print(f"[{i:2d}/{len(records)}] {artist} - {title}: keeping prior proposal")
            proposals.append(prior_by_artwork[artwork])
            continue

        existing_url = r.get("discogs_url")
        if existing_url:
            print(f"[{i:2d}/{len(records)}] {artist} - {title}: already has discogs_url, keeping")
            proposals.append({
                "artwork": artwork,
                "artist": artist,
                "title": title,
                "year": year_range,
                "discogs_url": existing_url,
                "source": "existing",
                "alternatives": [],
            })
            continue

        if artwork in known_urls:
            print(f"[{i:2d}/{len(records)}] {artist} - {title}: using URL from staging.json")
            proposals.append({
                "artwork": artwork,
                "artist": artist,
                "title": title,
                "year": year_range,
                "discogs_url": known_urls[artwork],
                "source": "staging",
                "alternatives": [],
            })
            continue

        print(f"[{i:2d}/{len(records)}] {artist} - {title} ({year_for_search}): searching Discogs...")
        try:
            results = search_discogs(artist, title, year_for_search)
        except Exception as e:
            print(f"    SEARCH FAILED: {e}", file=sys.stderr)
            proposals.append({
                "artwork": artwork,
                "artist": artist,
                "title": title,
                "year": year_range,
                "discogs_url": None,
                "source": "search-failed",
                "error": str(e),
                "alternatives": [],
            })
            throttle()
            continue
        throttle()

        top = best_match(results, year_for_search)
        if not top:
            print(f"    NO MATCH FOUND")
            proposals.append({
                "artwork": artwork,
                "artist": artist,
                "title": title,
                "year": year_range,
                "discogs_url": None,
                "source": "no-match",
                "alternatives": [],
            })
            continue

        chosen_url = result_url(top)
        alt_summary = []
        for r2 in results[:5]:
            alt_summary.append({
                "title": r2.get("title"),
                "year": r2.get("year"),
                "format": r2.get("format"),
                "country": r2.get("country"),
                "url": result_url(r2),
            })
        print(f"    -> {chosen_url}  ({top.get('title')} | {top.get('year')} | {top.get('country')})")
        proposals.append({
            "artwork": artwork,
            "artist": artist,
            "title": title,
            "year": year_range,
            "discogs_url": chosen_url,
            "source": "search",
            "search_match_year": top.get("year"),
            "search_match_country": top.get("country"),
            "alternatives": alt_summary,
        })

    PROPOSALS_PATH.write_text(json.dumps({"proposals": proposals}, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(proposals)} proposals to {PROPOSALS_PATH}")
    missing = [p for p in proposals if not p.get("discogs_url")]
    if missing:
        print(f"WARNING: {len(missing)} record(s) have no discogs_url. Edit the file before applying:")
        for p in missing:
            print(f"  - {p['artist']} - {p['title']}")
    return 0


def cmd_apply(args):
    if not PROPOSALS_PATH.exists():
        print(f"ERROR: {PROPOSALS_PATH} not found. Run 'propose' first.", file=sys.stderr)
        return 1

    data = json.loads(PROPOSALS_PATH.read_text())
    proposals = data.get("proposals", [])

    missing = [p for p in proposals if not p.get("discogs_url")]
    if missing:
        print(f"ERROR: {len(missing)} proposal(s) have no discogs_url. Fix the report first.", file=sys.stderr)
        for p in missing:
            print(f"  - {p['artist']} - {p['title']}", file=sys.stderr)
        return 1

    # Index records.json by artwork (unique enough)
    records = json.loads(RECORDS_JSON.read_text())
    by_artwork = {r["artwork"]: r for r in records}

    failures = []
    for i, p in enumerate(proposals, 1):
        artwork = p["artwork"]
        url = p["discogs_url"]
        record = by_artwork.get(artwork)
        if not record:
            failures.append(f"{artwork}: not found in records.json")
            continue

        print(f"[{i:2d}/{len(proposals)}] {p['artist']} - {p['title']}")

        try:
            release_id = resolve_to_release_id(url)
            throttle()
            release = discogs_get(f"/releases/{release_id}")
            throttle()
        except Exception as e:
            failures.append(f"{artwork}: failed to fetch release ({e})")
            continue

        img_url = None
        img_source = "release"
        master_id = release.get("master_id")
        if master_id and url not in PREFER_RELEASE_IMAGE:
            try:
                master = discogs_get(f"/masters/{master_id}")
                throttle()
                img_url = pick_primary_image(master.get("images"))
                if img_url:
                    img_source = "master"
            except Exception as e:
                print(f"    master fetch failed ({e}), falling back to release image", file=sys.stderr)
        if not img_url:
            img_url = pick_primary_image(release.get("images"))
        if not img_url:
            failures.append(f"{artwork}: no primary image on release {release_id} or its master")
            continue
        print(f"    image source: {img_source}")

        final_path = REPO_ROOT / artwork
        try:
            download_image(img_url, final_path)
            q = optimize_image(final_path)
            print(f"    image refreshed @ q{q}, {final_path.stat().st_size} bytes")
        except Exception as e:
            failures.append(f"{artwork}: image processing failed ({e})")
            continue

        record["discogs_url"] = url

    if failures:
        print("\nFAILURES:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)

    # Rewrite records.json preserving the existing custom formatting
    rewrite_records_json(records)
    print(f"Updated records.json")

    if failures:
        print(f"\n{len(failures)} record(s) failed; not running validator.", file=sys.stderr)
        return 1

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "validate_records.py")],
        cwd=str(REPO_ROOT),
    )
    return result.returncode


def rewrite_records_json(records):
    """Rewrite records.json using the same custom format as add_records.append_records_to_file."""
    parts = ["[\n"]
    for i, r in enumerate(records):
        ordered = {}
        for key in ("artwork", "artist", "title", "year", "rating", "genres"):
            ordered[key] = r[key]
        if r.get("notes"):
            ordered["notes"] = r["notes"]
        ordered["discogs_url"] = r["discogs_url"]
        if r.get("tracks"):
            ordered["tracks"] = [{"side": t["side"], "title": t["title"]} for t in r["tracks"]]
        dumped = json.dumps(ordered, indent=2, ensure_ascii=False)
        indented = "\n".join("  " + line for line in dumped.splitlines())
        parts.append(indented)
        parts.append("," if i < len(records) - 1 else "")
        parts.append("\n")
    parts.append("]\n")
    RECORDS_JSON.write_text("".join(parts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("propose", help="Search Discogs and write a proposals report")
    sub.add_parser("apply", help="Apply approved proposals: refresh images and update records.json")
    args = parser.parse_args()
    if args.cmd == "propose":
        return cmd_propose(args)
    if args.cmd == "apply":
        return cmd_apply(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
