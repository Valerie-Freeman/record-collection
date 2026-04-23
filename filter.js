export function matchesSearch(record, normalizedQuery) {
  if (!normalizedQuery) return true;
  return (
    record.artist.toLowerCase().includes(normalizedQuery) ||
    record.title.toLowerCase().includes(normalizedQuery)
  );
}

export function applySearch(records, query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) return records;
  return records.filter((r) => matchesSearch(r, q));
}

export function recordDecades(record) {
  const [start, end] = record.year;
  const startDecade = Math.floor(start / 10) * 10;
  const endDecade = Math.floor(end / 10) * 10;
  const decades = [];
  for (let d = startDecade; d <= endDecade; d += 10) decades.push(d);
  return decades;
}

export function matchesFilters(record, filters) {
  if (filters.artists.size > 0 && !filters.artists.has(record.artist)) return false;
  if (filters.decades.size > 0) {
    const decades = recordDecades(record);
    if (!decades.some((d) => filters.decades.has(d))) return false;
  }
  if (filters.genres.size > 0 && !record.genres.some((g) => filters.genres.has(g))) return false;
  if (filters.ratings.size > 0 && !filters.ratings.has(record.rating)) return false;
  return true;
}

export function applyFilters(records, filters) {
  return records.filter((r) => matchesFilters(r, filters));
}

export function sortKey(record, field) {
  switch (field) {
    case "artist":
      return record.artist.replace(/^the\s+/i, "").toLowerCase();
    case "title":
      return record.title.toLowerCase();
    case "year":
      return record.year[0];
    case "rating":
      return record.rating;
    default:
      return record.artist.replace(/^the\s+/i, "").toLowerCase();
  }
}

export function sortRecords(records, sort) {
  const dir = sort.dir === "desc" ? -1 : 1;
  return records.slice().sort((a, b) => {
    const ka = sortKey(a, sort.field);
    const kb = sortKey(b, sort.field);
    if (ka < kb) return -1 * dir;
    if (ka > kb) return 1 * dir;
    return 0;
  });
}

export function visibleRecords(records, state) {
  const searched = applySearch(records, state.search);
  const filtered = applyFilters(searched, state.filters);
  return sortRecords(filtered, state.sort);
}
