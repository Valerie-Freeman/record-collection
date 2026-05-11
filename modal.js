function reducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Controller for a modal element that opens with the `modal-open` body class
 * pattern and animates out via the `modal-out` class. Shared by every modal in
 * the app (rubric, signin, account, plus anything future).
 *
 * @param {{ modalEl: HTMLElement|null, openerEl: HTMLElement|null, closeEl: HTMLElement|null }} opts
 * @returns {{ setOpen: (open: boolean) => void, isOpen: () => boolean }}
 */
export function createModal({ modalEl, openerEl, closeEl }) {
  let returnFocus = null;
  let closeTimer = null;

  return {
    setOpen(open) {
      if (!modalEl) return;
      const currentlyOpen = !modalEl.hidden;
      if (open === currentlyOpen && !closeTimer) return;

      if (closeTimer) {
        clearTimeout(closeTimer);
        closeTimer = null;
      }
      openerEl?.setAttribute("aria-expanded", open ? "true" : "false");

      if (open) {
        document.body.classList.add("modal-open");
        modalEl.classList.remove("modal-out");
        modalEl.hidden = false;
        returnFocus = document.activeElement;
        closeEl?.focus();
        return;
      }

      modalEl.classList.add("modal-out");
      if (returnFocus instanceof HTMLElement) {
        returnFocus.focus();
        returnFocus = null;
      }
      closeTimer = setTimeout(() => {
        modalEl.hidden = true;
        modalEl.classList.remove("modal-out");
        document.body.classList.remove("modal-open");
        closeTimer = null;
      }, reducedMotion() ? 0 : 260);
    },

    isOpen() {
      return !!modalEl && !modalEl.hidden;
    },
  };
}
