-- Bidirectional canonical-list invariant (ADR-001).
-- Direction 1 (every reference is canonical) is enforced by the FKs in 20260504120000.
-- Direction 2 (every canonical row is referenced) is enforced here.

-- Auto-create canonical artist when records inserts/updates reference one.
create or replace function ensure_artist_canonical()
returns trigger as $$
begin
  insert into artists(name) values (new.artist)
  on conflict (name) do nothing;
  return new;
end;
$$ language plpgsql;

create trigger ensure_artist_canonical_on_records
  before insert or update of artist on records
  for each row
  execute function ensure_artist_canonical();

-- Auto-create canonical genre when record_genres inserts/updates reference one.
create or replace function ensure_genre_canonical()
returns trigger as $$
begin
  insert into genres(name) values (new.genre)
  on conflict (name) do nothing;
  return new;
end;
$$ language plpgsql;

create trigger ensure_genre_canonical_on_record_genres
  before insert or update of genre on record_genres
  for each row
  execute function ensure_genre_canonical();

-- Clean up orphan artist after a record is deleted or its artist is changed.
create or replace function cleanup_orphan_artist()
returns trigger as $$
begin
  if tg_op = 'UPDATE' and old.artist = new.artist then
    return null;
  end if;
  delete from artists
   where name = old.artist
     and not exists (select 1 from records where artist = old.artist);
  return null;
end;
$$ language plpgsql;

create trigger cleanup_orphan_artist_after_records
  after delete or update of artist on records
  for each row
  execute function cleanup_orphan_artist();

-- Clean up orphan genre after a record_genres row is deleted or changed.
create or replace function cleanup_orphan_genre()
returns trigger as $$
begin
  if tg_op = 'UPDATE' and old.genre = new.genre then
    return null;
  end if;
  delete from genres
   where name = old.genre
     and not exists (select 1 from record_genres where genre = old.genre);
  return null;
end;
$$ language plpgsql;

create trigger cleanup_orphan_genre_after_record_genres
  after delete or update of genre on record_genres
  for each row
  execute function cleanup_orphan_genre();

-- Belt-and-suspenders: deferred constraint triggers fail the transaction if
-- any artists or genres row is unreferenced at COMMIT. Catches direct INSERTs
-- to the canonical tables that bypass the auto-create flow above.
-- The "skip if the canonical row was deleted in this txn" guard handles the
-- edge case where a record is inserted and deleted in the same transaction:
-- the auto-cleanup removes the canonical row, and we don't want this check to
-- raise on a row that no longer exists.

create or replace function ensure_artist_referenced()
returns trigger as $$
begin
  if not exists (select 1 from artists where name = new.name) then
    return null;
  end if;
  if not exists (select 1 from records where artist = new.name) then
    raise exception 'artist % has no referencing record (canonical-list invariant)', new.name
      using errcode = 'check_violation';
  end if;
  return null;
end;
$$ language plpgsql;

create constraint trigger artists_must_be_referenced
  after insert or update on artists
  deferrable initially deferred
  for each row
  execute function ensure_artist_referenced();

create or replace function ensure_genre_referenced()
returns trigger as $$
begin
  if not exists (select 1 from genres where name = new.name) then
    return null;
  end if;
  if not exists (select 1 from record_genres where genre = new.name) then
    raise exception 'genre % has no referencing record_genres (canonical-list invariant)', new.name
      using errcode = 'check_violation';
  end if;
  return null;
end;
$$ language plpgsql;

create constraint trigger genres_must_be_referenced
  after insert or update on genres
  deferrable initially deferred
  for each row
  execute function ensure_genre_referenced();
