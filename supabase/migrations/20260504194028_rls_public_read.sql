-- Enable RLS on every table and grant public read.
-- Owner-only write policies arrive in Step 22 once Google auth is wired up.
-- Until then, no policies cover INSERT/UPDATE/DELETE, so the anon and
-- authenticated roles cannot mutate the schema's data; only the service role
-- (used by migrations and the MCP server) can.

alter table artists       enable row level security;
alter table genres        enable row level security;
alter table records       enable row level security;
alter table record_genres enable row level security;
alter table tracks        enable row level security;

create policy public_read on artists       for select to anon, authenticated using (true);
create policy public_read on genres        for select to anon, authenticated using (true);
create policy public_read on records       for select to anon, authenticated using (true);
create policy public_read on record_genres for select to anon, authenticated using (true);
create policy public_read on tracks        for select to anon, authenticated using (true);
