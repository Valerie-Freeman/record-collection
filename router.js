/** Parse a location hash into a route descriptor. */
function parseHash(hash) {
  const path = hash.replace(/^#/, "") || "/";
  const match = path.match(/^\/record\/(.+)$/);
  if (match) return { type: "record", id: match[1] };
  return { type: "list" };
}

/** Register a hashchange listener and immediately dispatch the current route. */
export function startRouter(onChange) {
  window.addEventListener("hashchange", () => onChange(parseHash(location.hash)));
  onChange(parseHash(location.hash));
}
