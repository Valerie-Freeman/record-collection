#!/usr/bin/env python3
"""Validate records.json, artists.json, and genres.json per PRD section 9.1."""

import datetime
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_RECORD_FIELDS = ("artwork", "artist", "title", "year", "rating", "genres", "discogs_url")
ALLOWED_RECORD_FIELDS = REQUIRED_RECORD_FIELDS + ("notes", "tracks")
ALLOWED_TRACK_FIELDS = {"side", "title"}

DISCOGS_URL_RX = re.compile(r"^https?://(?:www\.)?discogs\.com/(?:[a-z]{2}/)?(?:release/\d+|sell/item/\d+)(?:\b|/|$)")


def load_json(path):
    if not path.exists():
        return None, f"{path.name}: file not found at {path}"
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as e:
        return None, f"{path.name}: not valid UTF-8 ({e})"
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, f"{path.name}: invalid JSON ({e.msg} at line {e.lineno}, column {e.colno})"


def is_int(value):
    # bool is a subclass of int in Python; exclude it explicitly.
    return isinstance(value, int) and not isinstance(value, bool)


def validate_string_list(data, filename, errors):
    if not isinstance(data, list):
        errors.append(f"{filename}: top-level value must be an array")
        return
    seen = set()
    for i, entry in enumerate(data):
        if not isinstance(entry, str):
            errors.append(f"{filename}: entry at index {i} is not a string")
            continue
        if entry == "":
            errors.append(f"{filename}: entry at index {i} is an empty string")
            continue
        if entry in seen:
            errors.append(f"{filename}: duplicate entry '{entry}'")
        seen.add(entry)


def validate_record(record, index, errors, current_year):
    position = index + 1
    if not isinstance(record, dict):
        errors.append(f"Record {position}: must be a JSON object")
        return

    raw_title = record.get("title")
    title_display = raw_title if isinstance(raw_title, str) and raw_title else "?"
    label = f'Record {position} ("{title_display}")'

    for field in REQUIRED_RECORD_FIELDS:
        if field not in record:
            errors.append(f"{label}: missing required field '{field}'")

    for field in record:
        if field not in ALLOWED_RECORD_FIELDS:
            errors.append(f"{label}: unknown field '{field}'")

    for field in ("artwork", "artist", "title"):
        if field in record:
            value = record[field]
            if not isinstance(value, str) or value == "":
                errors.append(f"{label}: '{field}' must be a non-empty string")

    if "year" in record:
        year = record["year"]
        if not isinstance(year, list) or len(year) != 2:
            errors.append(f"{label}: 'year' must be a [start, end] array of two integers")
        elif not all(is_int(y) for y in year):
            errors.append(f"{label}: 'year' entries must be integers")
        else:
            start, end = year
            if start < 1900 or start > current_year + 1:
                errors.append(
                    f"{label}: year[0] must be between 1900 and {current_year + 1}, got {start}"
                )
            if end < 1900 or end > current_year + 1:
                errors.append(
                    f"{label}: year[1] must be between 1900 and {current_year + 1}, got {end}"
                )
            if start > end:
                errors.append(
                    f"{label}: year start ({start}) must be <= year end ({end})"
                )

    if "rating" in record:
        rating = record["rating"]
        if not is_int(rating):
            errors.append(f"{label}: 'rating' must be an integer")
        elif not (1 <= rating <= 5):
            errors.append(f"{label}: 'rating' must be an integer 1..5, got {rating}")

    if "genres" in record:
        genres = record["genres"]
        if not isinstance(genres, list) or len(genres) == 0:
            errors.append(f"{label}: 'genres' must be a non-empty array of strings")
        else:
            for j, g in enumerate(genres):
                if not isinstance(g, str) or g == "":
                    errors.append(f"{label}: genres[{j}] must be a non-empty string")

    if "notes" in record and not isinstance(record["notes"], str):
        errors.append(f"{label}: 'notes' must be a string")

    if "discogs_url" in record:
        url = record["discogs_url"]
        if not isinstance(url, str) or url == "":
            errors.append(f"{label}: 'discogs_url' must be a non-empty string")
        elif not DISCOGS_URL_RX.match(url):
            errors.append(
                f"{label}: 'discogs_url' must be a Discogs /release/<id> or /sell/item/<id> URL, got '{url}'"
            )

    artwork = record.get("artwork")
    if isinstance(artwork, str) and artwork:
        if not (REPO_ROOT / artwork).is_file():
            errors.append(f"{label}: artwork file '{artwork}' does not exist")

    if "tracks" in record:
        tracks = record["tracks"]
        if not isinstance(tracks, list) or len(tracks) == 0:
            errors.append(f"{label}: 'tracks' must be a non-empty array when present")
        else:
            for j, track in enumerate(tracks):
                tlabel = f"{label}: tracks[{j}]"
                if not isinstance(track, dict):
                    errors.append(f"{tlabel}: must be an object")
                    continue
                extra = sorted(set(track.keys()) - ALLOWED_TRACK_FIELDS)
                if extra:
                    errors.append(f"{tlabel}: unexpected field(s) {extra}")
                for tf in ("side", "title"):
                    if tf not in track:
                        errors.append(f"{tlabel}: missing '{tf}'")
                    elif not isinstance(track[tf], str) or track[tf] == "":
                        errors.append(f"{tlabel}: '{tf}' must be a non-empty string")


