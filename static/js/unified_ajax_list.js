(function () {
  function onReady(fn) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn);
    else fn();
  }

  function debounce(fn, ms) {
    let t = null;
    return function () {
      const args = arguments;
      window.clearTimeout(t);
      t = window.setTimeout(function () {
        fn.apply(null, args);
      }, ms);
    };
  }

  function buildParams(form) {
    const data = new FormData(form);
    const params = new URLSearchParams();
    for (const [k, v] of data.entries()) {
      const value = String(v ?? "").trim();
      if (!value) continue;
      params.append(k, value);
    }
    return params;
  }

  function setPageValue(form, page) {
    let pageInput = form.querySelector('input[name="page"]');
    if (!pageInput) {
      pageInput = document.createElement("input");
      pageInput.type = "hidden";
      pageInput.name = "page";
      form.appendChild(pageInput);
    }
    pageInput.value = String(page);
  }

  onReady(function () {
    document.querySelectorAll("[data-ajax-list-wrap]").forEach(function (wrap) {
      const form = wrap.querySelector("[data-ajax-form]");
      const tbody = wrap.querySelector("[data-ajax-tbody]");
      const pagination = wrap.querySelector("[data-ajax-pagination]");
      const summary = wrap.querySelector("[data-ajax-summary]");

      if (!form || !tbody) return;

      const baseUrl = wrap.getAttribute("data-ajax-url") || window.location.pathname;
      const loadingEl = wrap.querySelector("[data-ajax-loading]");

      function setLoading(isLoading) {
        if (!loadingEl) return;
        loadingEl.style.display = isLoading ? "" : "none";
      }

      async function fetchAndRender() {
        const params = buildParams(form);
        params.set("ajax", "1");

        const url = baseUrl + "?" + params.toString();
        setLoading(true);
        try {
          const res = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
          if (!res.ok) throw new Error("Bad response");
          const payload = await res.json();
          if (typeof payload.rows_html === "string") tbody.innerHTML = payload.rows_html;
          if (pagination && typeof payload.pagination_html === "string") pagination.innerHTML = payload.pagination_html;
          if (summary && typeof payload.summary_html === "string") summary.innerHTML = payload.summary_html;
          window.history.replaceState({}, "", baseUrl + "?" + params.toString().replace("ajax=1&", "").replace("&ajax=1", "").replace("ajax=1", ""));
        } catch (e) {
          // no-op (keep current UI)
        } finally {
          setLoading(false);
        }
      }

      const debouncedFetch = debounce(function () {
        setPageValue(form, 1);
        fetchAndRender();
      }, 180);

      form.addEventListener("submit", function (e) {
        e.preventDefault();
        setPageValue(form, 1);
        fetchAndRender();
      });

      form.querySelectorAll("input,select,textarea").forEach(function (el) {
        if (el.name === "page") return;
        el.addEventListener("input", debouncedFetch);
        el.addEventListener("change", debouncedFetch);
      });

      wrap.addEventListener("click", function (e) {
        const btn = e.target.closest("[data-page]");
        if (!btn) return;
        const page = btn.getAttribute("data-page");
        if (!page) return;
        setPageValue(form, page);
        fetchAndRender();
      });

      const resetBtn = wrap.querySelector("[data-ajax-reset]");
      if (resetBtn) {
        resetBtn.addEventListener("click", function () {
          form.querySelectorAll("input,select,textarea").forEach(function (el) {
            if (!el.name) return;
            if (el.type === "hidden" && el.name === "page") {
              el.value = "";
              return;
            }
            if (el.tagName === "SELECT") el.value = "";
            else el.value = "";
          });
          setPageValue(form, 1);
          fetchAndRender();
        });
      }
    });
  });
})();

