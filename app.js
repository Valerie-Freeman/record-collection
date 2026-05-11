import { loadCollection, updateRecord } from "./data.js";
import {
  render,
  buildFilterSheet,
  installArtworkFallback,
  renderAccountButton,
} from "./render.js";
import { startRouter } from "./router.js";
import { visibleRecords } from "./filter.js";
import { createModal } from "./modal.js";
import {
  signInWithGoogle,
  signOut,
  getOwner,
  onOwnerChange,
} from "./auth.js";

const state = {
  records: [],
  artists: [],
  genres: [],
  search: "",
  sort: { field: "artist", dir: "asc" },
  filters: {
    artists: new Set(),
    decades: new Set(),
    genres: new Set(),
    ratings: new Set(),
  },
  openRecordId: null,
  owner: null,
  editing: false,
  draft: null,
  error: false,
};

function enterEditMode() {
  const record = state.records.find((r) => r.id === state.openRecordId);
  if (!record || !state.owner) return;
  state.draft = structuredClone(record);
  state.editing = true;
  render(state);
}

function exitEditMode() {
  state.editing = false;
  state.draft = null;
  render(state);
}

function showSaveError(message) {
  const errEl = document.getElementById("detail-edit-error");
  if (!errEl) return;
  errEl.textContent = message;
  errEl.hidden = false;
}

function clearSaveError() {
  const errEl = document.getElementById("detail-edit-error");
  if (!errEl) return;
  errEl.textContent = "";
  errEl.hidden = true;
}

function setSavingDisabled(disabled) {
  const saveBtn = document.getElementById("detail-save");
  const cancelBtn = document.getElementById("detail-cancel");
  if (saveBtn) saveBtn.disabled = disabled;
  if (cancelBtn) cancelBtn.disabled = disabled;
}

function diffDraft(record, draft) {
  const updates = {};
  if (draft.rating !== record.rating) {
    updates.rating = draft.rating;
  }
  const normalizedNotes = draft.notes === "" ? null : draft.notes ?? null;
  const currentNotes = record.notes ?? null;
  if (normalizedNotes !== currentNotes) {
    updates.notes = normalizedNotes;
  }
  return updates;
}

async function saveDraft() {
  if (!state.editing || !state.draft) return;
  const record = state.records.find((r) => r.id === state.openRecordId);
  if (!record) return;

  const updates = diffDraft(record, state.draft);
  if (Object.keys(updates).length === 0) {
    exitEditMode();
    return;
  }

  clearSaveError();
  setSavingDisabled(true);

  try {
    await updateRecord(record.db_id, updates);
  } catch (err) {
    setSavingDisabled(false);
    showSaveError(err?.message || "Couldn't save changes.");
    return;
  }

  if ("rating" in updates) record.rating = updates.rating;
  if ("notes" in updates) {
    if (updates.notes === null) delete record.notes;
    else record.notes = updates.notes;
  }

  setSavingDisabled(false);
  exitEditMode();
}

function syncRatingStars(rating) {
  const container = document.querySelector("#detail-body .rating-input");
  if (!container) return;
  const buttons = container.querySelectorAll(".rating-star");
  buttons.forEach((btn, idx) => {
    const n = idx + 1;
    const filled = n <= rating;
    btn.classList.toggle("is-filled", filled);
    btn.textContent = filled ? "\u2605" : "\u2606";
    btn.setAttribute("aria-checked", n === rating ? "true" : "false");
  });
}

try {
  const [collection, owner] = await Promise.all([
    loadCollection(),
    getOwner(),
  ]);
  state.records = collection.records;
  state.artists = collection.artists;
  state.genres = collection.genres;
  state.owner = owner;
} catch (err) {
  console.error("Failed to load collection:", err);
  state.error = true;
}

