#!/usr/bin/env python3
"""One-shot import of records.json, artists.json, and genres.json into Supabase.

Reads the three canonical JSON files at the repo root and inserts their rows
into the Supabase Postgres database in dependency order:

    artists -> genres -> records -> record_genres -> tracks

The whole import runs in a single transaction so the schema's deferred
constraint triggers (canonical-list invariant, records-must-have-genre) all
fire at COMMIT against a fully-populated database.

Usage:

    python3 scripts/import_to_supabase.py --dry-run   # preflight only
    python3 scripts/import_to_supabase.py             # run the import

Requires psycopg2 and a .env file at the repo root with PROJECT_REF and
DB_PASSWORD set (matching the Supabase project from Step 19).
"""

import argparse
import json
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORDS_JSON = REPO_ROOT / "records.json"
ARTISTS_JSON = REPO_ROOT / "artists.json"
GENRES_JSON = REPO_ROOT / "genres.json"
ENV_FILE = REPO_ROOT / ".env"

TARGET_TABLES = ("artists", "genres", "records", "record_genres", "tracks")


def load_data():
    """Load and lightly shape-check the three canonical JSON files."""
    records = json.loads(RECORDS_JSON.read_text())
    artists = json.loads(ARTISTS_JSON.read_text())
    genres = json.loads(GENRES_JSON.read_text())

    if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
        sys.exit("records.json must be a list of objects")
    if not isinstance(artists, list) or not all(isinstance(a, str) for a in artists):
        sys.exit("artists.json must be a list of strings")
    if not isinstance(genres, list) or not all(isinstance(g, str) for g in genres):
        sys.exit("genres.json must be a list of strings")

    return records, artists, genres


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


def connect(env):
    """Open a direct Postgres connection to the Supabase project."""
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


def first_nonempty_table(conn):
    """Return the name of the first target table that has rows, or None."""
    with conn.cursor() as cur:
        for table in TARGET_TABLES:
            cur.execute(f"select count(*) from {table}")
            if cur.fetchone()[0] > 0:
                return table
    return None


def summarize(records, artists, genres):
    """Print the row counts we expect to insert into each table."""
    record_genres_edges = sum(len(r["genres"]) for r in records)
    tracks_total = sum(len(r.get("tracks", [])) for r in records)

    print(f"  artists:       {len(artists):>5}")
    print(f"  genres:        {len(genres):>5}")
    print(f"  records:       {len(records):>5}")
    print(f"  record_genres: {record_genres_edges:>5}")
    print(f"  tracks:        {tracks_total:>5}")


def import_all(conn, records, artists, genres):
    """Insert all rows in dependency order in a single transaction; commit at the end."""
    with conn.cursor() as cur:
        print(f"  Inserting artists ({len(artists)})...")
        execute_values(cur, "insert into artists (name) values %s", [(a,) for a in artists])

        print(f"  Inserting genres ({len(genres)})...")
        execute_values(cur, "insert into genres (name) values %s", [(g,) for g in genres])

        print(f"  Inserting records ({len(records)})...")
        record_rows = [
            (
                r["artist"],
                r["title"],
                r["year"][0],
                r["year"][1],
                r["rating"],
                r.get("notes"),
                r["discogs_url"],
                r["artwork"],
            )
            for r in records
        ]
        returned = execute_values(
            cur,
            "insert into records "
            "(artist, title, year_start, year_end, rating, notes, discogs_url, artwork) "
            "values %s returning id",
            record_rows,
            page_size=200,
            fetch=True,
        )
        record_ids = [row[0] for row in returned]

        rg_rows = [
            (record_id, genre)
            for record_id, r in zip(record_ids, records)
            for genre in r["genres"]
        ]
        print(f"  Inserting record_genres ({len(rg_rows)})...")
        execute_values(
            cur,
            "insert into record_genres (record_id, genre) values %s",
            rg_rows,
        )

        track_rows = []
        for record_id, r in zip(record_ids, records):
            position_by_side = {}
            for track in r.get("tracks", []):
                side = track["side"]
                position_by_side[side] = position_by_side.get(side, 0) + 1
                track_rows.append((record_id, side, position_by_side[side], track["title"]))
        print(f"  Inserting tracks ({len(track_rows)})...")
        if track_rows:
            execute_values(
                cur,
                "insert into tracks (record_id, side, position, title) values %s",
                track_rows,
                page_size=500,
            )

        print("  Committing transaction (deferred constraint triggers fire now)...")

    conn.commit()


