-- Initial schema for the Record Collection migration to Supabase.
-- Maps records.json, artists.json, and genres.json to relational tables.
-- Per-record column constraints port the rules from scripts/validate_records.py.
-- The bidirectional canonical-list invariant (ADR-001) is enforced by the
-- triggers in 20260504194023_canonical_list_invariant.sql.
-- RLS public-read policies live in 20260504194028_rls_public_read.sql.

create table artists (
  name text primary key,
  constraint artists_name_nonempty check (length(name) > 0)
);

create table genres (
  name text primary key,
  constraint genres_name_nonempty check (length(name) > 0)
);

create table records (
  id          serial primary key,
  artist      text    not null references artists(name) on update cascade,
  title       text    not null,
  year_start  integer not null,
  year_end    integer not null,
  rating      integer not null,
  notes       text,
  discogs_url text    not null,
  artwork     text    not null,
  constraint records_title_nonempty       check (length(title) > 0),
  constraint records_artwork_nonempty     check (length(artwork) > 0),
  constraint records_rating_range         check (rating between 1 and 5),
  -- Year upper bound is a static sanity guard (9999); the validator's tighter
  -- "<= current_year + 1" rule is enforced by the frontend at form time, since
  -- Postgres CHECK can't reference non-IMMUTABLE functions like current_date
  -- without breaking dump/restore round-trips.
  constraint records_year_start_range     check (year_start between 1900 and 9999),
  constraint records_year_end_range       check (year_end   between 1900 and 9999),
  constraint records_year_order           check (year_start <= year_end),
  constraint records_discogs_url_pattern  check (
    discogs_url ~ '^https?://(www\.)?discogs\.com/([a-z]{2}/)?(release|sell/item)/[0-9]+'
  ),
  constraint records_unique_tuple unique (artist, title, year_start, year_end)
);

create table record_genres (
  record_id integer not null references records(id) on delete cascade,
  genre     text    not null references genres(name) on update cascade,
  primary key (record_id, genre)
);

create table tracks (
  record_id integer not null references records(id) on delete cascade,
  side      text    not null,
  position  integer not null,
  title     text    not null,
  constraint tracks_side_nonempty     check (length(side) > 0),
  constraint tracks_title_nonempty    check (length(title) > 0),
  constraint tracks_position_positive check (position > 0),
  primary key (record_id, side, position)
);
