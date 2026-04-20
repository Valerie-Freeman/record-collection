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
};

render(state);
