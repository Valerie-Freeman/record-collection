#!/usr/bin/env python3
"""Add records to the collection from Discogs links.

Two subcommands:

  stage INPUT --out STAGING
    Parse INPUT (master/vinyl/rating/notes blocks separated by blank lines),
    fetch metadata from the Discogs public API, download and optimize cover
    art, and write a proposed record set to STAGING (JSON). Fails if any
    proposed record duplicates an existing (artist, title, year).

  apply STAGING [--dry-run]
    Read STAGING, move staged cover art into images/ (artwork stays in the
    repo and is served by GitHub Pages), and insert the records, their genre
    edges, and tracks into the Supabase database in one transaction. Artists
    and genres auto-create via the canonical-list triggers. With --dry-run the
    inserts run and the deferred constraints are checked, then everything rolls
    back, so the batch can be validated against the live schema without
    persisting. Requires psycopg2 and a .env with PROJECT_REF and DB_PASSWORD.

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

try:
    import psycopg2
    from psycopg2 import errors as psycopg2_errors
except ImportError:  # surfaced with a clear message in connect()
    psycopg2 = None
    psycopg2_errors = None

REPO_ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = REPO_ROOT / "images"
STAGING_IMAGES = REPO_ROOT / ".data-staging" / "images"
ENV_FILE = REPO_ROOT / ".env"

USER_AGENT = "RecordCollectionBrowser/1.0 +https://github.com/Valerie-Freeman/record-collection"
API_BASE = "https://api.discogs.com"
MAX_IMAGE_BYTES = 100 * 1024
TARGET_DIM = 600
QUALITY_LEVELS = [85, 75, 65, 55, 45, 35, 25, 15]


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
        # Skip fully-empty blocks (unused slots in the ten-block skeleton).
        if not record["vinyl"] and not record["master"] and record["rating"] in (None, "") and not record["notes"]:
            continue
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
    """Scale longest edge to TARGET_DIM (preserving aspect ratio, no cropping),
    iterate JPEG quality until under 100KB."""
    subprocess.run(
        ["sips", "-Z", str(TARGET_DIM), str(path)],
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

    is_compilation = False
    for fmt in release.get("formats", []) or []:
        for desc in fmt.get("descriptions", []) or []:
            if desc.lower() == "compilation":
                is_compilation = True
    if is_compilation:
        flags.append(
            f"compilation detected; year set to [{year}, {year}]. Edit "
            f".data-staging/staging.json to set the real [earliest, latest] "
            f"range from the tracklist (see ADR-002)"
        )

    # Default proposed genres: Discogs genres + styles, deduped, preserving order.
    proposed_genres = []
    for g in genres_list + styles_list:
        if g and g not in proposed_genres:
            proposed_genres.append(g)

    year_range = [year, year] if year is not None else None
    record = {
        "artwork": artwork_path(artist, title),
        "artist": artist,
        "title": title,
        "year": year_range,
        "rating": rating,
        "genres": proposed_genres,
    }
    if notes:
        record["notes"] = notes
    record["discogs_url"] = vinyl_url
    record["tracks"] = [{"side": t["side"], "title": t["title"]} for t in tracks]

    return record, flags, img_url


# ---------- Supabase connection ----------

def load_env():
    """Parse .env at the repo root into a dict. Bare KEY=VALUE lines, no quotes."""
    if not ENV_FILE.exists():
        sys.exit(f"{ENV_FILE} not found; cannot connect to Supabase")
    env = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def connect():
    """Open a direct Postgres connection to Supabase (postgres role, bypasses RLS)."""
    if psycopg2 is None:
        sys.exit("psycopg2 is required for database access: pip install psycopg2-binary")
    env = load_env()
    project_ref = env.get("PROJECT_REF")
    db_password = env.get("DB_PASSWORD")
    if not project_ref or not db_password:
        sys.exit("PROJECT_REF and DB_PASSWORD must be set in .env")
    return psycopg2.connect(
        host=f"db.{project_ref}.supabase.co",
        port=5432,
        dbname="postgres",
        user="postgres",
        password=db_password,
        sslmode="require",
    )


def load_existing_from_db(conn):
    """Read existing record tuples plus the canonical artist and genre lists.

    The database is the source of truth now, so duplicate detection and the
    new-artist / new-genre flags during review compare against it, not the
    frozen JSON snapshot.
    """
    with conn.cursor() as cur:
        cur.execute("select artist, title, year_start, year_end from records")
        records = [
            {"artist": a, "title": t, "year": [ys, ye]}
            for (a, t, ys, ye) in cur.fetchall()
        ]
        cur.execute("select name from artists")
        artists = [row[0] for row in cur.fetchall()]
        cur.execute("select name from genres")
        genres = [row[0] for row in cur.fetchall()]
    return records, artists, genres


def insert_records(conn, records, dry_run=False):
    """Insert records, their genre edges, and tracks in one transaction.

    Artists and genres auto-create via the canonical-list triggers; the
    deferred constraint triggers verify the bidirectional invariant at COMMIT.
    With dry_run, the deferred constraints are forced to fire immediately and
    the whole transaction rolls back, so the batch is validated against the
    live schema without persisting anything.
    """
    with conn.cursor() as cur:
        for r in records:
            cur.execute(
                "insert into records "
                "(artist, title, year_start, year_end, rating, notes, discogs_url, artwork) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s) returning id",
                (
                    r["artist"], r["title"], r["year"][0], r["year"][1],
                    r["rating"], r.get("notes"), r["discogs_url"], r["artwork"],
                ),
            )
            record_id = cur.fetchone()[0]

            for genre in r["genres"]:
                cur.execute(
                    "insert into record_genres (record_id, genre) values (%s, %s)",
                    (record_id, genre),
                )

            position_by_side = {}
            for track in r.get("tracks", []):
                side = track["side"]
                position_by_side[side] = position_by_side.get(side, 0) + 1
                cur.execute(
                    "insert into tracks (record_id, side, position, title) "
                    "values (%s, %s, %s, %s)",
                    (record_id, side, position_by_side[side], track["title"]),
                )

        if dry_run:
            # Force the deferred canonical-list triggers to fire now, then discard.
            cur.execute("set constraints all immediate")

    if dry_run:
        conn.rollback()
    else:
        conn.commit()


# ---------- stage ----------

def cmd_stage(args):
    input_text = Path(args.input).read_text() if args.input != "-" else sys.stdin.read()
    inputs = parse_input(input_text)

    conn = connect()
    try:
        existing_records, existing_artists, existing_genres = load_existing_from_db(conn)
    finally:
        conn.close()
    existing_tuples = {(r["artist"], r["title"], tuple(r["year"])) for r in existing_records}
    existing_tuples_ci = {
        (r["artist"].lower(), r["title"].lower(), tuple(r["year"])): (r["artist"], r["title"])
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

        year_tuple = tuple(record["year"]) if record["year"] else None
        key = (record["artist"], record["title"], year_tuple)
        key_ci = (record["artist"].lower(), record["title"].lower(), year_tuple)
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

    # Guard: the database requires a resolved year range and at least one genre.
    for r in records_to_add:
        year = r.get("year")
        if not year or year[0] is None or year[1] is None:
            print(
                f"ERROR: {r['artist']} - {r['title']} has no year range; "
                f"set it in {args.staging} before applying",
                file=sys.stderr,
            )
            return 1
        if not r.get("genres"):
            print(
                f"ERROR: {r['artist']} - {r['title']} has no genres; "
                f"set them in {args.staging} before applying",
                file=sys.stderr,
            )
            return 1

    # Move staged images into images/ (artwork stays in the repo, served by Pages).
    # Done before the insert so a missing image fails fast without touching the DB.
    # Skipped under --dry-run, which only validates the database insert and would
    # otherwise leave moved files behind after the transaction rolls back.
    if not args.dry_run:
        for r in records_to_add:
            final_path = REPO_ROOT / r["artwork"]
            staging_path = STAGING_IMAGES / final_path.name
            if staging_path.exists():
                final_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(staging_path), str(final_path))
            elif not final_path.exists():
                print(f"ERROR: no staged image for {r['artwork']}", file=sys.stderr)
                return 1

    conn = connect()
    try:
        insert_records(conn, records_to_add, dry_run=args.dry_run)
    except psycopg2.Error as e:
        conn.rollback()
        conn.close()
        if psycopg2_errors and isinstance(e, psycopg2_errors.UniqueViolation):
            sys.exit(
                "\nDuplicate record already in the database "
                "(same artist, title, and year range). Nothing was inserted."
            )
        sys.exit(f"\nDatabase insert failed, rolled back: {e}")
    conn.close()

    if args.dry_run:
        print(
            f"[dry-run] Validated {len(records_to_add)} record(s) against the live "
            f"schema; rolled back, nothing persisted.",
            file=sys.stderr,
        )
        return 0

    print(f"Inserted {len(records_to_add)} record(s) into the database:", file=sys.stderr)
    for r in records_to_add:
        print(f"  - {r['artist']} - {r['title']} ({r['year'][0]}-{r['year'][1]})", file=sys.stderr)
    print(
        "\nThe row data is live now. Commit and push the new image file(s) under "
        "images/ so GitHub Pages can serve the cover art.",
        file=sys.stderr,
    )
    return 0


# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_stage = sub.add_parser("stage", help="Stage proposed records from an input file")
    p_stage.add_argument("input", help="Path to input file, or '-' for stdin")
    p_stage.add_argument("--out", default=".data-staging/staging.json", help="Staging JSON output path")
    p_stage.set_defaults(func=cmd_stage)

    p_apply = sub.add_parser("apply", help="Insert a staging JSON into the database")
    p_apply.add_argument("staging", nargs="?", default=".data-staging/staging.json")
    p_apply.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the inserts and deferred-constraint checks, then roll back without persisting.",
    )
    p_apply.set_defaults(func=cmd_apply)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
