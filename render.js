import { visibleRecords } from "./filter.js";
import { renderCard } from "./render-card.js";
import { renderDetailSheet } from "./render-detail.js";
import { syncFilterSheet } from "./render-filters.js";
import { renderChips } from "./render-chips.js";

export { buildFilterSheet } from "./render-filters.js";

export function renderAccountButton(owner) {
  const btn = document.getElementById("account-btn");
  if (!btn) return;
  const glyph = btn.querySelector(".account-glyph");
  if (owner) {
    btn.dataset.owner = owner;
    btn.setAttribute("aria-label", `Account (${owner})`);
    if (glyph) glyph.textContent = owner.charAt(0).toUpperCase();
  } else {
    delete btn.dataset.owner;
    btn.setAttribute("aria-label", "Sign in to edit");
    if (glyph) glyph.textContent = "\u2699"; // gear
  }
}

export function installArtworkFallback() {
  document.addEventListener(
    "error",
    (e) => {
      const img = e.target;
      if (!(img instanceof HTMLImageElement)) return;
      if (!img.matches(".card-art, .detail-art")) return;
      const fallback = document.createElement("div");
      fallback.className = `${img.className} artwork-fallback`;
      fallback.textContent = img.dataset.fallbackTitle || "";
      img.replaceWith(fallback);
    },
    true
  );
}

export function render(state) {
  const main = document.querySelector("main");
  const countEl = document.getElementById("record-count");

  if (state.error) {
    if (countEl) countEl.hidden = true;
    if (main) {
      main.innerHTML = `
        <div class="error-state" role="alert">
          <p class="error-state-message">Couldn't load the collection.</p>
          <p class="error-state-hint">Check your connection and try again.</p>
          <button id="error-reload" type="button" class="error-reload">Reload</button>
        </div>
      `;
      const reload = document.getElementById("error-reload");
      reload?.addEventListener("click", () => location.reload());
    }
    return;
  }

  const visible = visibleRecords(state.records, state);

  if (countEl) {
    countEl.hidden = false;
    countEl.textContent = String(visible.length);
  }

  const empty = visible.length === 0;

  const list = document.getElementById("record-list");
  if (list) {
    list.hidden = empty;
    list.innerHTML = empty ? "" : visible.map(renderCard).join("");
  }

  const emptyState = document.getElementById("empty-state");
  if (emptyState) emptyState.hidden = !empty;

  const surpriseBtn = document.getElementById("surprise-me");
  const surpriseHint = document.getElementById("surprise-hint");
  if (surpriseBtn) surpriseBtn.disabled = empty;
  if (surpriseHint) surpriseHint.hidden = true;

  renderChips(state);
  syncFilterSheet(state);
  renderDetailSheet(state);
}
