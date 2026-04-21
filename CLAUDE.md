# CLAUDE.md, Record Collection Browser

This project is a static, no-backend record collection browser. I (the owner) will use you most often as a data-entry assistant: adding, editing, or removing records, and keeping the canonical artist and genre lists in sync.

When I ask you to make app changes rather than data changes, read [dev-docs/PRD.md](dev-docs/PRD.md), [dev-docs/ARCHITECTURE.md](dev-docs/ARCHITECTURE.md), and any ADRs in [dev-docs/adrs/](dev-docs/adrs/) first. Those docs are the source of truth for what to build and how. This file is scoped specifically to data work.

## The canonical-list invariant (read this first)

Three data files live at the repo root and move together:

- `records.json`: array of record objects (see schema below).
- `artists.json`: array of canonical artist name strings.
- `genres.json`: array of canonical genre name strings.

Every record's `artist` value must exist in `artists.json` exactly. Every string in a record's `genres` array must exist in `genres.json` exactly. Every entry in `artists.json` and `genres.json` must be used by at least one record. CI enforces all four directions. See [ADR-001](dev-docs/adrs/001-canonical-artist-and-genre-lists.md).

**Practical rule:** when you touch `records.json`, also touch the canonical lists if and only if the change introduces a new artist or genre, or removes the last use of one. In the same commit.

## Record schema

```json
{
  "artwork": "images/the-band.jpg",
  "artist": "The Band",
  "title": "The Band",
  "year": 1969,
  "rating": 5,
  "genres": ["Rock", "Americana"],
  "notes": "Brown album. Winchester pressing."
}
```

| Field    | Type     | Required | Notes                                                |
|----------|----------|----------|------------------------------------------------------|
| artwork  | string   | yes      | Repo-relative path under `images/`, must exist       |
| artist   | string   | yes      | Must match an `artists.json` entry exactly           |
| title    | string   | yes      | Album title                                          |
| year     | integer  | yes      | Original release year, not pressing year; 1900 to current year + 1 |
| rating   | integer  | yes      | 1 to 5 inclusive                                     |
| genres   | string[] | yes      | Non-empty; each must match a `genres.json` entry     |
| notes    | string   | no       | Free text                                            |

No other fields. Do not invent fields like `format`, `label`, `pressing`. Those are explicitly out of scope for v1 (PRD §11).

**Year convention.** Use the album's original release year, not the pressing year on the jacket in hand. For compilations (greatest hits, best-of records), use the compilation's own release year. If the compilation is undated or its tracks span a long period, ask the owner; they may prefer the average year of the source recordings over the comp release year.

## Adding a record

When I say something like "add Revolver by The Beatles, 1966, 5 stars, Rock and Psychedelic":

1. **Check for duplicates.** The `(artist, title, year)` tuple must be unique across the whole collection. If a record with the same tuple already exists, stop and ask me what I want to do.
2. **Confirm artwork.** Look for an image I've dropped under `images/`. If you cannot find one, ask me to add it before you edit `records.json`. Do not commit a record pointing at a nonexistent file. Naming convention: `images/<slugified-artist>-<slugified-title>.jpg` (lowercase, non-alphanumeric to `-`, collapse repeats). Spec: 600×600 JPEG, under 100 KB (see PRD §6.1.1).
3. **Canonical lists.** For the artist and each genre, check if it's already in `artists.json` / `genres.json` exactly. If not, append the new entry. Case-sensitive match. Preserve the user's exact form including a leading "The " where applicable.
4. **Append the record** to `records.json`. Order does not matter; appending is fine.
5. **Stage and commit** everything in a single commit (see commit message section below).

Ask clarifying questions before editing files if anything is ambiguous (spelling of the artist, whether a near-match already exists, which genres apply). Better to ask than to create a typo variant.

## Removing a record

When I say "remove [album]":

1. **Find and delete** the record from `records.json`.
2. **Check for orphans.** After removal, scan the remaining records. If the artist is no longer used by any record, remove it from `artists.json`. For each genre the removed record had, if that genre is no longer used by any record, remove it from `genres.json`. The CI validator will fail if you forget this.
3. **Delete the artwork file** under `images/` unless I've said otherwise.
4. **Commit** the whole change in one commit.

## Renaming an artist or genre

Typo fixes and canonical-form changes (e.g. "Rock & Roll" to "Rock and Roll") must update every occurrence:

1. Update the entry in `artists.json` or `genres.json`.
2. Update every matching `artist` field or `genres[]` entry in `records.json`.
3. Commit as a single change.

## Editing an existing record

Small edits (rating change, notes update, year correction) are safe. If the edit changes `artist` or a `genres[]` value, treat it as a rename or potentially as introducing/retiring a canonical entry. Apply the same invariant reasoning as above.

## Commit messages

Conventional Commits format. For data changes, use the `data` type. Examples:

- `data: add Revolver by The Beatles`
- `data: add 7 jazz records`
- `data: remove Led Zeppelin II`
- `data: rename genre "Rock & Roll" to "Rock and Roll"`
- `data: fix rating on Kind of Blue`

Never include Co-Authored-By trailers. The body is optional for data changes; include one only if the change needs explanation.

## What CI will catch (so you can catch it first)

`scripts/validate_records.py` runs on every push. It will fail the build if:

- `records.json` is malformed, missing fields, has out-of-range rating or year, has an empty `genres` array, or points to a nonexistent artwork file.
- Two records share an `(artist, title, year)` tuple.
- A record's `artist` or `genres[]` value is not in the corresponding canonical list.
- A canonical list has duplicates or empty strings.
- A canonical list contains an entry unused by any record.

If you find yourself wanting to suppress or work around a validator error, stop and ask me. The validator is the main line of defense and should not be bypassed.

## Things not to do

- Do not add fields to records beyond the schema above.
- Do not commit artwork files that don't follow the spec (larger than 100 KB, not square, not JPEG) without asking.
- Do not edit `dev-docs/`, `tandem.json`, or the ADRs as part of a data-entry task. Those are gitignored / out of scope here. If I ask you to update project docs, that's a separate request and should go through the proper skills.
- Do not use em dashes in any written content (JSON notes, commit messages, documentation). Use commas, periods, colons, or semicolons instead.
- Do not add Co-Authored-By trailers to commits.
- Do not bulk-rename or normalize existing data on your own initiative. If you notice inconsistencies, tell me and let me decide.

## When in doubt

Ask. A one-sentence clarification beats a commit that introduces "The Beatles" and "the beatles" as two different canonical entries.
