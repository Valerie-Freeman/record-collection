import {
  escapeHtml,
  stars,
  sortedArtists,
  sortedGenres,
  derivedDecades,
} from "./render-helpers.js";

function renderPill(category, rawValue, label) {
  const value = escapeHtml(rawValue);
  return `
    <button
      type="button"
      class="pill"
      aria-pressed="false"
      data-filter="${category}"
      data-value="${value}"
    >${escapeHtml(label)}</button>
  `;
}

function renderFilterGroup(title, category, options) {
  const pills = options
    .map(({ value, label }) => renderPill(category, value, label))
    .join("");
  const optionsId = `filter-options-${category}`;
  return `
    <section class="filter-group" data-category="${category}" data-collapsed>
      <button
        type="button"
        class="filter-group-header"
        aria-expanded="false"
        aria-controls="${optionsId}"
      >
        <span class="filter-group-title">${escapeHtml(title)}</span>
        <span class="filter-group-meta">
          <span class="filter-count" data-count-for="${category}" hidden>0</span>
          <span class="filter-toggle" aria-hidden="true"></span>
        </span>
      </button>
      <div class="filter-options" id="${optionsId}">${pills}</div>
    </section>
  `;
}

export function buildFilterSheet(state) {
  const body = document.getElementById("filter-sheet-body");
  if (!body) return;

  const artistOptions = sortedArtists(state.artists).map((name) => ({
    value: name,
    label: name,
  }));

  const decadeOptions = derivedDecades(state.records).map((decade) => ({
    value: String(decade),
    label: `${decade}s`,
  }));

  const genreOptions = sortedGenres(state.genres).map((name) => ({
    value: name,
    label: name,
  }));

  const ratingOptions = [5, 4, 3, 2, 1].map((rating) => ({
    value: String(rating),
    label: stars(rating),
  }));

  body.innerHTML = [
    renderFilterGroup("Artist", "artists", artistOptions),
    renderFilterGroup("Decade", "decades", decadeOptions),
    renderFilterGroup("Genre", "genres", genreOptions),
    renderFilterGroup("Rating", "ratings", ratingOptions),
  ].join("");
}

export function syncFilterSheet(state) {
  const body = document.getElementById("filter-sheet-body");
  if (!body) return;

  const categoryValue = (category, raw) =>
    category === "decades" || category === "ratings" ? Number(raw) : raw;

  for (const pill of body.querySelectorAll(".pill")) {
    const category = pill.dataset.filter;
    const value = categoryValue(category, pill.dataset.value);
    const pressed = state.filters[category]?.has(value) ? "true" : "false";
    if (pill.getAttribute("aria-pressed") !== pressed) {
      pill.setAttribute("aria-pressed", pressed);
    }
  }

  for (const badge of body.querySelectorAll(".filter-count")) {
    const category = badge.dataset.countFor;
    const count = state.filters[category]?.size ?? 0;
    if (count > 0) {
      badge.textContent = String(count);
      badge.hidden = false;
    } else {
      badge.hidden = true;
    }
  }
}
