export function render(state) {
  const countEl = document.getElementById("record-count");
  if (countEl) {
    countEl.textContent = String(state.records.length);
  }
}
