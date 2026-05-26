# Collection backup

`collection.json` in this directory is a **generated backup** of the live Supabase
collection, not the source of truth. The database is the source of truth.

- It is written by [`scripts/export_backup.py`](../scripts/export_backup.py) and
  committed automatically by [`.github/workflows/backup.yml`](../.github/workflows/backup.yml),
  which runs daily and commits only when the collection has actually changed.
- Do not edit it by hand; the next run overwrites it.
- It exists for two reasons: an off-Supabase backup the free tier does not give
  you (Supabase's downloadable backups are paid), and a git-versioned audit log
  of the collection, which the move off static JSON otherwise gave up (see
  [ADR-004](../dev-docs/adrs/004-replace-static-json-with-deployed-database.md)).

To restore from this file, re-run the schema migrations in `supabase/migrations/`
on a fresh project, then insert the rows from `collection.json` (artists and
genres auto-create from record references via the canonical-list triggers, so
inserting records, their genres, and tracks is enough). Cover-art images live in
`../images/` and are versioned in git independently.
