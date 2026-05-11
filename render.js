import { visibleRecords } from "./filter.js";
import { renderCard } from "./render-card.js";
import { renderDetailSheet } from "./render-detail.js";
import { syncFilterSheet } from "./render-filters.js";
import { renderChips } from "./render-chips.js";

export { buildFilterSheet } from "./render-filters.js";

const GEAR_SVG =
  '<svg viewBox="0 0 24 24" fill="currentColor" focusable="false"><path d="M19.43 12.98c.04-.32.07-.64.07-.98s-.03-.66-.07-.98l2.11-1.65c.19-.15.24-.42.12-.64l-2-3.46c-.12-.22-.39-.3-.61-.22l-2.49 1c-.52-.4-1.08-.73-1.69-.98l-.38-2.65C14.46 2.18 14.25 2 14 2h-4c-.25 0-.46.18-.49.42l-.38 2.65c-.61.25-1.17.59-1.69.98l-2.49-1c-.23-.09-.49 0-.61.22l-2 3.46c-.13.22-.07.49.12.64l2.11 1.65c-.04.32-.07.65-.07.98s.03.66.07.98l-2.11 1.65c-.19.15-.24.42-.12.64l2 3.46c.12.22.39.3.61.22l2.49-1c.52.4 1.08.73 1.69.98l.38 2.65c.03.24.24.42.49.42h4c.25 0 .46-.18.49-.42l.38-2.65c.61-.25 1.17-.59 1.69-.98l2.49 1c.23.09.49 0 .61-.22l2-3.46c.12-.22.07-.49-.12-.64l-2.11-1.65zM12 15.5c-1.93 0-3.5-1.57-3.5-3.5s1.57-3.5 3.5-3.5 3.5 1.57 3.5 3.5-1.57 3.5-3.5 3.5z"/></svg>';

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
    if (glyph) glyph.innerHTML = GEAR_SVG;
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
