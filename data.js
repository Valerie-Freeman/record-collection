import { supabase } from "./supabase.js";

function slugify(str) {
  return String(str)
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function shapeRecord(row) {
  const [start, end] = [row.year_start, row.year_end];
  const yearPart = start === end ? `${start}` : `${start}-${end}`;
  const tracks = (row.tracks ?? [])
    .slice()
    .sort((a, b) =>
      a.side === b.side ? a.position - b.position : a.side < b.side ? -1 : 1
    )
    .map(({ side, title }) => ({ side, title }));
  const record = {
    db_id: row.id,
    artwork: row.artwork,
    artist: row.artist,
    title: row.title,
    year: [start, end],
    rating: row.rating,
    genres: (row.record_genres ?? []).map((g) => g.genre),
    discogs_url: row.discogs_url,
    id: slugify(`${row.artist} ${row.title} ${yearPart}`),
  };
  if (row.notes) record.notes = row.notes;
  if (tracks.length > 0) record.tracks = tracks;
  return record;
}

export async function updateRecord(dbId, updates) {
  const { data, error } = await supabase
    .from("records")
    .update(updates)
    .eq("id", dbId)
    .select()
    .single();
  if (error) {
    if (error.code === "PGRST116") {
      throw new Error("Update blocked. Sign in as the owner and try again.");
    }
    throw error;
  }
  return data;
}

export async function loadCollection() {
  const [recordsRes, artistsRes, genresRes] = await Promise.all([
    supabase
      .from("records")
      .select(
        "id, artist, title, year_start, year_end, rating, notes, discogs_url, artwork, record_genres(genre), tracks(side, position, title)"
      ),
    supabase.from("artists").select("name").order("name"),
    supabase.from("genres").select("name").order("name"),
  ]);

  for (const res of [recordsRes, artistsRes, genresRes]) {
    if (res.error) throw res.error;
  }

  return {
    records: recordsRes.data.map(shapeRecord),
    artists: artistsRes.data.map((a) => a.name),
    genres: genresRes.data.map((g) => g.name),
  };
}
