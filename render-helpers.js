const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);
}

export function stars(rating) {
  return "★".repeat(rating) + "☆".repeat(5 - rating);
}

export function artistSortKey(name) {
  return name.replace(/^the\s+/i, "").toLowerCase();
}

export function sortedArtists(artists) {
  return artists.slice().sort((a, b) => {
    const ka = artistSortKey(a);
    const kb = artistSortKey(b);
    return ka < kb ? -1 : ka > kb ? 1 : 0;
  });
}

export function sortedGenres(genres) {
  return genres.slice().sort((a, b) => {
    const ka = a.toLowerCase();
    const kb = b.toLowerCase();
    return ka < kb ? -1 : ka > kb ? 1 : 0;
  });
}

export function derivedDecades(records) {
  const set = new Set();
  for (const r of records) set.add(Math.floor(r.year / 10) * 10);
  return Array.from(set).sort((a, b) => a - b);
}
