const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);
}

function stars(rating) {
  return "★".repeat(rating) + "☆".repeat(5 - rating);
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

  if (countEl) {
    countEl.hidden = false;
    countEl.textContent = String(state.records.length);
  }

  const list = document.getElementById("record-list");
  if (list) {
    list.innerHTML = state.records.map(renderCard).join("");
  }
}
