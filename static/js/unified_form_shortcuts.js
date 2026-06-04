(function () {
  if (window.__UNIFIED_FORM_SHORTCUTS_INSTALLED__ === true) return;
  window.__UNIFIED_FORM_SHORTCUTS_INSTALLED__ = true;

  function onReady(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  function isVisible(el) {
    return !!(el && el.offsetParent !== null && !el.disabled);
  }

  function getHelpModal() {
    return document.getElementById("keyboardHelp");
  }

  function ensureHelpModal() {
    if (getHelpModal()) return;
    const modal = document.createElement("div");
    modal.id = "keyboardHelp";
    modal.className = "keyboard-help-modal";
    modal.style.display = "none";
    modal.setAttribute("role", "dialog");
    modal.setAttribute("aria-modal", "true");
    modal.setAttribute("aria-label", "Keyboard shortcuts");
    modal.innerHTML = `
      <div class="keyboard-help-content">
        <h3 class="fw-bold text-primary mb-4">Keyboard Shortcuts</h3>
        <div class="shortcuts-grid">
          <div class="shortcut-item"><kbd class="fw-bold">F1</kbd> <span>Show shortcuts</span></div>
          <div class="shortcut-item"><kbd class="fw-bold">F2</kbd> <span>Focus first field</span></div>
          <div class="shortcut-item"><kbd class="fw-bold">F5</kbd> <span>Save / Submit</span></div>
          <div class="shortcut-item"><kbd class="fw-bold">Ctrl+S</kbd> <span>Save / Submit</span></div>
          <div class="shortcut-item"><kbd class="fw-bold">Esc</kbd> <span>Close shortcuts / Back</span></div>
          <div class="shortcut-item"><kbd class="fw-bold">Enter</kbd> <span>Next field</span></div>
          <div class="shortcut-item"><kbd class="fw-bold">Shift+Enter</kbd> <span>Previous field</span></div>
        </div>
        <div class="text-center mt-4">
          <button type="button" class="btn btn-danger btn-lg fw-bold px-4" onclick="hideKeyboardHelp()">Close</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  function isHelpOpen() {
    const modal = getHelpModal();
    if (!modal) return false;
    const style = (modal.style && modal.style.display) || "";
    if (style) return style !== "none";
    return window.getComputedStyle(modal).display !== "none";
  }

  window.showKeyboardHelp =
    window.showKeyboardHelp ||
    function () {
      const modal = getHelpModal();
      if (!modal) return;
      modal.style.display = "flex";
      const closeBtn = modal.querySelector("button, [role='button'], a");
      if (closeBtn) closeBtn.focus();
    };

  window.hideKeyboardHelp =
    window.hideKeyboardHelp ||
    function () {
      const modal = getHelpModal();
      if (!modal) return;
      modal.style.display = "none";
    };

  function primaryField() {
    const explicit = document.querySelector("[data-kb-primary='1']");
    if (explicit && isVisible(explicit)) return explicit;
    const form = document.querySelector("form");
    if (!form) return null;
    const selector = "input:not([type='hidden']), select, textarea";
    const first = form.querySelector(selector);
    return isVisible(first) ? first : null;
  }

  function cancelTarget() {
    const el = document.querySelector("[data-kb-cancel], #kbCancel");
    return isVisible(el) ? el : null;
  }

  function submitForm() {
    const btn =
      document.querySelector("[data-kb-submit]") ||
      document.querySelector("form button[type='submit'], form input[type='submit']");
    const form = (btn && btn.form) || document.querySelector("form");
    if (!form) return;
    if (typeof form.requestSubmit === "function") form.requestSubmit(btn || undefined);
    else form.submit();
  }

  function focusPrimary() {
    const field = primaryField();
    if (!field) return;
    field.focus();
    if (typeof field.select === "function" && (field.type === "text" || field.type === "number")) {
      field.select();
    }
  }

  onReady(function () {
    const isAddScreen = document.body && document.body.classList && document.body.classList.contains("add-screen");
    const isOrderEntry = (window.__ADD_ORDER_PC_BUSY__ === true) || !!document.querySelector(".busy-order-pc, #orderBody, #mainOrderCard");
    if (!isAddScreen || isOrderEntry) return;

    if (!document.querySelector("form")) return;

    ensureHelpModal();
    const modal = getHelpModal();
    if (modal && !modal.style.display) modal.style.display = "none";

    document.addEventListener("keydown", function (e) {
      // F1: help
      if (e.key === "F1") {
        e.preventDefault();
        if (isHelpOpen()) window.hideKeyboardHelp();
        else window.showKeyboardHelp();
        return;
      }

      // F2: focus primary field
      if (e.key === "F2") {
        e.preventDefault();
        focusPrimary();
        return;
      }

      // F5 / Ctrl+S: submit
      if (e.key === "F5" || (e.ctrlKey && (e.key === "s" || e.key === "S"))) {
        e.preventDefault();
        submitForm();
        return;
      }

      // Esc: close help or go back
      if (e.key === "Escape") {
        if (isHelpOpen()) {
          e.preventDefault();
          window.hideKeyboardHelp();
          return;
        }
        const cancel = cancelTarget();
        if (cancel) {
          e.preventDefault();
          cancel.click();
          return;
        }
      }
    });

    // Auto-focus first field for keyboard-first entry
    setTimeout(function () {
      const field = primaryField();
      if (field && document.activeElement === document.body) field.focus();
    }, 50);
  });
})();
