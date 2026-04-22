import {
  escapeHtml,
  stars,
  sortedArtists,
  sortedGenres,
  derivedDecades,
} from "./render-helpers.js";

function chipEntries(state) {
  const entries = [];
  for (const artist of sortedArtists(state.artists)) {
    if (state.filters.artists.has(artist)) {
      entries.push({ category: "artists", value: artist, label: artist });
    }
  }
  for (const decade of derivedDecades(state.records)) {
    if (state.filters.decades.has(decade)) {
      entries.push({ category: "decades", value: String(decade), label: `${decade}s` });
    }
  }
  for (const genre of sortedGenres(state.genres)) {
    if (state.filters.genres.has(genre)) {
      entries.push({ category: "genres", value: genre, label: genre });
    }
  }
  for (const rating of [5, 4, 3, 2, 1]) {
    if (state.filters.ratings.has(rating)) {
      entries.push({ category: "ratings", value: String(rating), label: stars(rating) });
    }
  }
  return entries;
}

export function renderChips(state) {
  const container = document.getElementById("filter-chips");
  if (!container) return;

  const entries = chipEntries(state);
  if (entries.length === 0) {
    container.hidden = true;
    container.innerHTML = "";
    return;
  }

  const chips = entries
    .map(
      ({ category, value, label }) => `
        <button
          type="button"
          class="chip"
          data-chip-filter="${category}"
          data-chip-value="${escapeHtml(value)}"
          aria-label="Remove filter ${escapeHtml(label)}"
        >
          <span>${escapeHtml(label)}</span>
          <span class="chip-x" aria-hidden="true">×</span>
        </button>
      `
    )
    .join("");

  container.hidden = false;
  container.innerHTML = `
    ${chips}
    <button type="button" class="chip-clear" data-chip-clear>Clear all</button>
  `;
}
