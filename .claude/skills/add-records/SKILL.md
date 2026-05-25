---
name: add-records
description: Add one or more records to the collection from Discogs links. Use whenever the user wants to add records, mentions Discogs master/vinyl links for data entry, or asks to trigger the record-entry workflow.
---

# Add Records

Primary data-entry workflow for this project. Drives `scripts/add_records.py` with user-in-the-loop review.

The collection lives in Supabase (see [ADR-004](../../../dev-docs/adrs/004-replace-static-json-with-deployed-database.md)). `stage` reads the existing collection from the database to detect duplicates and flag new artists/genres; `apply` inserts the new rows into the database. Cover art is the exception: it still lives in the repo under `images/` and is served by GitHub Pages, so a new record's image needs a git commit and push (the row data itself does not). Both subcommands need `psycopg2` and a `.env` at the repo root with `PROJECT_REF` and `DB_PASSWORD`.

## Setup (do this before Step 2)

`psycopg2` is not in the system `python3`; it lives in a gitignored project virtualenv at `.venv/`. Run every `add_records.py` command in this skill as `.venv/bin/python scripts/add_records.py ...`, not `python3 ...`.

If `.venv/` does not exist yet (fresh clone), create it once:

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

`.env` (with `PROJECT_REF` and `DB_PASSWORD`) must also be present at the repo root; it is gitignored and not recreated automatically.

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
2. Run `.venv/bin/python scripts/add_records.py stage .data-staging/input.txt`.
3. If it exits non-zero (duplicate record, parse error, Discogs API failure), stop and report the error verbatim. Do not try to bypass. Ask the user to clarify or correct.

The script will print a numbered summary per record: artist/title/year/rating, genres, notes, track count, and any FLAGs (new artist, new genre, duplicate track positions, year mismatches, etc.). Images are downloaded to `.data-staging/images/` and optimized; they are not moved into `images/` until `apply` runs.

## Step 3: Review with the user

For each record, surface to the user:

- The proposed year (a `[start, end]` range; see below), genres (see **Genre rules** below), and anything flagged.
- Any new artists being added to the collection (spelling, leading "The", ampersand vs. "and"). `apply` creates the canonical artist row automatically, so this review is the only guard against a typo'd variant.
- Any new genres being added to the collection.
- Compilation records: `year` must span the source recordings' master release years, not the compilation's own release year. The staging script detects compilations via the Discogs format descriptor and flags them with `year: [y, y]` as a placeholder. Before applying, resolve the real `[earliest, latest]` range (look at the tracklist, use Discogs to date tracks if needed) and edit `.data-staging/staging.json`. See [ADR-002](../../../dev-docs/adrs/002-year-as-range.md) for the rationale.

`year` is always a two-element `[start, end]` integer array. Studio albums use `[y, y]`; compilations use `[earliest, latest]` spanning the source recordings. Ask the user if a compilation's range is ambiguous.

Ask for confirmation or corrections. Apply corrections by editing `.data-staging/staging.json` directly (it is a plain JSON file). If the user wants to change a URL or rating, edit `.data-staging/input.txt` and rerun `stage`.

### Genre rules

The staging script emits every Discogs `genre` and `style` concatenated and deduped. Your job during review is to trim that raw list to a consistent, simple set.

**Hard rules:**

- **Max 3 genres per record.** If the proposal has more, trim.
- **Prioritize using genres already in the collection.** The `genres` table is the canonical vocabulary, and the `stage` summary flags any proposed genre not already in it. Try to match to an existing genre. If a record genuinely needs a new one, flag it to the user for confirmation; `apply` creates the canonical row automatically on insert, so this review is the only safeguard against silently introducing a stray genre.
- **Prefer short forms** when both exist: `Prog Rock` (not "Progressive Rock"), `Rock & Roll` (not "Rock and Roll"), `Neo-Soul` (not "Neo Soul").

**Map common Discogs terms to their canonical equivalent:**

