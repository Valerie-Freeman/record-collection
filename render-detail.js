import { escapeHtml, stars, formatYear } from "./render-helpers.js";

let detailCloseTimer = null;

function detailCloseDelay() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 260;
}

function renderTracks(tracks) {
  if (!Array.isArray(tracks) || tracks.length === 0) return "";

  const groups = [];
  let current = null;
  for (const track of tracks) {
    if (!current || current.side !== track.side) {
      current = { side: track.side, titles: [] };
      groups.push(current);
    }
    current.titles.push(track.title);
  }

  const groupsHtml = groups
    .map(
      ({ side, titles }) => `
        <section class="detail-side">
          <h4 class="detail-side-label">Side ${escapeHtml(side)}</h4>
          <ol class="detail-track-list">
            ${titles.map((t) => `<li>${escapeHtml(t)}</li>`).join("")}
          </ol>
        </section>
      `
    )
    .join("");

  return `
    <section class="detail-tracks" aria-label="Track listing">
      ${groupsHtml}
    </section>
  `;
}

function renderArtwork(record) {
  return `
    <img
      class="detail-art"
      src="${escapeHtml(record.artwork)}"
      alt="${escapeHtml(record.title)} by ${escapeHtml(record.artist)}"
      width="300"
      height="300"
      data-fallback-title="${escapeHtml(record.title)}"
    />
  `;
}

function renderReadBody(record) {
  const genreChips = record.genres
    .map((g) => `<span class="detail-genre-chip">${escapeHtml(g)}</span>`)
    .join("");
  const notesHtml = record.notes
    ? `<p class="detail-notes">${escapeHtml(record.notes)}</p>`
    : "";
  return `
    <div class="detail-header-row">
      ${renderArtwork(record)}
      <div class="detail-info">
        <h2 id="detail-title" class="detail-title">${escapeHtml(record.title)}</h2>
        <p class="detail-artist">${escapeHtml(record.artist)}</p>
        <p class="detail-meta">${formatYear(record.year)}</p>
        <p class="detail-rating" aria-label="Rated ${record.rating} out of 5">
          <span aria-hidden="true">${stars(record.rating)}</span>
        </p>
      </div>
    </div>
    <div class="detail-genres">${genreChips}</div>
    ${notesHtml}
    ${renderTracks(record.tracks)}
  `;
}

function renderRatingEditor(rating) {
  const buttons = [1, 2, 3, 4, 5]
    .map((n) => {
      const filled = n <= rating;
      const label = n === 1 ? "1 star" : `${n} stars`;
      return `<button
        type="button"
        class="rating-star${filled ? " is-filled" : ""}"
        data-edit-rating="${n}"
        role="radio"
        aria-checked="${n === rating ? "true" : "false"}"
        aria-label="${label}"
      >${filled ? "\u2605" : "\u2606"}</button>`;
    })
    .join("");
  return `
    <div class="rating-input" role="radiogroup" aria-label="Rating">
      ${buttons}
    </div>
  `;
}

function renderEditBody(record, draft) {
  const genreChips = draft.genres
    .map((g) => `<span class="detail-genre-chip">${escapeHtml(g)}</span>`)
    .join("");
  const notesHtml = `<textarea
      class="detail-notes-input"
      data-edit-field="notes"
      aria-label="Notes"
      placeholder="Notes"
      rows="3"
    >${escapeHtml(draft.notes ?? "")}</textarea>`;
  return `
    <div class="detail-header-row">
      ${renderArtwork(record)}
      <div class="detail-info">
        <h2 id="detail-title" class="detail-title">${escapeHtml(draft.title)}</h2>
        <p class="detail-artist">${escapeHtml(draft.artist)}</p>
        <p class="detail-meta">${formatYear(draft.year)}</p>
        ${renderRatingEditor(draft.rating)}
      </div>
    </div>
    <div class="detail-genres">${genreChips}</div>
    ${notesHtml}
    ${renderTracks(draft.tracks)}
  `;
}

export function renderDetailSheet(state) {
  const sheet = document.getElementById("detail-sheet");
  if (!sheet) return;

  if (!state.openRecordId) {
    if (!sheet.hidden && !sheet.classList.contains("sheet-out")) {
      sheet.classList.add("sheet-out");
      if (detailCloseTimer) clearTimeout(detailCloseTimer);
      detailCloseTimer = setTimeout(() => {
        sheet.hidden = true;
        sheet.classList.remove("sheet-out");
        document.body.classList.remove("detail-open");
        detailCloseTimer = null;
      }, detailCloseDelay());
    }
    return;
  }

  const record = state.records.find((r) => r.id === state.openRecordId);
  if (!record) {
    sheet.hidden = true;
    document.body.classList.remove("detail-open");
    return;
  }

  if (detailCloseTimer) {
    clearTimeout(detailCloseTimer);
    detailCloseTimer = null;
  }
  sheet.classList.remove("sheet-out");

  const editing = !!state.editing;
  sheet.classList.toggle("detail-editing", editing);

  const editBtn = document.getElementById("detail-edit");
  if (editBtn) editBtn.hidden = !state.owner || editing;

  const editFooter = document.getElementById("detail-edit-footer");
  if (editFooter) editFooter.hidden = !editing;

  if (!editing) {
    const errEl = document.getElementById("detail-edit-error");
    if (errEl) {
      errEl.hidden = true;
      errEl.textContent = "";
    }
  }

  const body = document.getElementById("detail-body");
  if (body) {
    const desiredKey = `${record.id}:${editing ? "edit" : "read"}`;
    if (body.dataset.bodyKey !== desiredKey) {
      body.innerHTML =
        editing && state.draft
          ? renderEditBody(record, state.draft)
          : renderReadBody(record);
      body.dataset.bodyKey = desiredKey;
    }
  }

  sheet.hidden = false;
  document.body.classList.add("detail-open");
}
