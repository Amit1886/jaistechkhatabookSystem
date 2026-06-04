(function () {
  const REPORT_PATH_RE = /\/reports\//;
  const LIVE_MS = 12000;
  const ROOT_SELECTOR = ".unified-report-card,.unified-list-card,.pc-universal-shell > .card,.card";
  const ACTION_HTML = `
    <span class="smart-report-live-pill" data-smart-report-status>
      <span class="smart-report-live-dot"></span>
      <span data-smart-report-status-text>Live</span>
    </span>
    <button type="button" class="btn unified-btn-outline" data-smart-report-act="print">Print</button>
    <button type="button" class="btn unified-btn-outline" data-smart-report-act="excel">Excel</button>
    <button type="button" class="btn unified-btn-outline" data-smart-report-act="pdf">PDF</button>
    <button type="button" class="btn unified-btn-outline" data-smart-report-act="share">Share</button>
  `;

  function isReportPage() {
    return REPORT_PATH_RE.test(window.location.pathname) || document.querySelector(".unified-report-screen,.unified-list-screen");
  }

  function notify(message, type) {
    window.dispatchEvent(new CustomEvent("ui:toast", { detail: { message, type: type || "info" } }));
  }

  function csvEscape(value) {
    const text = String(value == null ? "" : value).replace(/\s+/g, " ").trim();
    if (/[",\n]/.test(text)) return '"' + text.replaceAll('"', '""') + '"';
    return text;
  }

  function reportTitle(root) {
    const h = root.querySelector("h1,h2,h3,h4");
    return (h ? h.innerText : document.title || "report").trim();
  }

  function safeFilename(name) {
    return name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || "report";
  }

  function getRoot() {
    return document.querySelector(".unified-report-card,.unified-list-card") || document.querySelector(".pc-universal-shell > .card,.card");
  }

  function tableToCsv(root) {
    const tables = Array.from(root.querySelectorAll("table"));
    const rows = [];
    tables.forEach(function (table, tableIndex) {
      if (tableIndex) rows.push("");
      Array.from(table.querySelectorAll("tr")).forEach(function (tr) {
        if (tr.offsetParent === null) return;
        const cells = Array.from(tr.querySelectorAll("th,td")).map(function (cell) {
          return csvEscape(cell.innerText);
        });
        if (cells.length) rows.push(cells.join(","));
      });
    });
    return rows.join("\n");
  }

  function download(filename, text, type) {
    const blob = new Blob([text], { type: type || "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(function () { URL.revokeObjectURL(url); }, 1200);
  }

  function professionalPrint(root, saveAsPdf) {
    const title = reportTitle(root);
    const generatedAt = new Date().toLocaleString();
    const url = window.location.href;
    const styles = Array.from(document.querySelectorAll('link[rel="stylesheet"],style'))
      .map(function (node) { return node.outerHTML; })
      .join("\n");
    const clone = root.cloneNode(true);
    clone.querySelectorAll(".smart-report-actions,.smart-report-live-pill,.doc-action-bar,.no-print,button,.btn,.dropdown-menu").forEach(function (el) {
      el.remove();
    });
    const html = `
      <!doctype html>
      <html>
      <head>
        <meta charset="utf-8">
        <title>${title}</title>
        ${styles}
        <style>
          body{font-family:Arial,sans-serif;background:#fff;color:#111827;padding:18px}
          .smart-print-head{display:flex;justify-content:space-between;gap:16px;border-bottom:2px solid #111827;padding-bottom:10px;margin-bottom:14px}
          .smart-print-head h1{font-size:20px;margin:0}
          .smart-print-meta{font-size:11px;color:#475569;text-align:right;line-height:1.5}
          table{width:100%;border-collapse:collapse}
          th,td{border:1px solid #d7dee9;padding:7px;font-size:11px}
          th{background:#edf2f7;color:#0f172a}
          .card,.unified-report-card,.unified-list-card{box-shadow:none!important;border:0!important}
        </style>
      </head>
      <body>
        <div class="smart-print-head">
          <div>
            <h1>${title}</h1>
            <div>Enterprise Business OS Report</div>
          </div>
          <div class="smart-print-meta">
            Generated: ${generatedAt}<br>
            Source: ${url}
          </div>
        </div>
        ${clone.outerHTML}
      </body>
      </html>`;
    const win = window.open("", "_blank");
    if (!win) {
      notify("Popup blocked. Please allow popup for print.", "warning");
      return;
    }
    win.document.open();
    win.document.write(html);
    win.document.close();
    win.focus();
    window.setTimeout(function () {
      win.print();
      if (!saveAsPdf) win.close();
    }, 300);
  }

  function ensureActions(root) {
    if (!root || root.dataset.smartReportReady === "1") return;
    root.dataset.smartReportReady = "1";

    const header = root.querySelector(".unified-report-header,.unified-list-header,.card-header") || root;
    let actionBox = header.querySelector(".smart-report-actions");
    if (!actionBox) {
      actionBox = document.createElement("div");
      actionBox.className = "smart-report-actions";
      actionBox.setAttribute("data-smart-report-actions", "");
      actionBox.innerHTML = ACTION_HTML;
      header.appendChild(actionBox);
    } else if (!actionBox.querySelector("[data-smart-report-status]")) {
      actionBox.insertAdjacentHTML("afterbegin", ACTION_HTML);
    }

    const body = root.querySelector(".unified-report-body,.unified-list-body,.card-body");
    if (body && body.querySelector("table") && !body.querySelector("[data-smart-quick-search]") && !body.querySelector("[data-master-search]")) {
      const bar = document.createElement("div");
      bar.className = "smart-report-quickbar";
      bar.innerHTML = '<div><label class="unified-label">Quick Search</label><input type="text" class="form-control" data-smart-quick-search placeholder="Search this report"></div>';
      body.insertBefore(bar, body.querySelector(".unified-table-wrap,.table-responsive,table"));
    }

    root.querySelectorAll("table").forEach(function (table) {
      if (!table.hasAttribute("data-smart-table")) table.setAttribute("data-smart-table", "");
    });
  }

  function setStatus(text, refreshing) {
    document.querySelectorAll("[data-smart-report-status]").forEach(function (el) {
      el.classList.toggle("is-refreshing", !!refreshing);
      const textEl = el.querySelector("[data-smart-report-status-text]");
      if (textEl) textEl.textContent = text;
    });
  }

  function applyQuickFilters(root) {
    const qEls = Array.from(root.querySelectorAll("[data-smart-quick-search],[data-master-search]"));
    const filterEls = Array.from(root.querySelectorAll("[data-master-filter]"));
    const query = qEls.map(function (el) { return (el.value || "").toLowerCase().trim(); }).filter(Boolean).join(" ");
    root.querySelectorAll("table").forEach(function (table) {
      const rows = Array.from(table.querySelectorAll("tbody tr"));
      rows.forEach(function (tr) {
        let visible = true;
        const text = tr.innerText.toLowerCase();
        if (query && !text.includes(query)) visible = false;
        filterEls.forEach(function (filterEl) {
          const val = (filterEl.value || "").toLowerCase().trim();
          if (!val) return;
          const idx = Number(filterEl.getAttribute("data-master-filter"));
          const cell = tr.children[idx];
          if (cell && !cell.innerText.toLowerCase().includes(val)) visible = false;
        });
        tr.style.display = visible ? "" : "none";
      });
    });
  }

  async function shareReport(root) {
    const title = reportTitle(root);
    const text = title + " - " + window.location.href;
    if (navigator.share) {
      try {
        await navigator.share({ title, text, url: window.location.href });
        return;
      } catch (err) {
        return;
      }
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      notify("Report link copied.", "success");
    } else {
      window.prompt("Copy report link:", text);
    }
  }

  async function refreshReport() {
    const root = getRoot();
    if (!root || document.hidden) return;
    const active = document.activeElement;
    if (active && root.contains(active) && /^(INPUT|SELECT|TEXTAREA)$/.test(active.tagName)) return;
    try {
      setStatus("Syncing", true);
      const response = await fetch(window.location.href, {
        headers: { "X-Requested-With": "XMLHttpRequest", "X-Smart-Report": "1" },
        credentials: "same-origin"
      });
      if (!response.ok) throw new Error("Report refresh failed");
      const html = await response.text();
      const doc = new DOMParser().parseFromString(html, "text/html");
      const freshRoot = doc.querySelector(".unified-report-card,.unified-list-card") || doc.querySelector(".pc-universal-shell > .card,.card");
      if (!freshRoot) throw new Error("Report root missing");
      root.innerHTML = freshRoot.innerHTML;
      root.dataset.smartReportReady = "";
      init();
      setStatus("Live", false);
    } catch (err) {
      setStatus("Offline", false);
    }
  }

  function init() {
    if (!isReportPage()) return;
    const root = getRoot();
    if (!root) return;
    ensureActions(root);
    applyQuickFilters(root);
  }

  window.SmartReports = {
    print: function () {
      const root = getRoot();
      if (root) professionalPrint(root, false);
    },
    pdf: function () {
      const root = getRoot();
      if (root) professionalPrint(root, true);
    },
    excel: function () {
      const root = getRoot();
      if (root) download(safeFilename(reportTitle(root)) + ".csv", tableToCsv(root), "text/csv;charset=utf-8");
    },
    share: function () {
      const root = getRoot();
      if (root) shareReport(root);
    },
    refresh: refreshReport
  };

  document.addEventListener("click", function (event) {
    const btn = event.target.closest("[data-smart-report-act]");
    if (!btn) return;
    const root = getRoot();
    if (!root) return;
    const action = btn.getAttribute("data-smart-report-act");
    if (action === "print") professionalPrint(root, false);
    if (action === "pdf") professionalPrint(root, true);
    if (action === "excel") download(safeFilename(reportTitle(root)) + ".csv", tableToCsv(root), "text/csv;charset=utf-8");
    if (action === "share") shareReport(root);
  });

  document.addEventListener("click", function (event) {
    const btn = event.target.closest("[data-export]");
    if (!btn || !isReportPage()) return;
    const root = getRoot();
    if (!root) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const action = btn.getAttribute("data-export");
    if (action === "print") professionalPrint(root, false);
    if (action === "pdf") professionalPrint(root, true);
    if (action === "excel" || action === "csv") {
      download(safeFilename(btn.getAttribute("data-export-name") || reportTitle(root)) + ".csv", tableToCsv(root), "text/csv;charset=utf-8");
    }
    if (action === "share") shareReport(root);
  }, true);

  document.addEventListener("input", function (event) {
    if (event.target.matches("[data-smart-quick-search],[data-master-search]")) {
      const root = getRoot();
      if (root) applyQuickFilters(root);
    }
  });

  document.addEventListener("change", function (event) {
    if (event.target.matches("[data-master-filter]")) {
      const root = getRoot();
      if (root) applyQuickFilters(root);
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    init();
    if (isReportPage()) window.setInterval(refreshReport, LIVE_MS);
  });
})();