def check_duplicates(records, errors):
    seen = {}
    for i, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        artist = record.get("artist")
        title = record.get("title")
        year = record.get("year")
        if not isinstance(artist, str) or not isinstance(title, str):
            continue
        if not isinstance(year, list) or len(year) != 2 or not all(is_int(y) for y in year):
            continue
        key = (artist, title, year[0], year[1])
        if key in seen:
            first = seen[key] + 1
            errors.append(
                f'Record {i + 1} ("{title}"): duplicate (artist, title, year) tuple; '
                f"first seen at Record {first}"
            )
        else:
            seen[key] = i


def check_cross_file_consistency(records, artists, genres, errors):
    artists_set = {a for a in artists if isinstance(a, str)}
    genres_set = {g for g in genres if isinstance(g, str)}
    used_artists = set()
    used_genres = set()

    for i, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        raw_title = record.get("title")
        title = raw_title if isinstance(raw_title, str) and raw_title else "?"

        artist = record.get("artist")
        if isinstance(artist, str) and artist:
            if artist not in artists_set:
                errors.append(
                    f'Record {i + 1} ("{title}"): unknown artist \'{artist}\'. '
                    f"Add it to artists.json or fix the spelling."
                )
            used_artists.add(artist)

        record_genres = record.get("genres")
        if isinstance(record_genres, list):
            for g in record_genres:
                if isinstance(g, str) and g:
                    if g not in genres_set:
                        errors.append(
                            f'Record {i + 1} ("{title}"): unknown genre \'{g}\'. '
                            f"Add it to genres.json or fix the spelling."
                        )
                    used_genres.add(g)

    for a in artists:
        if isinstance(a, str) and a and a not in used_artists:
            errors.append(
                f"Artist '{a}' is in artists.json but no record uses it. "
                f"Remove it from artists.json or add a record."
            )
    for g in genres:
        if isinstance(g, str) and g and g not in used_genres:
            errors.append(
                f"Genre '{g}' is in genres.json but no record uses it. "
                f"Remove it from genres.json or add a record."
            )


def print_errors(errors):
    print(f"Validation failed with {len(errors)} error(s):", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)


def main():
    errors = []

    records, err = load_json(REPO_ROOT / "records.json")
    if err:
        errors.append(err)
    artists, err = load_json(REPO_ROOT / "artists.json")
    if err:
        errors.append(err)
    genres, err = load_json(REPO_ROOT / "genres.json")
    if err:
        errors.append(err)

    if errors:
        print_errors(errors)
        return 1

    validate_string_list(artists, "artists.json", errors)
    validate_string_list(genres, "genres.json", errors)

    if not isinstance(records, list):
        errors.append("records.json: top-level value must be an array")
        print_errors(errors)
        return 1

    current_year = datetime.date.today().year
    for i, record in enumerate(records):
        validate_record(record, i, errors, current_year)

    check_duplicates(records, errors)

    if isinstance(artists, list) and isinstance(genres, list):
        check_cross_file_consistency(records, artists, genres, errors)

    if errors:
        print_errors(errors)
        return 1

    print(
        f"OK: {len(records)} records, {len(artists)} artists, {len(genres)} genres."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
