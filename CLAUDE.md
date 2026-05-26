# CLAUDE.md, Record Collection Browser

This project is a record collection browser: a static frontend on GitHub Pages backed by a Supabase (Postgres) database. I (the owner) will use you most often as a data-entry assistant: adding, editing, or removing records. The collection lives in the database, not in the repo. See [ADR-004](dev-docs/adrs/004-replace-static-json-with-deployed-database.md).

When I ask you to make app changes rather than data changes, read [dev-docs/PRD.md](dev-docs/PRD.md), [dev-docs/ARCHITECTURE.md](dev-docs/ARCHITECTURE.md), and any ADRs in [dev-docs/adrs/](dev-docs/adrs/) first. Those docs are the source of truth for what to build and how. This file is scoped specifically to data work.

## UI testing

Any UI change must be verified with Playwright before being reported as complete. Always set the viewport to **390x844** (iPhone 14 size) before taking screenshots or checking layout -- this is a mobile-first site and desktop rendering is not a reliable signal for whether the UI is correct.

## Where the data lives

The collection is five Supabase tables (schema in [supabase/migrations/](supabase/migrations/)):

- `records`: one row per record. Columns: `id` (serial PK), `artist`, `title`, `year_start`, `year_end`, `rating`, `notes`, `discogs_url`, `artwork`.
- `artists`: canonical artist names (`name` PK).
- `genres`: canonical genre names (`name` PK).
- `record_genres`: junction rows linking a record to each of its genres (`record_id`, `genre`).
- `tracks`: one row per track (`record_id`, `side`, `position`, `title`).

The frontend reads these tables through the Supabase JS SDK ([data.js](data.js)). Reads are public; writes are owner-only, gated by row-level security on my Google account. There are no `records.json` / `artists.json` / `genres.json` files anymore; they were retired when the database became the source of truth.

## The canonical-list invariant (now enforced by the database)

The invariant from [ADR-001](dev-docs/adrs/001-canonical-artist-and-genre-lists.md) still holds: every record's `artist` must exist in `artists`, every genre in `record_genres` must exist in `genres`, and every `artists` / `genres` row must be referenced by at least one record. **You no longer maintain this by hand.** The database does it for you:

- Foreign keys reject any `artist` or `genre` value that is not canonical.
- Triggers auto-create a canonical `artists` / `genres` row the first time a record references a new name.
- Triggers auto-delete a canonical row once its last referencing record is gone.
- Deferred constraint triggers fail the transaction at commit if any record has no genre, or any canonical row is left unreferenced.

So when you add or remove a record through the proper tooling, the canonical lists stay correct automatically. Do not insert into or delete from `artists` / `genres` directly to "keep them in sync"; that is the trigger's job and a direct edit can trip the deferred checks.

## Record fields

| Field    | Type     | Required | Notes                                                |
|----------|----------|----------|------------------------------------------------------|
| artwork  | string   | yes      | Repo-relative path under `images/`, the file must exist and be committed |
| artist   | string   | yes      | Auto-added to `artists` if new                       |
| title    | string   | yes      | Album title                                          |
| year     | [int, int] | yes    | Stored as `year_start` / `year_end`. `[start, end]` range of the music, not the pressing year. Both 1900 to current year + 1, `start <= end`. Studio albums use `[y, y]`; compilations span earliest to latest source track. See [ADR-002](dev-docs/adrs/002-year-as-range.md). |
| rating   | integer  | yes      | 1 to 5 inclusive                                     |
| genres   | string[] | yes      | Non-empty; stored as `record_genres` rows; each genre auto-added to `genres` if new |
| notes    | string   | no       | Free text                                            |
| discogs_url | string | yes      | Discogs `/release/<id>` or `/sell/item/<id>` URL the record was added from. Captures source provenance for cover art and metadata. See [ADR-003](dev-docs/adrs/003-discogs-url-as-record-field.md). |
| tracks   | object[] | no       | `{ side, position, title }` rows; `position` is track order within a side. Sourced from Discogs. |

Do not invent fields like `format`, `label`, `pressing`. Those are explicitly out of scope for v1 (PRD §11).