def check_record_matches(conn, jr):
    """Read jr from the DB by its unique tuple and diff every field. Returns (ok, message)."""
    with conn.cursor() as cur:
        cur.execute(
            "select id, artist, title, year_start, year_end, rating, "
            "       notes, discogs_url, artwork "
            "from records "
            "where artist = %s and title = %s and year_start = %s and year_end = %s",
            (jr["artist"], jr["title"], jr["year"][0], jr["year"][1]),
        )
        row = cur.fetchone()
        if row is None:
            return False, "NOT FOUND in DB"
        record_id, artist, title, year_start, year_end, rating, notes, discogs_url, artwork = row

        mismatches = []
        if artist != jr["artist"]:
            mismatches.append("artist")
        if title != jr["title"]:
            mismatches.append("title")
        if year_start != jr["year"][0]:
            mismatches.append("year_start")
        if year_end != jr["year"][1]:
            mismatches.append("year_end")
        if rating != jr["rating"]:
            mismatches.append("rating")
        if (notes or "") != (jr.get("notes") or ""):
            mismatches.append("notes")
        if discogs_url != jr["discogs_url"]:
            mismatches.append("discogs_url")
        if artwork != jr["artwork"]:
            mismatches.append("artwork")

        cur.execute("select genre from record_genres where record_id = %s", (record_id,))
        db_genres = sorted(r[0] for r in cur.fetchall())
        json_genres = sorted(jr["genres"])
        if db_genres != json_genres:
            mismatches.append(f"genres ({db_genres} vs {json_genres})")

        cur.execute(
            "select side, position, title from tracks "
            "where record_id = %s order by side, position",
            (record_id,),
        )
        db_tracks = cur.fetchall()
        json_tracks_by_side = {}
        for t in jr.get("tracks", []):
            json_tracks_by_side.setdefault(t["side"], []).append(t["title"])
        expected_tracks = []
        for side in sorted(json_tracks_by_side.keys()):
            for pos, title in enumerate(json_tracks_by_side[side], 1):
                expected_tracks.append((side, pos, title))
        if db_tracks != expected_tracks:
            mismatches.append("tracks")

    if mismatches:
        return False, f"MISMATCH: {', '.join(mismatches)}"
    return True, f"OK ({len(jr['genres'])} genres, {len(jr.get('tracks', []))} tracks)"


def verify(conn, records, artists, genres):
    """Compare row counts and spot-check three records. Returns True if everything matches."""
    expected = {
        "artists":       len(artists),
        "genres":        len(genres),
        "records":       len(records),
        "record_genres": sum(len(r["genres"]) for r in records),
        "tracks":        sum(len(r.get("tracks", [])) for r in records),
    }

    actual = {}
    with conn.cursor() as cur:
        for table in TARGET_TABLES:
            cur.execute(f"select count(*) from {table}")
            actual[table] = cur.fetchone()[0]

    all_ok = True
    print("\nRow count verification:")
    for table in TARGET_TABLES:
        ok = actual[table] == expected[table]
        status = "OK" if ok else "MISMATCH"
        print(
            f"  {table:<14} expected={expected[table]:>5}  "
            f"actual={actual[table]:>5}  {status}"
        )
        if not ok:
            all_ok = False

    indices = [0, len(records) // 2, len(records) - 1]
    print("\nSpot-checking records:")
    for idx in indices:
        record = records[idx]
        ok, msg = check_record_matches(conn, record)
        label = f"{record['artist']} - {record['title']}"
        print(f"  [{idx}] {label}: {msg}")
        if not ok:
            all_ok = False

    return all_ok


def main():
    """Run the import: preflight, connect, safety guard, transactional insert."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load and summarize the JSON files, then exit without touching the database.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Proceed even if target tables already have rows. "
            "Manual TRUNCATE first if you want a clean redo."
        ),
    )
    args = parser.parse_args()

    records, artists, genres = load_data()

    print("Source JSON files loaded. Row counts to import:")
    summarize(records, artists, genres)

    if args.dry_run:
        print("\nDry run, exiting before any database work.")
        return

    env = load_env()
    print(f"\nConnecting to Supabase project {env.get('PROJECT_REF')}...")
    conn = connect(env)
    print("Connected.")

    occupied = first_nonempty_table(conn)
    if occupied and not args.force:
        conn.close()
        sys.exit(
            f"Refusing to import: table '{occupied}' already has rows. "
            f"Use --force to override, or TRUNCATE the target tables first."
        )

    print("\nStarting import:")
    try:
        import_all(conn, records, artists, genres)
    except psycopg2.Error as e:
        conn.rollback()
        conn.close()
        sys.exit(f"\nImport failed, rolled back: {e}")
    print("\nImport committed.")

    ok = verify(conn, records, artists, genres)
    conn.close()
    if not ok:
        sys.exit("\nVerification FAILED. The import committed but the data does not match the JSON source.")
    print("\nVerification passed.")


if __name__ == "__main__":
    main()
