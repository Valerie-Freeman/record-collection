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

- The proposed year (a `[start, end]` range; see below), genres (see **Genre rules** below), and anything flagged.
- Any new artists being added to `artists.json` (spelling, leading "The", ampersand vs. "and").
- Any new genres being added to `genres.json`.
- Compilation records: `year` must span the source recordings' master release years, not the compilation's own release year. The staging script detects compilations via the Discogs format descriptor and flags them with `year: [y, y]` as a placeholder. Before applying, resolve the real `[earliest, latest]` range (look at the tracklist, use Discogs to date tracks if needed) and edit `.data-staging/staging.json`. See [ADR-002](../../../dev-docs/adrs/002-year-as-range.md) for the rationale.

`year` is always a two-element `[start, end]` integer array. Studio albums use `[y, y]`; compilations use `[earliest, latest]` spanning the source recordings. Ask the user if a compilation's range is ambiguous.

Ask for confirmation or corrections. Apply corrections by editing `.data-staging/staging.json` directly (it is a plain JSON file). If the user wants to change a URL or rating, edit `.data-staging/input.txt` and rerun `stage`.

### Genre rules

The staging script emits every Discogs `genre` and `style` concatenated and deduped. Your job during review is to trim that raw list to a consistent, simple set.

**Hard rules:**

- **Max 3 genres per record.** If the proposal has more, trim.
- **Only use entries already in `genres.json`.** That file is the canonical vocabulary. If a record genuinely needs a genre that does not exist there, flag it to the user and add it to `genres.json` in the same commit; do not silently introduce a new canonical entry.
- **Prefer short forms** when both exist: `Prog Rock` (not "Progressive Rock"), `Rock & Roll` (not "Rock and Roll"), `Neo-Soul` (not "Neo Soul").

**Map common Discogs terms to their canonical equivalent:**

| Discogs term | Use canonical |
|---|---|
| Classic Rock | Rock |
| Electric Blues | Blues |
| Arena Rock | Hard Rock |
| AOR | Soft Rock |
| Rock & Roll (as a style) | Rock & Roll |
| Symphonic Rock | Prog Rock |
| Contemporary R&B | R&B |
| Neo Soul | Neo-Soul |
| Stage & Screen | Soundtrack |
| Musical | Soundtrack |
| Folk, World, & Country | Folk (or Folk Rock / Country Rock / Americana, depending on which style Discogs also lists) |

**Drop these Discogs terms** (no canonical equivalent and no good fallback): `Electronic`, `Hip Hop`, `Vocal`, `Theme`, `Bossa Nova`, `Psychedelic Rock`, `Synth-pop`, `Funk / Soul` (pick `Funk` or `Soul` based on what the styles suggest).

**Redundancy rule.** When both a broad and a narrow genre apply, drop the broad one:

- `Jazz` is redundant when `Vocal Jazz`, `Smooth Jazz`, `Big Band`, or `Swing` is already present.
- `Rock` can usually be dropped when a specific rock sub-genre (`Prog Rock`, `Art Rock`, `Southern Rock`, `Hard Rock`, etc.) captures the record. Keep `Rock` only if there is room and the album actually straddles the sub-genre and mainstream rock.
- `Soul` and `R&B` are near-synonyms; use one, not both, unless the record genuinely bridges both scenes.
- `Pop` and `Pop Rock` together is usually redundant; prefer `Pop Rock` for rock-adjacent records, `Pop` for non-rock pop.

**Consistency within an artist.** If the collection already has other records by this artist, check their genres and align unless there is a real stylistic difference. Atlanta Rhythm Section records all carry `Southern Rock`; Erykah Badu records all carry `Neo-Soul, R&B`. Drift is how a collection becomes inconsistent.

**When presenting to the user**, show: proposed genres (your trimmed set), Discogs raw `genres + styles` (so they can second-guess you), any mapping you applied, and any new canonical entries that need approval.

The genre audit script at `scripts/_genre_audit.py` is available if a broader consistency check is ever needed again.

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
