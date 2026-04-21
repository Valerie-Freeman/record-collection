const RECORD_REQUIRED_FIELDS = ["artwork", "artist", "title", "year", "rating", "genres"];

function slugify(str) {
  return String(str)
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function checkRecords(data) {
  if (!Array.isArray(data)) throw new Error("records.json is not an array");
  data.forEach((r, i) => {
    if (!r || typeof r !== "object") throw new Error(`records[${i}] is not an object`);
    for (const f of RECORD_REQUIRED_FIELDS) {
      if (!(f in r)) throw new Error(`records[${i}] missing field "${f}"`);
    }
    if (typeof r.artwork !== "string" || !r.artwork) throw new Error(`records[${i}].artwork must be a non-empty string`);
    if (typeof r.artist !== "string" || !r.artist) throw new Error(`records[${i}].artist must be a non-empty string`);
    if (typeof r.title !== "string" || !r.title) throw new Error(`records[${i}].title must be a non-empty string`);
    if (!Number.isInteger(r.year)) throw new Error(`records[${i}].year must be an integer`);
    if (!Number.isInteger(r.rating) || r.rating < 1 || r.rating > 5) {
      throw new Error(`records[${i}].rating must be an integer 1..5`);
    }
    if (!Array.isArray(r.genres) || r.genres.length === 0) {
      throw new Error(`records[${i}].genres must be a non-empty array`);
    }
    if (!r.genres.every((g) => typeof g === "string" && g.length > 0)) {
      throw new Error(`records[${i}].genres must contain non-empty strings`);
    }
    if ("notes" in r && typeof r.notes !== "string") {
      throw new Error(`records[${i}].notes must be a string`);
    }
  });
}

function checkStringList(data, name) {
  if (!Array.isArray(data)) throw new Error(`${name} is not an array`);
  const seen = new Set();
  data.forEach((v, i) => {
    if (typeof v !== "string" || v.length === 0) throw new Error(`${name}[${i}] must be a non-empty string`);
    if (seen.has(v)) throw new Error(`${name} has duplicate entry "${v}"`);
    seen.add(v);
  });
}

async function fetchJson(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`fetch ${path} failed: ${res.status} ${res.statusText}`);
  return res.json();
}

export async function loadCollection() {
  const [records, artists, genres] = await Promise.all([
    fetchJson("records.json"),
    fetchJson("artists.json"),
    fetchJson("genres.json"),
  ]);

  checkRecords(records);
  checkStringList(artists, "artists.json");
  checkStringList(genres, "genres.json");

  const withIds = records.map((r) => ({
    ...r,
    id: slugify(`${r.artist} ${r.title} ${r.year}`),
  }));

  return { records: withIds, artists, genres };
}