if (state.error) {
  render(state);
} else {
  installArtworkFallback();
  buildFilterSheet(state);
  renderAccountButton(state.owner);

  const searchInput = document.getElementById("search-input");
  if (searchInput) {
    let debounceId;
    searchInput.addEventListener("input", (e) => {
      clearTimeout(debounceId);
      const value = e.target.value;
      debounceId = setTimeout(() => {
        state.search = value;
        render(state);
      }, 150);
    });
  }

  const sortField = document.getElementById("sort-field");
  const sortDir = document.getElementById("sort-dir");

  function updateDirButton(dir) {
    const asc = dir === "asc";
    sortDir.textContent = asc ? "↑ Asc" : "↓ Desc";
    sortDir.setAttribute("aria-pressed", asc ? "false" : "true");
    sortDir.setAttribute(
      "aria-label",
      asc ? "Sort direction: ascending" : "Sort direction: descending"
    );
  }

  if (sortField && sortDir) {
    sortField.addEventListener("change", (e) => {
      const field = e.target.value;
      const dir = field === "year" || field === "rating" ? "desc" : "asc";
      state.sort = { field, dir };
      updateDirButton(dir);
      render(state);
    });

    sortDir.addEventListener("click", () => {
      const dir = state.sort.dir === "asc" ? "desc" : "asc";
      state.sort = { ...state.sort, dir };
      updateDirButton(dir);
      render(state);
    });
  }

  const filterOpen = document.getElementById("filter-open");
  const filterClose = document.getElementById("filter-close");
  const filterClear = document.getElementById("filter-clear");
  const filterSheet = document.getElementById("filter-sheet");
  const filterSheetBody = document.getElementById("filter-sheet-body");
  const filterChips = document.getElementById("filter-chips");

  let filterReturnFocus = null;
  let filterSheetCloseTimer = null;

  function sheetCloseDelay() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 260;
  }

  function setSheetOpen(open) {
    if (!filterSheet || !filterOpen) return;

    if (filterSheetCloseTimer) {
      clearTimeout(filterSheetCloseTimer);
      filterSheetCloseTimer = null;
    }

    filterOpen.setAttribute("aria-expanded", open ? "true" : "false");

    if (open) {
      document.body.classList.add("sheet-open");
      filterSheet.classList.remove("sheet-out");
      filterSheet.hidden = false;
      filterReturnFocus = document.activeElement;
      filterClose?.focus();
    } else {
      filterSheet.classList.add("sheet-out");
      if (filterReturnFocus instanceof HTMLElement) {
        filterReturnFocus.focus();
        filterReturnFocus = null;
      }
      filterSheetCloseTimer = setTimeout(() => {
        filterSheet.hidden = true;
        filterSheet.classList.remove("sheet-out");
        document.body.classList.remove("sheet-open");
        filterSheetCloseTimer = null;
      }, sheetCloseDelay());
    }
  }

  function coerce(category, value) {
    return category === "decades" || category === "ratings" ? Number(value) : value;
  }

  function clearAllFilters() {
    state.filters.artists.clear();
    state.filters.decades.clear();
    state.filters.genres.clear();
    state.filters.ratings.clear();
  }

  function resetSearchAndFilters() {
    clearAllFilters();
    state.search = "";
    const input = document.getElementById("search-input");
    if (input) input.value = "";
  }

  const emptyClear = document.getElementById("empty-clear");
  emptyClear?.addEventListener("click", () => {
    resetSearchAndFilters();
    render(state);
  });

  if (filterOpen && filterSheet) {
    filterOpen.addEventListener("click", () => setSheetOpen(true));
    filterClose?.addEventListener("click", () => setSheetOpen(false));

    filterClear?.addEventListener("click", () => {
      clearAllFilters();
      render(state);
    });

    filterSheetBody?.addEventListener("click", (e) => {
      const el = e.target instanceof Element ? e.target : null;
      if (!el) return;

      const header = el.closest(".filter-group-header");
      if (header) {
        const section = header.closest(".filter-group");
        if (!section) return;
        const collapsed = section.toggleAttribute("data-collapsed");
        header.setAttribute("aria-expanded", collapsed ? "false" : "true");
        return;
      }

      const pill = el.closest(".pill");
      if (pill) {
        const category = pill.dataset.filter;
        if (!category || !(category in state.filters)) return;
        const value = coerce(category, pill.dataset.value);
        if (state.filters[category].has(value)) state.filters[category].delete(value);
        else state.filters[category].add(value);
        render(state);
      }
    });

    filterChips?.addEventListener("click", (e) => {
      const target =
        e.target instanceof Element
          ? e.target.closest("[data-chip-filter],[data-chip-clear]")
          : null;
      if (!target) return;
      if (target.hasAttribute("data-chip-clear")) {
        clearAllFilters();
      } else {
        const category = target.getAttribute("data-chip-filter");
        const value = coerce(category, target.getAttribute("data-chip-value"));
        state.filters[category]?.delete(value);
      }
      render(state);
    });
  }

  const rubricModalEl = document.getElementById("rubric-modal");
  const rubricOpenBtn = document.getElementById("rubric-open");
  const rubricCloseBtn = document.getElementById("rubric-close");
  const signinModalEl = document.getElementById("signin-modal");
  const accountModalEl = document.getElementById("account-modal");
  const accountBtn = document.getElementById("account-btn");

  const rubricModal = createModal({
    modalEl: rubricModalEl,
    openerEl: rubricOpenBtn,
    closeEl: rubricCloseBtn,
  });

  const signinModal = createModal({
    modalEl: signinModalEl,
    openerEl: null,
    closeEl: document.getElementById("signin-close"),
  });

  const accountModal = createModal({
    modalEl: accountModalEl,
    openerEl: accountBtn,
    closeEl: document.getElementById("account-close"),
  });

  rubricOpenBtn?.addEventListener("click", () => rubricModal.setOpen(true));
  rubricCloseBtn?.addEventListener("click", () => rubricModal.setOpen(false));
  rubricModalEl?.addEventListener("click", (e) => {
    if (e.target === rubricModalEl) rubricModal.setOpen(false);
  });

  document
    .getElementById("signin-close")
    ?.addEventListener("click", () => (location.hash = "#/"));
  signinModalEl?.addEventListener("click", (e) => {
    if (e.target === signinModalEl) location.hash = "#/";
  });
  document
    .getElementById("signin-google")
    ?.addEventListener("click", () => signInWithGoogle());

  document
    .getElementById("account-close")
    ?.addEventListener("click", () => accountModal.setOpen(false));
  accountModalEl?.addEventListener("click", (e) => {
    if (e.target === accountModalEl) accountModal.setOpen(false);
  });
  document
    .getElementById("signout-btn")
    ?.addEventListener("click", async () => {
      await signOut();
      accountModal.setOpen(false);
    });

  accountBtn?.addEventListener("click", () => {
    if (state.owner) {
      const emailEl = document.getElementById("account-email");
      if (emailEl) emailEl.textContent = state.owner;
      accountModal.setOpen(true);
    } else {
      location.hash = "#/signin";
    }
  });

  onOwnerChange((owner) => {
    state.owner = owner;
    renderAccountButton(owner);
    if (owner) {
      if (location.hash === "#/signin") location.hash = "#/";
    } else {
      accountModal.setOpen(false);
      if (state.editing) {
        state.editing = false;
        state.draft = null;
      }
    }
    render(state);
  });

  const surpriseBtn = document.getElementById("surprise-me");
  surpriseBtn?.addEventListener("click", () => {
    const visible = visibleRecords(state.records, state);
    if (visible.length === 0) return;
    const pick = visible[Math.floor(Math.random() * visible.length)];
    location.hash = `#/record/${pick.id}`;
  });

  const detailClose = document.getElementById("detail-close");
  detailClose?.addEventListener("click", () => {
    location.hash = "#/";
  });

  document
    .getElementById("detail-edit")
    ?.addEventListener("click", () => enterEditMode());

  document
    .getElementById("detail-cancel")
    ?.addEventListener("click", () => exitEditMode());

  document.getElementById("detail-body")?.addEventListener("click", (e) => {
    if (!state.editing || !state.draft) return;
    const el = e.target instanceof Element ? e.target : null;
    if (!el) return;

    const ratingBtn = el.closest("[data-edit-rating]");
    if (ratingBtn) {
      const value = Number(ratingBtn.dataset.editRating);
      if (Number.isInteger(value) && value >= 1 && value <= 5) {
        state.draft.rating = value;
        syncRatingStars(value);
      }
      return;
    }
  });

  document.getElementById("detail-body")?.addEventListener("input", (e) => {
    if (!state.editing || !state.draft) return;
    const el = e.target instanceof Element ? e.target : null;
    const field = el?.getAttribute("data-edit-field");
    if (field === "notes" && el instanceof HTMLTextAreaElement) {
      state.draft.notes = el.value;
    }
  });

  document
    .getElementById("detail-save")
    ?.addEventListener("click", () => saveDraft());

  const detailSheet = document.getElementById("detail-sheet");
  if (detailSheet) {
    let touchStartY = 0;
    detailSheet.addEventListener("touchstart", (e) => {
      touchStartY = e.touches[0].clientY;
    }, { passive: true });
    detailSheet.addEventListener("touchend", (e) => {
      const dy = e.changedTouches[0].clientY - touchStartY;
      if (dy > 80 && detailSheet.scrollTop === 0) {
        location.hash = "#/";
      }
    }, { passive: true });
  }

  let detailReturnFocusSelector = null;

  startRouter((route) => {
    if (route.type === "signin") {
      if (state.owner) {
        location.hash = "#/";
        return;
      }
      state.openRecordId = null;
      render(state);
      signinModal.setOpen(true);
      return;
    }
    signinModal.setOpen(false);

    const prevId = state.openRecordId;
    const nextId = route.type === "record" ? route.id : null;

    if (!prevId && nextId) {
      const card = document.activeElement?.closest?.(".card");
      detailReturnFocusSelector = card?.dataset.id
        ? `.card[data-id="${CSS.escape(card.dataset.id)}"] .card-link`
        : null;
    }

    if (prevId !== nextId && state.editing) {
      state.editing = false;
      state.draft = null;
    }

    state.openRecordId = nextId;
    render(state);

    if (!prevId && nextId) {
      document.getElementById("detail-close")?.focus();
    } else if (prevId && !nextId) {
      const target = detailReturnFocusSelector
        ? document.querySelector(detailReturnFocusSelector)
        : null;
      if (target instanceof HTMLElement) target.focus();
      detailReturnFocusSelector = null;
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (rubricModal.isOpen()) {
      rubricModal.setOpen(false);
      return;
    }
    if (accountModal.isOpen()) {
      accountModal.setOpen(false);
      return;
    }
    if (signinModal.isOpen()) {
      location.hash = "#/";
      return;
    }
    if (state.openRecordId) {
      location.hash = "#/";
      return;
    }
    if (filterSheet && !filterSheet.hidden) {
      setSheetOpen(false);
    }
  });
}
