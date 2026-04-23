#!/usr/bin/env python3
"""Add records to the collection from Discogs links.

Two subcommands:

  stage INPUT --out STAGING
    Parse INPUT (master/vinyl/rating/notes blocks separated by blank lines),
    fetch metadata from the Discogs public API, download and optimize cover
    art, and write a proposed record set to STAGING (JSON). Fails if any
    proposed record duplicates an existing (artist, title, year).

  apply STAGING
    Read STAGING and write the records into records.json (preserving the
    project's custom formatting), update artists.json and genres.json, and
    run the validator.

Input format (stdin or file):

    master: https://www.discogs.com/master/...
    vinyl: https://www.discogs.com/release/...
    rating: 4
    notes: optional text

    master:
    vinyl: https://www.discogs.com/sell/item/...
    rating: 3
    notes:

Records are separated by blank lines. master may be empty (release has no
master); vinyl is required. Rating is 1-5. notes may be empty.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORDS_JSON = REPO_ROOT / "records.json"
ARTISTS_JSON = REPO_ROOT / "artists.json"
GENRES_JSON = REPO_ROOT / "genres.json"
IMAGES_DIR = REPO_ROOT / "images"
STAGING_IMAGES = REPO_ROOT / ".data-staging" / "images"

USER_AGENT = "RecordCollectionBrowser/1.0 +https://github.com/Valerie-Freeman/record-collection"
API_BASE = "https://api.discogs.com"
MAX_IMAGE_BYTES = 100 * 1024
TARGET_DIM = 600
QUALITY_LEVELS = [85, 75, 65, 55, 45, 35]


# ---------- HTTP ----------

def http_get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                return data if binary else data.decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise
        except urllib.error.URLError:
            if attempt < 2:
                time.sleep(1)
                continue
            raise


def discogs_get(path):
    return json.loads(http_get(f"{API_BASE}{path}"))


# ---------- URL parsing ----------

URL_PATTERNS = [
    ("master", re.compile(r"discogs\.com/(?:[a-z]{2}/)?master/(\d+)")),
    ("release", re.compile(r"discogs\.com/(?:[a-z]{2}/)?release/(\d+)")),
    ("sell", re.compile(r"discogs\.com/(?:[a-z]{2}/)?sell/item/(\d+)")),
]


def parse_discogs_url(url):
    if not url:
        return None
    for kind, rx in URL_PATTERNS:
        m = rx.search(url)
        if m:
            return (kind, int(m.group(1)))
    return None


def resolve_to_release_id(url):
    """Resolve any vinyl URL (release or sell/item) to a release ID."""
    ref = parse_discogs_url(url)
    if ref is None:
        raise ValueError(f"Could not parse Discogs URL: {url}")
    kind, ident = ref
    if kind == "release":
        return ident
    if kind == "sell":
        listing = discogs_get(f"/marketplace/listings/{ident}")
        rel = listing.get("release", {}).get("id")
        if not rel:
            raise ValueError(f"Marketplace listing {ident} has no release reference")
        return rel
    raise ValueError(f"Vinyl URL must be a release or sell/item link, got: {url}")


# ---------- Input parsing ----------

def parse_input(text):
    """Parse blocks separated by blank lines."""
    blocks = re.split(r"\n\s*\n", text.strip())
    out = []
    for block_idx, block in enumerate(blocks, 1):
        record = {"master": "", "vinyl": "", "rating": None, "notes": ""}
        for line in block.splitlines():
            line = line.rstrip()
            if not line.strip():
                continue
            m = re.match(r"^(master|vinyl|rating|notes)\s*:\s*(.*)$", line)
            if not m:
                raise ValueError(f"Record {block_idx}: unrecognized line: {line!r}")
            key, value = m.group(1), m.group(2).strip()
            record[key] = value
        if not record["vinyl"]:
            raise ValueError(f"Record {block_idx}: vinyl link is required")
        if record["rating"] in (None, ""):
            raise ValueError(f"Record {block_idx}: rating is required")
        try:
            record["rating"] = int(record["rating"])
        except ValueError:
            raise ValueError(f"Record {block_idx}: rating must be an integer, got {record['rating']!r}")
        if not 1 <= record["rating"] <= 5:
            raise ValueError(f"Record {block_idx}: rating must be 1-5, got {record['rating']}")
        out.append(record)
    return out


# ---------- Slugs ----------

def slugify(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def artwork_path(artist, title):
    return f"images/{slugify(artist)}-{slugify(title)}.jpg"


# ---------- Image processing ----------

def optimize_image(path: Path):
    """Resize to 600x600 center-crop, iterate JPEG quality until under 100KB."""
    subprocess.run(
        ["sips", "--resampleHeightWidthMax", "800", str(path)],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["sips", "-c", str(TARGET_DIM), str(TARGET_DIM), str(path)],
        check=True, capture_output=True,
    )
    tmp = path.with_suffix(".tmp.jpg")
    for q in QUALITY_LEVELS:
        subprocess.run(
            ["sips", "-s", "format", "jpeg", "-s", "formatOptions", str(q),
             str(path), "--out", str(tmp)],
            check=True, capture_output=True,
        )
        shutil.move(str(tmp), str(path))
        if path.stat().st_size < MAX_IMAGE_BYTES:
            return q
    return QUALITY_LEVELS[-1]


def download_image(url: Path, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = http_get(url, binary=True)
    dest.write_bytes(data)


def pick_primary_image(images):
    for img in images or []:
        if img.get("type") == "primary" and img.get("uri"):
            return img["uri"]
    if images:
        return images[0].get("uri")
    return None


# ---------- Discogs metadata ----------

def build_proposal(master_url, vinyl_url, rating, notes):
    master = None
    if master_url:
        ref = parse_discogs_url(master_url)
        if not ref or ref[0] != "master":
            raise ValueError(f"Expected /master/ URL, got: {master_url}")
        master = discogs_get(f"/masters/{ref[1]}")

    release_id = resolve_to_release_id(vinyl_url)
    release = discogs_get(f"/releases/{release_id}")

    source = master or release
    year = source.get("year")
    genres_list = source.get("genres", []) or []
    styles_list = source.get("styles", []) or []
    img_url = pick_primary_image(source.get("images")) or pick_primary_image(release.get("images"))

    artists = release.get("artists") or []
    artist = release.get("artists_sort") or (artists[0].get("name") if artists else None)
    artist = re.sub(r"\s+\(\d+\)$", "", artist or "")
    title = release.get("title")

    tracks = []
    positions_seen = {}
    for t in release.get("tracklist", []):
        if t.get("type_") and t.get("type_") != "track":
            continue
        pos = (t.get("position") or "").strip()
        m = re.match(r"^([A-Za-z]+)", pos)
        side = m.group(1).upper() if m else ""
        tracks.append({"side": side, "title": t.get("title", ""), "_position": pos})
        positions_seen.setdefault(pos, 0)
        positions_seen[pos] += 1

    flags = []
    if master:
        # sanity: year from master takes priority; warn if release year differs materially
        rel_year = release.get("year")
        if rel_year and year and rel_year != year:
            flags.append(f"release year {rel_year} differs from master year {year}; using master year")
    dup_positions = [p for p, n in positions_seen.items() if n > 1 and p]
    if dup_positions:
        flags.append(f"duplicate tracklist positions: {', '.join(dup_positions)} (verify manually)")
    blank_sides = [t for t in tracks if not t["side"]]
    if blank_sides:
        flags.append(f"{len(blank_sides)} track(s) missing side info")
    if not tracks:
        flags.append("no tracks found in release")
    if not year:
        flags.append("no year found on master or release")
    if not genres_list and not styles_list:
        flags.append("no Discogs genres or styles found")

    # Default proposed genres: Discogs genres + styles, deduped, preserving order.
    proposed_genres = []
    for g in genres_list + styles_list:
        if g and g not in proposed_genres:
            proposed_genres.append(g)

    record = {
        "artwork": artwork_path(artist, title),
        "artist": artist,
        "title": title,
        "year": year,
        "rating": rating,
        "genres": proposed_genres,
    }
    if notes:
        record["notes"] = notes
    record["tracks"] = [{"side": t["side"], "title": t["title"]} for t in tracks]

    return record, flags, img_url


# ---------- Data-file I/O ----------

def load_existing():
    records = json.loads(RECORDS_JSON.read_text())
    artists = json.loads(ARTISTS_JSON.read_text())
    genres = json.loads(GENRES_JSON.read_text())
    return records, artists, genres


def artist_sort_key(name):
    return re.sub(r"^The\s+", "", name, flags=re.IGNORECASE).lower()


def format_record(r, is_last):
    lines = ["  {"]
    lines.append(f'    "artwork": {json.dumps(r["artwork"])},')
    lines.append(f'    "artist": {json.dumps(r["artist"])},')
    lines.append(f'    "title": {json.dumps(r["title"])},')
    lines.append(f'    "year": {r["year"]},')
    lines.append(f'    "rating": {r["rating"]},')
    genres_str = "[" + ", ".join(json.dumps(g) for g in r["genres"]) + "]"
    tail_comma = "," if (r.get("notes") or r.get("tracks")) else ""
    lines.append(f'    "genres": {genres_str}{tail_comma}')
    if r.get("notes"):
        tail_comma = "," if r.get("tracks") else ""
        lines.append(f'    "notes": {json.dumps(r["notes"])}{tail_comma}')
    if r.get("tracks"):
        lines.append('    "tracks": [')
        track_lines = [
            f'      {{ "side": {json.dumps(t["side"])}, "title": {json.dumps(t["title"])} }}'
            for t in r["tracks"]
        ]
        lines.append(",\n".join(track_lines))
        lines.append('    ]')
    lines.append("  }" + ("" if is_last else ","))
    return "\n".join(lines)


def append_records_to_file(new_records):
    content = RECORDS_JSON.read_text()
    if not content.rstrip().endswith("]"):
        raise RuntimeError("records.json does not end with ']'")
    idx = content.rfind("]")
    prefix = content[:idx]
    last_brace = prefix.rfind("  }")
    if last_brace < 0:
        # Empty array -- unlikely but handle
        prefix_new = prefix
    else:
        prefix_new = prefix[: last_brace + 3] + "," + prefix[last_brace + 3 :]

    new_text = prefix_new.rstrip() + "\n"
    for i, r in enumerate(new_records):
        new_text += format_record(r, is_last=(i == len(new_records) - 1))
        new_text += "\n"
    new_text += "]\n"
    RECORDS_JSON.write_text(new_text)


def write_sorted_list(path, items, sort_key):
    items = sorted(set(items), key=sort_key)
    lines = ["["]
    for i, item in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        lines.append(f"  {json.dumps(item)}{comma}")
    lines.append("]")
    path.write_text("\n".join(lines) + "\n")


# ---------- stage ----------

def cmd_stage(args):
    input_text = Path(args.input).read_text() if args.input != "-" else sys.stdin.read()
    inputs = parse_input(input_text)

    existing_records, existing_artists, existing_genres = load_existing()
    existing_tuples = {(r["artist"], r["title"], r["year"]) for r in existing_records}
    existing_tuples_ci = {
        (r["artist"].lower(), r["title"].lower(), r["year"]): (r["artist"], r["title"])
        for r in existing_records
    }
    artists_set = set(existing_artists)
    artists_ci = {a.lower(): a for a in existing_artists}
    genres_set = set(existing_genres)

    staged = []
    image_tasks = []  # (staging_path, final_path, img_url)

    failures = []
    for i, inp in enumerate(inputs, 1):
        try:
            record, flags, img_url = build_proposal(
                inp["master"], inp["vinyl"], inp["rating"], inp["notes"]
            )
        except Exception as e:
            failures.append(f"Record {i}: {e}")
            continue

        key = (record["artist"], record["title"], record["year"])
        key_ci = (record["artist"].lower(), record["title"].lower(), record["year"])
        if key in existing_tuples:
            failures.append(
                f"Record {i}: duplicate of existing {record['artist']!r} / "
                f"{record['title']!r} / {record['year']}"
            )
            continue
        if key_ci in existing_tuples_ci:
            existing = existing_tuples_ci[key_ci]
            flags.append(
                f"case-insensitive near-duplicate of existing "
                f"{existing[0]!r} / {existing[1]!r} ({record['year']}); "
                f"verify before applying"
            )

        if record["artist"].lower() in artists_ci and record["artist"] not in artists_set:
            existing_artist = artists_ci[record["artist"].lower()]
            flags.append(
                f"artist {record['artist']!r} nearly matches existing "
                f"{existing_artist!r} (case/spelling differs); reuse existing?"
            )
        elif record["artist"] not in artists_set:
            flags.append(f"new artist: {record['artist']!r}")
        new_genres = [g for g in record["genres"] if g not in genres_set]
        if new_genres:
            flags.append(f"new genre(s): {', '.join(repr(g) for g in new_genres)}")

        # Queue image
        final_path = REPO_ROOT / record["artwork"]
        staging_path = STAGING_IMAGES / f"{slugify(record['artist'])}-{slugify(record['title'])}.jpg"
        image_tasks.append((staging_path, final_path, img_url))

        record["_flags"] = flags
        record["_discogs"] = {
            "master_url": inp["master"] or None,
            "vinyl_url": inp["vinyl"],
            "image_url": img_url,
        }
        staged.append(record)

    if failures:
        print("Staging failed:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    # Download + optimize images
    STAGING_IMAGES.mkdir(parents=True, exist_ok=True)
    for staging_path, final_path, img_url in image_tasks:
        if not img_url:
            print(f"WARNING: no image URL for {final_path.name}", file=sys.stderr)
            continue
        print(f"  downloading {final_path.name}...", file=sys.stderr)
        download_image(img_url, staging_path)
        q = optimize_image(staging_path)
        size = staging_path.stat().st_size
        print(f"    {size} bytes @ q{q}", file=sys.stderr)
        if size >= MAX_IMAGE_BYTES:
            print(f"    WARNING: still over 100KB", file=sys.stderr)

    # Write staging JSON
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"records": staged}, indent=2) + "\n")
    print(f"Staged {len(staged)} record(s) to {out_path}", file=sys.stderr)

    # Summary to stdout (the skill will surface this to the user)
    for i, r in enumerate(staged, 1):
        print(f"\n[{i}] {r['artist']} - {r['title']} ({r['year']}) {r['rating']}★")
        print(f"    genres: {', '.join(r['genres'])}")
        if r.get("notes"):
            print(f"    notes: {r['notes']}")
        print(f"    tracks: {len(r['tracks'])}")
        for flag in r["_flags"]:
            print(f"    FLAG: {flag}")
    return 0


# ---------- apply ----------

def cmd_apply(args):
    staging = json.loads(Path(args.staging).read_text())
    proposals = staging.get("records", [])
    if not proposals:
        print("No records to apply.", file=sys.stderr)
        return 1

    # Strip internal fields
    records_to_add = []
    for r in proposals:
        clean = {k: v for k, v in r.items() if not k.startswith("_")}
        records_to_add.append(clean)

    # Move staged images into place
    for r in records_to_add:
        final_path = REPO_ROOT / r["artwork"]
        staging_path = STAGING_IMAGES / final_path.name
        if staging_path.exists():
            final_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staging_path), str(final_path))
        elif not final_path.exists():
            print(f"ERROR: no staged image for {r['artwork']}", file=sys.stderr)
            return 1

    append_records_to_file(records_to_add)

    existing_artists = set(json.loads(ARTISTS_JSON.read_text()))
    existing_genres = set(json.loads(GENRES_JSON.read_text()))
    for r in records_to_add:
        existing_artists.add(r["artist"])
        for g in r["genres"]:
            existing_genres.add(g)
    write_sorted_list(ARTISTS_JSON, existing_artists, artist_sort_key)
    write_sorted_list(GENRES_JSON, existing_genres, str.lower)

    print(f"Applied {len(records_to_add)} record(s).", file=sys.stderr)

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "validate_records.py")],
        cwd=str(REPO_ROOT),
    )
    return result.returncode


# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_stage = sub.add_parser("stage", help="Stage proposed records from an input file")
    p_stage.add_argument("input", help="Path to input file, or '-' for stdin")
    p_stage.add_argument("--out", default=".data-staging/staging.json", help="Staging JSON output path")
    p_stage.set_defaults(func=cmd_stage)

    p_apply = sub.add_parser("apply", help="Apply a staging JSON to the data files")
    p_apply.add_argument("staging", nargs="?", default=".data-staging/staging.json")
    p_apply.set_defaults(func=cmd_apply)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
