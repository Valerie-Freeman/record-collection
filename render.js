import { visibleRecords } from "./filter.js";

const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);
}

function stars(rating) {
  return "★".repeat(rating) + "☆".repeat(5 - rating);
}

function artistSortKey(name) {
  return name.replace(/^the\s+/i, "").toLowerCase();
}

function sortedArtists(artists) {
  return artists.slice().sort((a, b) => {
    const ka = artistSortKey(a);
    const kb = artistSortKey(b);
    return ka < kb ? -1 : ka > kb ? 1 : 0;
  });
}

function sortedGenres(genres) {
  return genres.slice().sort((a, b) => {
    const ka = a.toLowerCase();
    const kb = b.toLowerCase();
    return ka < kb ? -1 : ka > kb ? 1 : 0;
  });
}

function derivedDecades(records) {
  const set = new Set();
  for (const r of records) set.add(Math.floor(r.year / 10) * 10);
  return Array.from(set).sort((a, b) => a - b);
}

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

function renderChips(state) {
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

function syncFilterSheet(state) {
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

function renderCard(record) {
  const title = escapeHtml(record.title);
  const artist = escapeHtml(record.artist);
  const artwork = escapeHtml(record.artwork);
  const ratingLabel = `Rated ${record.rating} out of 5`;
  return `
    <li class="card" data-id="${escapeHtml(record.id)}">
      <img class="card-art" src="${artwork}" alt="${title} by ${artist}" loading="lazy" width="96" height="96" />
      <div class="card-body">
        <h2 class="card-title">${title}</h2>
        <p class="card-artist">${artist}</p>
        <p class="card-rating" aria-label="${ratingLabel}"><span aria-hidden="true">${stars(record.rating)}</span></p>
      </div>
    </li>
  `;
}

export function render(state) {
  const main = document.querySelector("main");
  const countEl = document.getElementById("record-count");

  if (state.error) {
    if (countEl) countEl.hidden = true;
    if (main) {
      main.innerHTML = `
        <div class="error-state" role="alert">
          <p>Couldn't load the collection. Try refreshing.</p>
        </div>
      `;
    }
    return;
  }

  const visible = visibleRecords(state.records, state);

  if (countEl) {
    countEl.hidden = false;
    countEl.textContent = String(visible.length);
  }

  const list = document.getElementById("record-list");
  if (list) {
    list.innerHTML = visible.map(renderCard).join("");
  }

  renderChips(state);
  syncFilterSheet(state);
}
