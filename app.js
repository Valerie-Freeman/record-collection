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
  const filterDone = document.getElementById("filter-done");
  const filterClear = document.getElementById("filter-clear");
  const filterSheet = document.getElementById("filter-sheet");
  const filterSheetBody = document.getElementById("filter-sheet-body");
  const filterChips = document.getElementById("filter-chips");

  function setSheetOpen(open) {
    if (!filterSheet || !filterOpen) return;
    filterSheet.hidden = !open;
    filterOpen.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.classList.toggle("sheet-open", open);
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
    filterDone?.addEventListener("click", () => setSheetOpen(false));

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

  startRouter((route) => {
    state.openRecordId = route.type === "record" ? route.id : null;
    render(state);
  });
}