| Discogs term             | Use canonical                                                                               |
| ------------------------ | ------------------------------------------------------------------------------------------- |
| Classic Rock             | Rock                                                                                        |
| Electric Blues           | Blues                                                                                       |
| Arena Rock               | Hard Rock                                                                                   |
| AOR                      | Soft Rock                                                                                   |
| Rock & Roll (as a style) | Rock & Roll                                                                                 |
| Symphonic Rock           | Prog Rock                                                                                   |
| Contemporary R&B         | R&B                                                                                         |
| Neo Soul                 | Neo-Soul                                                                                    |
| Stage & Screen           | Soundtrack                                                                                  |
| Musical                  | Soundtrack                                                                                  |
| Folk, World, & Country   | Folk (or Folk Rock / Country Rock / Americana, depending on which style Discogs also lists) |

**Drop these Discogs terms** (no canonical equivalent and no good fallback): `Electronic`, `Hip Hop`, `Vocal`, `Theme`, `Bossa Nova`, `Psychedelic Rock`, `Synth-pop`, `Funk / Soul` (pick `Funk` or `Soul` or both based on what the styles suggest).

**Redundancy rule.** When both a broad and a narrow genre apply, drop the broad one:

- `Jazz` is redundant when `Vocal Jazz`, `Smooth Jazz`, `Big Band`, or `Swing` is already present.
- `Rock` can usually be dropped when a specific rock sub-genre (`Prog Rock`, `Art Rock`, `Southern Rock`, `Hard Rock`, etc.) captures the record. Keep `Rock` only if there is room and the album actually straddles the sub-genre and mainstream rock.
- `Soul` and `R&B` are near-synonyms; use one, not both, unless the record genuinely bridges both scenes.
- `Pop` and `Pop Rock` together is usually redundant; prefer `Pop Rock` for rock-adjacent records, `Pop` for non-rock pop.

**Consistency within an artist.** If the collection already has other records by this artist, check their genres and align unless there is a real stylistic difference. Atlanta Rhythm Section records all carry `Southern Rock`; Erykah Badu records all carry `Neo-Soul, R&B`. Drift is how a collection becomes inconsistent.

**When presenting to the user**, show: proposed genres (your trimmed set), Discogs raw `genres + styles` (so they can second-guess you), any mapping you applied, and any new canonical entries that need approval.

The genre audit script at `scripts/_genre_audit.py` is available if a broader consistency check is ever needed again.

## Step 4: Apply

Optionally dry-run first: `.venv/bin/python scripts/add_records.py apply --dry-run` runs the inserts and forces the deferred constraint checks against the live schema, then rolls back without persisting or moving any images. Use it to catch a constraint problem before it lands.

Once the user confirms, run `.venv/bin/python scripts/add_records.py apply`. This:

- Moves the staged images into `images/` (cover art stays in the repo, served by GitHub Pages).
- Inserts the records, their genre edges, and tracks into the Supabase database in one transaction. New artists and genres are created automatically by the canonical-list triggers.
- Reports the inserted records.

The row data is live in the database the moment `apply` succeeds; no push is needed for it to appear. There is no validator step anymore: the database constraints are the validation. If the insert fails (duplicate tuple, constraint violation, connection error), stop and report the error verbatim. Do not try to bypass.

## Step 5: Commit and push the cover art

The record data is already live. The only thing left in git is the new image file(s) under `images/`, which GitHub Pages needs in order to serve the cover art.

**Always ask before committing and before pushing.**

- Stage only the new image(s): `git add images/<file>.jpg`. Do not stage `records.json`, `artists.json`, or `genres.json`; those are a frozen snapshot now and this workflow no longer updates them.
- Commit message, conventional-commit form:
  - Single record: `data: add <title> by <artist>`
  - Small batch: `data: add <N> records (<artist1>, <artist2>, ...)`
- Never include `Co-Authored-By` trailers.
- Push so GitHub Pages deploys the art.

## Step 6: Browser check

Ask the user to open the app and confirm the new records look right, cover art included. Note: a new record's data shows immediately, but its image renders as a title fallback tile until the image push has deployed; once Pages updates, the art appears. Do not skip this.

## Clean-up

If the user abandons a batch, the staging dir can be deleted safely: `rm -rf .data-staging`. It is gitignored.
