(function () {
  function onReady(fn) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn);
    else fn();
  }

  function isHidden(el) {
    if (!el) return true;
    // offsetParent is null for display:none; it can also be null for fixed-position elements,
    // so fall back to computed style for safety.
    if (el.offsetParent !== null) return false;
    try {
      const cs = window.getComputedStyle(el);
      return cs.display === "none" || cs.visibility === "hidden";
    } catch (e) {
      return true;
    }
  }

  function shouldInitSelect2(select) {
    if (!select || select.tagName !== "SELECT") return false;

    // Opt-outs
    const uiFlag = String(select.getAttribute("data-ui-select2") || "").trim();
    if (uiFlag === "0") return false;
    if (String(select.getAttribute("data-no-select2") || "") === "1") return false;
    if (select.classList.contains("no-select2")) return false;

    // PC busy screens use a custom product search grid; avoid Select2 inside the grid table.
    // (Top-strip selects like Warehouse/Payment can still be enhanced.)
    if (select.closest && select.closest(".busy-order-pc") && select.closest("#orderTable")) return false;

    // Hidden selects (Select2 measures width; init when visible instead).
    if (isHidden(select)) return false;

    return true;
  }

  function initOne(select) {
    const $el = jQuery(select);
    if ($el.data("select2")) return;

    const hasEmptyOption = $el.find("option[value='']").length > 0;
    const placeholder =
      (select.getAttribute("data-placeholder") || "").trim() ||
      (hasEmptyOption ? ($el.find("option[value='']").first().text() || "").trim() : "");

    // Always show the search box by default (user expects type-to-search everywhere).
    // You can override per-select via `data-select2-min-results="Infinity"` (or a number).
    const minResultsRaw = String(select.getAttribute("data-select2-min-results") || "").trim();
    const minResults =
      minResultsRaw !== ""
        ? minResultsRaw.toLowerCase() === "infinity"
          ? Infinity
          : Number.parseInt(minResultsRaw, 10)
        : 0;

      $el.select2({
        width: "100%",
        placeholder: placeholder || undefined,
        allowClear: hasEmptyOption,
        minimumResultsForSearch: Number.isFinite(minResults) ? minResults : 0,
      });
  }

  function initWithin(root) {
    if (!root) return;
    if (!window.jQuery || !jQuery.fn || !jQuery.fn.select2) return;

    const selects = [];
    if (root.tagName === "SELECT") selects.push(root);
    else if (root.querySelectorAll) selects.push(...root.querySelectorAll("select"));

    selects.forEach((select) => {
      if (!shouldInitSelect2(select)) return;
      initOne(select);
    });
  }

  onReady(function () {
    if (!window.jQuery || !jQuery.fn || !jQuery.fn.select2) return;

    // Backwards compatible: still supports explicit opt-in via data-ui-select2="1",
    // but defaults to enhancing all visible selects (unless opted out).
    initWithin(document);
    window.kpInitSelect2 = initWithin;

    // Bootstrap modals/offcanvas mount content hidden; initialize when shown.
    document.addEventListener("shown.bs.modal", (e) => initWithin(e.target));
    document.addEventListener("shown.bs.offcanvas", (e) => initWithin(e.target));

    // If a select becomes visible later (wizard steps, tabs, etc.), initialize on first interaction
    // and open Select2 immediately so the user still gets search on the first click.
    document.addEventListener(
      "mousedown",
      (e) => {
        const target = e.target;
        if (!target || target.tagName !== "SELECT") return;
        if (!shouldInitSelect2(target)) return;
        const $el = jQuery(target);
        if ($el.data("select2")) return;

        // Prevent native select opening; swap to Select2 and open.
        e.preventDefault();
        initOne(target);
        try {
          $el.select2("open");
        } catch (err) {}
      },
      true
    );

    // Enhance dynamically added selects (formsets, AJAX partials, etc.).
    try {
      const observer = new MutationObserver((mutations) => {
        for (const m of mutations) {
          for (const node of Array.from(m.addedNodes || [])) {
            if (!node || node.nodeType !== 1) continue;
            // Avoid loops: Select2 adds lots of markup; we only care about selects.
            if (node.tagName === "SELECT") initWithin(node);
            else if (node.querySelector && node.querySelector("select")) initWithin(node);
          }
        }
      });
      observer.observe(document.documentElement || document.body, { childList: true, subtree: true });
    } catch (e) {}
  });
})();
