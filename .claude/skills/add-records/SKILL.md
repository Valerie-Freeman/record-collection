---
name: add-records
description: Add one or more records to the collection from Discogs links. Use whenever the user wants to add records, mentions Discogs master/vinyl links for data entry, or asks to trigger the record-entry workflow.
---

# Add Records

Primary data-entry workflow for this project. Drives `scripts/add_records.py` with user-in-the-loop review.

## Step 1: Show the input template

When the skill is triggered without input data already present, respond with the template below, the rating rubric, and a short prompt. Wait for the user to paste back a filled version.

```
master:
vinyl:
rating:
notes:

master:
vinyl:
rating:
notes:
```

**Rating rubric:**

- 1 = Keeping it for some reason
- 2 = Alright
- 3 = Good
- 4 = Great
- 5 = Favorite

**Field rules to mention briefly:**

- `master` is the Discogs `/master/...` URL (year, genres, artwork). May be empty if the release has no master.
- `vinyl` is the Discogs `/release/...` or `/sell/item/...` URL (gives the correct side-A/side-B split). Required.
- `rating` is 1-5. Required.
- `notes` is the user's personal thoughts about the record. May be empty.
- One record per block; separate records with a blank line.

## Step 2: Stage

When the user pastes the filled template:

1. Write it to `.data-staging/input.txt` (create the directory if needed).
2. Run `python3 scripts/add_records.py stage .data-staging/input.txt`.
3. If it exits non-zero (duplicate record, parse error, Discogs API failure), stop and report the error verbatim. Do not try to bypass. Ask the user to clarify or correct.

The script will print a numbered summary per record: artist/title/year/rating, genres, notes, track count, and any FLAGs (new artist, new genre, duplicate track positions, year mismatches, etc.). Images are downloaded to `.data-staging/images/` and optimized; they are not moved into `images/` until `apply` runs.

## Step 3: Review with the user

For each record, surface to the user:

- The proposed year (a `[start, end]` range; see below), genres, and anything flagged.
- Any new artists being added to `artists.json` (spelling, leading "The", ampersand vs. "and").
- Any new genres being added to `genres.json`.
- Compilation records: `year` must span the source recordings' master release years, not the compilation's own release year. The staging script detects compilations via the Discogs format descriptor and flags them with `year: [y, y]` as a placeholder. Before applying, resolve the real `[earliest, latest]` range (look at the tracklist, use Discogs to date tracks if needed) and edit `.data-staging/staging.json`. See [ADR-002](../../../dev-docs/adrs/002-year-as-range.md) for the rationale.

`year` is always a two-element `[start, end]` integer array. Studio albums use `[y, y]`; compilations use `[earliest, latest]` spanning the source recordings. Ask the user if a compilation's range is ambiguous.

Ask for confirmation or corrections. Apply corrections by editing `.data-staging/staging.json` directly (it is a plain JSON file). If the user wants to change a URL or rating, edit `.data-staging/input.txt` and rerun `stage`.

## Step 4: Apply

Once the user confirms, run `python3 scripts/add_records.py apply`. This:

- Moves staged images into `images/`.
- Appends the records to `records.json` (preserving the project's custom formatting).
- Updates `artists.json` and `genres.json` with any new entries (sorted, ignoring "The").
- Runs `scripts/validate_records.py` and exits with its status.

If the validator fails, stop and report. Do not try to bypass.

## Step 5: Browser check

Ask the user to open the app and confirm the new records look right. Do not skip this.

## Step 6: Commit

**Always ask before committing.** When the user confirms, craft a commit message in conventional-commit form:

- Single record: `data: add <title> by <artist>`
- Small batch: `data: add <N> records (<artist1>, <artist2>, ...)`
- Genre/artist-only: match the specific change (e.g. `data: add genre "Easy Listening"`)

Never include `Co-Authored-By` trailers. Stage all changed files in one commit (records.json, artists.json, genres.json, and any new images).

## Step 7: Push

**Always ask before pushing.** Do not push automatically.

## Clean-up

If the user abandons a batch, the staging dir can be deleted safely: `rm -rf .data-staging`. It is gitignored.