**Year convention.** Record the year of the music, not the year the physical record was pressed or the compilation assembled. The goal is to capture when the music itself was made; the physical object doesn't matter here. The field is always a two-element `[start, end]` range, even for single-year records.

- **Studio albums:** use `[y, y]` where `y` is the master (original) release year. If my copy is a later reissue, keep the master year, not the reissue year.
- **Compilations (greatest hits, best-of records):** use `[earliest, latest]` spanning the master release years of the source recordings. Do not use the compilation's own release year. If the album cover prints a date range (e.g. "Their Greatest Hits 1971-1975"), trust it. If you can't determine the range from the tracklist, ask me.

## Adding records

Adding records is the `/add-records` skill, not a manual database edit. It drives `scripts/add_records.py` (`stage` then `apply`) from Discogs links, fetches metadata and cover art, checks for duplicates against the live database, and inserts the rows in one transaction. Invoke that skill when I ask to add records, and follow it. The only thing that lands in git is the new cover-art image under `images/`, which GitHub Pages serves; the row data is live in the database the moment `apply` succeeds.

If I describe a record in chat without going through the skill, point me at `/add-records` rather than hand-writing SQL inserts.

## Editing a record

Rating and notes are editable from the detail sheet in the app (the two fields I reach for while a record is on the turntable), synced through the SDK to the database. Every other field is editable too, but through Claude Code and the Supabase MCP rather than the UI. For those edits:

- An `UPDATE` to a column is safe and immediate. Changing `rating`, `notes`, `year_*`, `title`, `discogs_url`, or `artwork` is a single-row update.
- Changing `artist` or a record's genres flows through the triggers: a new value auto-creates its canonical row, and the old value's canonical row is auto-removed if it was the last reference. You do not touch `artists` / `genres` yourself.

## Removing a record

Delete the `records` row through the Supabase MCP. `record_genres` and `tracks` rows cascade automatically, and the orphan-cleanup triggers drop any `artists` / `genres` row that the deleted record was the last to use. After removing a record, delete its artwork file under `images/` (and commit that) unless I say otherwise.

## Commit messages

Conventional Commits format. Record additions/removals mostly touch only artwork in git, so use the `data` type for those image commits. Examples:

- `data: add Revolver by The Beatles`
- `data: add 7 jazz records`
- `data: remove Led Zeppelin II`
- `data: fix rating on Kind of Blue`

Never include Co-Authored-By trailers. The body is optional for data changes; include one only if the change needs explanation.

## How data is validated now

Validation lives in the database schema, not in CI. The Postgres constraints and triggers enforce: rating 1 to 5, `year_start <= year_end`, both years within range, non-empty title/artwork, a valid Discogs URL pattern, a unique `(artist, title, year_start, year_end)` tuple, every record having at least one genre, and the bidirectional canonical-list invariant. A failed insert or update raises a database error. If one fires, stop and report it verbatim; do not try to bypass a constraint. CI no longer runs a JSON validator (the `deploy` workflow only publishes the static site).

## Things not to do

- Do not add fields to records beyond the schema above.
- Do not insert into or delete from `artists` / `genres` directly. The canonical-list triggers own those tables.
- Do not hand-write SQL inserts to add records; use the `/add-records` skill.
- Do not commit artwork files that don't follow the spec (larger than 100 KB, not square 600x600, not JPEG) without asking.
- Do not edit `dev-docs/`, `tandem.json`, or the ADRs as part of a data-entry task. Those are gitignored / out of scope here. If I ask you to update project docs, that's a separate request and should go through the proper skills.
- Do not use em dashes in any written content (notes, commit messages, documentation). Use commas, periods, colons, or semicolons instead.
- Do not add Co-Authored-By trailers to commits.
- Do not bulk-rename or normalize existing data on your own initiative. If you notice inconsistencies, tell me and let me decide.

## When in doubt

Ask. A one-sentence clarification beats an edit that introduces "The Beatles" and "the beatles" as two different canonical entries, or a duplicate record the unique constraint will reject.
