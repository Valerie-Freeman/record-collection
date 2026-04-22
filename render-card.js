import { escapeHtml, stars } from "./render-helpers.js";

export function renderCard(record) {
  const id = escapeHtml(record.id);
  const title = escapeHtml(record.title);
  const artist = escapeHtml(record.artist);
  const artwork = escapeHtml(record.artwork);
  const ratingLabel = `Rated ${record.rating} out of 5`;
  return `
    <li class="card" data-id="${id}">
      <a href="#/record/${id}" class="card-link">
        <img class="card-art" src="${artwork}" alt="${title} by ${artist}" loading="lazy" width="96" height="96" data-fallback-title="${title}" />
        <div class="card-body">
          <h2 class="card-title">${title}</h2>
          <p class="card-artist">${artist}</p>
          <p class="card-rating" aria-label="${ratingLabel}"><span aria-hidden="true">${stars(record.rating)}</span></p>
        </div>
      </a>
    </li>
  `;
}
