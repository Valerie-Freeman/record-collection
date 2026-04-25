import { loadCollection } from "./data.js";
import { render, buildFilterSheet, installArtworkFallback } from "./render.js";
import { startRouter } from "./router.js";
import { visibleRecords } from "./filter.js";

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
  error: false,
};

try {
  const { records, artists, genres } = await loadCollection();
  state.records = records;
  state.artists = artists;
  state.genres = genres;
} catch (err) {
  console.error("Failed to load collection:", err);
  state.error = true;
}

if (state.error) {
  render(state);
} else {
  installArtworkFallback();
  buildFilterSheet(state);

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

  const rubricOpen = document.getElementById("rubric-open");
  const rubricClose = document.getElementById("rubric-close");
  const rubricModal = document.getElementById("rubric-modal");

  let rubricReturnFocus = null;
  let rubricCloseTimer = null;

  function setRubricOpen(open) {
    if (!rubricModal || !rubricOpen) return;

    if (rubricCloseTimer) {
      clearTimeout(rubricCloseTimer);
      rubricCloseTimer = null;
    }

    rubricOpen.setAttribute("aria-expanded", open ? "true" : "false");

    if (open) {
      document.body.classList.add("modal-open");
      rubricModal.classList.remove("modal-out");
      rubricModal.hidden = false;
      rubricReturnFocus = document.activeElement;
      rubricClose?.focus();
    } else {
      rubricModal.classList.add("modal-out");
      if (rubricReturnFocus instanceof HTMLElement) {
        rubricReturnFocus.focus();
        rubricReturnFocus = null;
      }
      rubricCloseTimer = setTimeout(() => {
        rubricModal.hidden = true;
        rubricModal.classList.remove("modal-out");
        document.body.classList.remove("modal-open");
        rubricCloseTimer = null;
      }, sheetCloseDelay());
    }
  }

  rubricOpen?.addEventListener("click", () => setRubricOpen(true));
  rubricClose?.addEventListener("click", () => setRubricOpen(false));
  rubricModal?.addEventListener("click", (e) => {
    if (e.target === rubricModal) setRubricOpen(false);
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
    const prevId = state.openRecordId;
    const nextId = route.type === "record" ? route.id : null;

    if (!prevId && nextId) {
      const card = document.activeElement?.closest?.(".card");
      detailReturnFocusSelector = card?.dataset.id
        ? `.card[data-id="${CSS.escape(card.dataset.id)}"] .card-link`
        : null;
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
    if (rubricModal && !rubricModal.hidden) {
      setRubricOpen(false);
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
