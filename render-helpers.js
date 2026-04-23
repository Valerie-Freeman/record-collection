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

export function formatYear(year) {
  const [start, end] = year;
  return start === end ? String(start) : `${start}\u2013${end}`;
}

export function derivedDecades(records) {
  const set = new Set();
  for (const r of records) {
    const [start, end] = r.year;
    const startDecade = Math.floor(start / 10) * 10;
    const endDecade = Math.floor(end / 10) * 10;
    for (let d = startDecade; d <= endDecade; d += 10) set.add(d);
  }
  return Array.from(set).sort((a, b) => a - b);
}
