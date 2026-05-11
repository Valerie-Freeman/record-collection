-- Owner-write RLS policies for Step 22.
-- Reads remain public via the policies in 20260504194028_rls_public_read.sql.
-- Writes are gated to the owner emails read from the auth JWT.
-- Two owners are managed inline; flip to a table if the list ever grows.
--
-- All five tables get a single `for all` policy. For SELECT this OR's with the
-- existing public_read policy and simplifies to "everyone can read" (no change).
-- The canonical-list triggers in 20260504194023 insert into / delete from the
-- `artists` and `genres` tables on the invoker's behalf, so owners need write
-- access to those tables too, not just to `records`.

create or replace function is_owner()
returns boolean
language sql
stable
as $$
  select coalesce(auth.jwt() ->> 'email', '') in (
    'valerah7@gmail.com',
    'caylonfreeman@gmail.com'
  );
$$;

create policy owner_write on artists       for all to authenticated using (is_owner()) with check (is_owner());
create policy owner_write on genres        for all to authenticated using (is_owner()) with check (is_owner());
create policy owner_write on records       for all to authenticated using (is_owner()) with check (is_owner());
create policy owner_write on record_genres for all to authenticated using (is_owner()) with check (is_owner());
create policy owner_write on tracks        for all to authenticated using (is_owner()) with check (is_owner());
