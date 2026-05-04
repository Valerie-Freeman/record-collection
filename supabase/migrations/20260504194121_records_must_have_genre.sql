-- Records must have at least one genre.
-- The validator enforces this on records.json's genres array; in the junction
-- model, it's a transaction-end check across records and record_genres.

create or replace function ensure_record_has_genre()
returns trigger as $$
begin
  if not exists (select 1 from records where id = new.id) then
    return null;
  end if;
  if not exists (select 1 from record_genres where record_id = new.id) then
    raise exception 'record % must have at least one genre', new.id
      using errcode = 'check_violation';
  end if;
  return null;
end;
$$ language plpgsql;

create constraint trigger records_must_have_genre
  after insert or update on records
  deferrable initially deferred
  for each row
  execute function ensure_record_has_genre();

-- Mirror check fires when the last record_genres row for a record is deleted.
create or replace function ensure_record_has_genre_after_unlink()
returns trigger as $$
begin
  -- If the record itself is gone (cascade), nothing to check.
  if not exists (select 1 from records where id = old.record_id) then
    return null;
  end if;
  if not exists (select 1 from record_genres where record_id = old.record_id) then
    raise exception 'record % must have at least one genre', old.record_id
      using errcode = 'check_violation';
  end if;
  return null;
end;
$$ language plpgsql;

create constraint trigger records_must_have_genre_on_unlink
  after delete on record_genres
  deferrable initially deferred
  for each row
  execute function ensure_record_has_genre_after_unlink();
