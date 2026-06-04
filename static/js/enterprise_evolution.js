(function () {
  "use strict";

  const STORAGE_THEME = "kp_enterprise_theme";
  const MAX_COMMANDS = 90;

  function $(selector, root) {
    return (root || document).querySelector(selector);
  }

  function all(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  }

  function textOf(node) {
    return String(node && node.textContent ? node.textContent : "").replace(/\s+/g, " ").trim();
  }

  function icon(name) {
    return '<i class="bi bi-' + name + '" aria-hidden="true"></i>';
  }

  function applySavedTheme() {
    try {
      if (localStorage.getItem(STORAGE_THEME) === "dark") {
        document.body.classList.add("ee-dark");
      }
    } catch (e) {}
  }

  function toggleTheme() {
    const isDark = document.body.classList.toggle("ee-dark");
    try {
      localStorage.setItem(STORAGE_THEME, isDark ? "dark" : "light");
    } catch (e) {}
    window.dispatchEvent(
      new CustomEvent("ui:toast", {
        detail: { type: "info", message: isDark ? "Dark mode enabled" : "Light mode enabled", ms: 1600 },
      })
    );
  }

  function getCommands() {
    const seen = new Set();
    const commands = [];
    const selectors = [
      ".dashboard-actions a[href]",
      ".quick-slider a[href]",
      ".smart-card a[href]",
      ".sidebar a[href]",
      ".topbar a[href]",
    ];

    all(selectors.join(",")).forEach((link) => {
      const href = link.getAttribute("href");
      const label = textOf(link);
      if (!href || href === "#" || !label) return;
      const key = href + "::" + label.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);

      let area = "Dashboard";
      if (link.closest(".sidebar")) area = "Navigation";
      if (link.closest(".dashboard-actions")) area = "Quick Action";
      if (link.closest(".quick-slider")) area = "Quick Center";
      commands.push({ label, href, area });
    });

    return commands.slice(0, MAX_COMMANDS);
  }

  function buildCommandPalette() {
    if ($("#eeCommandBackdrop")) return;

    const backdrop = document.createElement("div");
    backdrop.id = "eeCommandBackdrop";
    backdrop.className = "ee-command-backdrop";
    backdrop.innerHTML = [
      '<div class="ee-command-palette" role="dialog" aria-modal="true" aria-label="Command palette">',
      '  <div class="ee-command-search">',
      icon("search"),
      '    <input id="eeCommandInput" type="search" autocomplete="off" placeholder="Search actions, modules, reports">',
      '    <button type="button" class="ee-shell-button" data-ee-close-command aria-label="Close command palette">',
      icon("x"),
      "    </button>",
      "  </div>",
      '  <div class="ee-command-results" id="eeCommandResults"></div>',
      "</div>",
    ].join("");
    document.body.appendChild(backdrop);

    backdrop.addEventListener("click", function (event) {
      if (event.target === backdrop || event.target.closest("[data-ee-close-command]")) closeCommandPalette();
    });

    $("#eeCommandInput", backdrop).addEventListener("input", renderCommandResults);
  }

  function renderCommandResults() {
    const input = $("#eeCommandInput");
    const results = $("#eeCommandResults");
    if (!input || !results) return;

    const query = input.value.toLowerCase().trim();
    const commands = getCommands().filter((item) => {
      if (!query) return true;
      return (item.label + " " + item.area).toLowerCase().includes(query);
    });

    if (!commands.length) {
      results.innerHTML = '<div class="ee-panel-card"><strong>No results</strong><p>Try a module, report, customer, order, or settings keyword.</p></div>';
      return;
    }

    results.innerHTML = commands
      .slice(0, 30)
      .map(function (item, index) {
        return [
          '<a class="ee-command-item' + (index === 0 ? " is-active" : "") + '" href="' + item.href + '">',
          "  <span>" + item.label + "</span>",
          "  <small>" + item.area + "</small>",
          "</a>",
        ].join("");
      })
      .join("");
  }

  function openCommandPalette() {
    buildCommandPalette();
    const backdrop = $("#eeCommandBackdrop");
    const input = $("#eeCommandInput");
    if (!backdrop || !input) return;
    backdrop.classList.add("is-open");
    input.value = "";
    renderCommandResults();
    window.setTimeout(function () {
      input.focus();
    }, 30);
  }

  function closeCommandPalette() {
    const backdrop = $("#eeCommandBackdrop");
    if (backdrop) backdrop.classList.remove("is-open");
  }

  function buildAssistantPanel() {
    if ($("#eeSidePanel")) return;

    const panel = document.createElement("aside");
    panel.id = "eeSidePanel";
    panel.className = "ee-side-panel";
    panel.setAttribute("aria-label", "Smart assistant panel");
    panel.innerHTML = [
      '<div class="ee-panel-header">',
      "  <div>",
      "    <h3>Smart Assistant</h3>",
      '    <div class="muted-text" style="font-size:12px;">Contextual shortcuts for this workspace</div>',
      "  </div>",
      '  <button type="button" class="ee-shell-button" data-ee-close-panel aria-label="Close assistant panel">',
      icon("x"),
      "  </button>",
      "</div>",
      '<div class="ee-panel-body">',
      '  <div class="ee-panel-card"><strong>Find anything faster</strong><p>Use the command palette to jump across existing modules without changing your workflow.</p></div>',
      '  <div class="ee-panel-card"><strong>Today focus</strong><p>Review unpaid invoices, recent orders, low stock, and customer activity from the dashboard cards already available.</p></div>',
      '  <div class="ee-panel-card"><strong>Keyboard flow</strong><p>Press Ctrl+K for universal search. Press Esc to close panels.</p></div>',
      '  <div class="ee-panel-actions" id="eePanelActions"></div>',
      "</div>",
    ].join("");

    const backdrop = document.createElement("div");
    backdrop.id = "eePanelBackdrop";
    backdrop.className = "ee-panel-backdrop";
    document.body.appendChild(backdrop);
    document.body.appendChild(panel);

    panel.addEventListener("click", function (event) {
      if (event.target.closest("[data-ee-close-panel]")) closeAssistantPanel();
    });
    backdrop.addEventListener("click", closeAssistantPanel);

    const actions = $("#eePanelActions", panel);
    getCommands()
      .filter((item) => ["Add Transaction", "Add Order", "Add Product", "Settings"].some((label) => item.label.includes(label)))
      .slice(0, 4)
      .forEach((item) => {
        const link = document.createElement("a");
        link.href = item.href;
        link.textContent = item.label;
        actions.appendChild(link);
      });
  }

  function openAssistantPanel() {
    buildAssistantPanel();
    $("#eeSidePanel").classList.add("is-open");
    $("#eePanelBackdrop").classList.add("is-open");
  }

  function closeAssistantPanel() {
    const panel = $("#eeSidePanel");
    const backdrop = $("#eePanelBackdrop");
    if (panel) panel.classList.remove("is-open");
    if (backdrop) backdrop.classList.remove("is-open");
  }

  function buildUtilityDock() {
    if ($("#eeUtilityDock")) return;

    const dock = document.createElement("div");
    dock.id = "eeUtilityDock";
    dock.className = "ee-utility-dock";
    dock.innerHTML = [
      '<button type="button" class="ee-shell-button" data-ee-command title="Command palette" aria-label="Open command palette">',
      icon("search"),
      "</button>",
      '<button type="button" class="ee-shell-button" data-ee-panel title="Smart assistant" aria-label="Open smart assistant">',
      icon("stars"),
      "</button>",
      '<button type="button" class="ee-shell-button" data-ee-theme title="Toggle theme" aria-label="Toggle dark mode">',
      icon("moon-stars"),
      "</button>",
    ].join("");
    document.body.appendChild(dock);

    dock.addEventListener("click", function (event) {
      if (event.target.closest("[data-ee-command]")) openCommandPalette();
      if (event.target.closest("[data-ee-panel]")) openAssistantPanel();
      if (event.target.closest("[data-ee-theme]")) toggleTheme();
    });
  }

  function enhanceKeyboardFlow() {
    document.addEventListener("keydown", function (event) {
      const key = event.key.toLowerCase();
      const isTyping = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement && document.activeElement.tagName);
      if ((event.ctrlKey || event.metaKey) && key === "k") {
        event.preventDefault();
        openCommandPalette();
      }
      if (event.key === "Escape" && !isTyping) {
        closeCommandPalette();
        closeAssistantPanel();
      }
    });
  }

  function init() {
    applySavedTheme();
    buildUtilityDock();
    enhanceKeyboardFlow();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
