(function () {
  if (window.__KP_PREVENT_DOUBLE_ACTIONS__ === true) return;
  window.__KP_PREVENT_DOUBLE_ACTIONS__ = true;

  const CLICK_LOCK_MS = 700;
  const FORM_SUBMIT_LOCK_MS = 30000;

  const lastClickAt = new WeakMap();

  function now() {
    return Date.now ? Date.now() : new Date().getTime();
  }

  function isSubmitControl(el) {
    if (!el) return false;
    if (el.tagName === "BUTTON") return (el.getAttribute("type") || "submit").toLowerCase() === "submit";
    if (el.tagName === "INPUT") return (el.getAttribute("type") || "").toLowerCase() === "submit";
    return false;
  }

  function disableSubmitControls(form) {
    if (!form) return;
    const controls = form.querySelectorAll("button[type='submit'], input[type='submit']");
    controls.forEach((c) => {
      if (c.disabled) return;
      c.dataset.kpDisabledByGuard = "1";
      c.disabled = true;
      c.setAttribute("aria-disabled", "true");
    });
  }

  function shouldAllowMultiClick(el) {
    if (!el) return true;
    if (el.dataset && (el.dataset.allowMultiClick === "1" || el.dataset.kpAllowMultiClick === "1")) return true;
    if (el.closest && el.closest("[data-allow-multi-click='1'], [data-kp-allow-multi-click='1']")) return true;
    return false;
  }

  document.addEventListener(
    "click",
    function (e) {
      const target = (e.target && e.target.closest && e.target.closest("button, a, input[type='submit']")) || null;
      if (!target) return;
      if (shouldAllowMultiClick(target)) return;

      // Only guard "action-ish" clicks:
      // - submit controls
      // - anchors with href
      const isSubmit = isSubmitControl(target);
      const isAnchor = target.tagName === "A";
      const href = isAnchor ? (target.getAttribute("href") || "") : "";
      if (isAnchor && href.trim().toLowerCase().startsWith("javascript:")) return;
      if (!isSubmit && !(isAnchor && href && href !== "#")) return;

      const t = now();
      const prev = lastClickAt.get(target) || 0;
      if (t - prev < CLICK_LOCK_MS) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      lastClickAt.set(target, t);
    },
    true
  );

  // Prevent double form submission (e.g., rapid Enter/F5/Ctrl+S or double-click).
  // Runs in bubble phase so custom handlers that call preventDefault() can opt out.
  document.addEventListener(
    "submit",
    function (e) {
      const form = e.target;
      if (!form || !(form instanceof HTMLFormElement)) return;
      if (e.defaultPrevented) return;

      const t = now();
      const last = parseInt(form.dataset.kpLastSubmitAt || "0", 10) || 0;
      if (form.dataset.kpSubmitting === "1" && t - last < FORM_SUBMIT_LOCK_MS) {
        e.preventDefault();
        e.stopImmediatePropagation();
        return;
      }

      form.dataset.kpSubmitting = "1";
      form.dataset.kpLastSubmitAt = String(t);
      disableSubmitControls(form);
    },
    false
  );

  // Desktop safety: never allow scripts to close the main window.
  try {
    const body = document.body;
    const systemMode = body && body.dataset ? String(body.dataset.systemMode || "") : "";
    const isDesktopMode = systemMode.toUpperCase().indexOf("DESKTOP") !== -1;
    if (isDesktopMode && !window.opener) {
      const originalClose = window.close;
      window.close = function () {
        // Allow callers to intentionally bypass guard via window.__KP_ALLOW_WINDOW_CLOSE__ = true
        if (window.__KP_ALLOW_WINDOW_CLOSE__ === true) return originalClose.call(window);
        return;
      };

      // Avoid `javascript:` URL navigations inside embedded webview (can be flaky on some runtimes).
      document.addEventListener(
        "click",
        function (e) {
          const a = e.target && e.target.closest ? e.target.closest("a[href]") : null;
          if (!a) return;
          const h = String(a.getAttribute("href") || "").trim().toLowerCase();
          if (h.startsWith("javascript:")) e.preventDefault();
        },
        true
      );
    }
  } catch (_err) {
    // ignore
  }
})();
