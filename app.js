import { loadCollection } from "./data.js";
import { render } from "./render.js";

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

render(state);

const searchInput = document.getElementById("search-input");
if (searchInput && !state.error) {
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
