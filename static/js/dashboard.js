/* ---------------------------------------------------------
   DASHBOARD JS (UI helpers)
--------------------------------------------------------- */
document.addEventListener("DOMContentLoaded", function () {
  // Close action menus when clicking outside
  document.addEventListener("click", function (e) {
    if (!e.target.closest(".action-card")) {
      document.querySelectorAll(".action-menu").forEach((menu) => {
        menu.style.display = "none";
      });
    }
  });

  initDashboardCardMiniToggles();
  initHighDueCardMenu();
  initPartyLedgerMoreDetails();
  initSmartLimitedTables();
});

function initSmartLimitedTables() {
  document.querySelectorAll("[data-limited-table-card]").forEach((card) => {
    const rows = Array.from(card.querySelectorAll("[data-limited-table-extra]"));
    const btn = card.querySelector("[data-limited-table-more]");
    const label = card.querySelector("[data-limited-table-more-label]");
    const icon = btn ? btn.querySelector("i") : null;
    if (!btn || !label) return;

    if (rows.length === 0) {
      btn.hidden = true;
      return;
    }

    function setExpanded(isExpanded) {
      rows.forEach((row) => {
        row.hidden = !isExpanded;
      });
      label.textContent = isExpanded ? "Show Less" : `More Details (${rows.length})`;
      if (icon) {
        icon.classList.toggle("bi-chevron-up", isExpanded);
        icon.classList.toggle("bi-list-ul", !isExpanded);
      }
    }

    setExpanded(false);

    btn.addEventListener("click", function () {
      const isExpanded = rows.some((row) => !row.hidden);
      setExpanded(!isExpanded);
    });
  });
}

function initPartyLedgerMoreDetails() {
  const card = document.querySelector("[data-party-ledger-card]");
  if (!card) return;

  const rows = Array.from(card.querySelectorAll("[data-party-ledger-extra]"));
  const btn = card.querySelector("[data-party-ledger-more]");
  const label = card.querySelector("[data-party-ledger-more-label]");
  const icon = btn ? btn.querySelector("i") : null;
  if (!btn || !label) return;

  if (rows.length === 0) {
    btn.hidden = true;
    return;
  }

  function setExpanded(isExpanded) {
    rows.forEach((row) => {
      row.hidden = !isExpanded;
    });
    label.textContent = isExpanded ? "Show Less" : `More Details (${rows.length})`;
    if (icon) {
      icon.classList.toggle("bi-chevron-up", isExpanded);
      icon.classList.toggle("bi-list-ul", !isExpanded);
    }
  }

  setExpanded(false);

  btn.addEventListener("click", function () {
    const isExpanded = rows.some((row) => !row.hidden);
    setExpanded(!isExpanded);
  });
}

function initHighDueCardMenu() {
  const card = document.querySelector("[data-high-due-card]");
  if (!card) return;

  const body = card.querySelector("[data-high-due-body]");
  const toggle = card.querySelector("[data-high-due-toggle]");
  const label = card.querySelector("[data-high-due-toggle-label]");
  const icon = toggle ? toggle.querySelector("i") : null;
  if (!body || !toggle || !label) return;

  const storageKey = "kp_dashboard_high_due_hidden";

  function readHidden() {
    try {
      return localStorage.getItem(storageKey) === "1";
    } catch (e) {
      return false;
    }
  }

  function writeHidden(isHidden) {
    try {
      localStorage.setItem(storageKey, isHidden ? "1" : "0");
    } catch (e) {}
  }

  function setHidden(isHidden) {
    body.style.display = isHidden ? "none" : "";
    label.textContent = isHidden ? "Show list" : "Hide list";
    if (icon) {
      icon.classList.toggle("bi-eye", isHidden);
      icon.classList.toggle("bi-eye-slash", !isHidden);
    }
    writeHidden(isHidden);
  }

  setHidden(readHidden());

  toggle.addEventListener("click", function () {
    setHidden(body.style.display !== "none");
  });
}

function initDashboardCardMiniToggles() {
  if (typeof window.jQuery === "undefined") return;

  const $ = window.jQuery;
  const STORAGE_PREFIX = "kp_dashboard_card_collapsed:";

  function normalizeText(text) {
    return String(text || "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function keyForTitle(title) {
    const slug = normalizeText(title)
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");
    return STORAGE_PREFIX + slug;
  }

  function readCollapsed(title) {
    try {
      return localStorage.getItem(keyForTitle(title)) === "1";
    } catch (e) {
      return false;
    }
  }

  function writeCollapsed(title, isCollapsed) {
    try {
      localStorage.setItem(keyForTitle(title), isCollapsed ? "1" : "0");
    } catch (e) {}
  }

  function createToggleButton() {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "kp-mini-toggle-btn";
    btn.setAttribute("aria-label", "Collapse/expand card");
    btn.setAttribute("aria-expanded", "true");
    btn.innerHTML = '<i class="bi bi-chevron-up" aria-hidden="true"></i>';
    return btn;
  }

  function setButtonState(btn, isCollapsed) {
    btn.setAttribute("aria-expanded", String(!isCollapsed));
    const icon = btn.querySelector("i");
    if (!icon) return;
    icon.classList.toggle("bi-chevron-up", !isCollapsed);
    icon.classList.toggle("bi-chevron-down", isCollapsed);
  }

  function ensureRightActionsWrap(headerEl) {
    const children = Array.from(headerEl.children);
    const left = children[0] || null;
    const rightExisting = children.slice(1);

    const existingWrap = Array.from(headerEl.querySelectorAll(".kp-card-header-actions")).find(
      (el) => el.parentElement === headerEl
    );
    if (existingWrap) return existingWrap;

    const wrap = document.createElement("div");
    wrap.className = "kp-card-header-actions";
    rightExisting.forEach((node) => wrap.appendChild(node));
    if (left) headerEl.appendChild(wrap);
    else headerEl.appendChild(wrap);
    return wrap;
  }

  function setupCard({ title, header, bodyEls, actionsContainer }) {
    if (!header || !bodyEls || bodyEls.length === 0) return;
    if (header.querySelector(".kp-mini-toggle-btn")) return;

    const btn = createToggleButton();
    const actions = actionsContainer || ensureRightActionsWrap(header);
    actions.appendChild(btn);

    const collapsedInitially = readCollapsed(title);
    if (collapsedInitially) $(bodyEls).hide();
    setButtonState(btn, collapsedInitially);

    btn.addEventListener("click", function () {
      const isExpanded = bodyEls.some((el) => $(el).is(":visible"));
      const nextCollapsed = isExpanded;

      if (nextCollapsed) $(bodyEls).stop(true, true).slideUp(180);
      else $(bodyEls).stop(true, true).slideDown(180);

      setButtonState(btn, nextCollapsed);
      writeCollapsed(title, nextCollapsed);
    });
  }

  function findSmartCardByTitle(expectedTitle) {
    const expected = normalizeText(expectedTitle);
    const cards = Array.from(document.querySelectorAll(".smart-card"));
    return cards.filter((card) => {
      const h3 = card.querySelector(".smart-card-header h3");
      return h3 && normalizeText(h3.textContent) === expected;
    });
  }

  findSmartCardByTitle("Quick Centers").forEach((card) => {
    setupCard({
      title: "Quick Centers",
      header: card.querySelector(".smart-card-header"),
      bodyEls: Array.from(card.querySelectorAll(".quick-slider")),
    });
  });

  findSmartCardByTitle("Premium Services").forEach((card) => {
    setupCard({
      title: "Premium Services",
      header: card.querySelector(".smart-card-header"),
      bodyEls: Array.from(card.querySelectorAll(".quick-slider")),
    });
  });

  findSmartCardByTitle("Party Ledger Summary").forEach((card) => {
    setupCard({
      title: "Party Ledger Summary",
      header: card.querySelector(".smart-card-header"),
      bodyEls: Array.from(card.querySelectorAll(".smart-table-wrap")),
    });
  });

  findSmartCardByTitle("Commerce").forEach((card) => {
    const bodies = [
      ...Array.from(card.querySelectorAll("#commerceQuickActionsSlider")),
      ...Array.from(card.querySelectorAll(".smart-action-grid")),
      ...Array.from(card.querySelectorAll(".action-card")),
      ...Array.from(card.querySelectorAll(".col-md-4")),
    ];

    setupCard({
      title: "Commerce",
      header: card.querySelector(".smart-card-header"),
      bodyEls: bodies,
    });
  });

  document.querySelectorAll(".ai-reorder-wrap").forEach((wrap) => {
    const titleEl = wrap.querySelector(".ai-title");
    if (!titleEl || normalizeText(titleEl.textContent) !== "ai reorder planner") return;

    setupCard({
      title: "Planner",
      header: wrap.querySelector(".ai-reorder-header"),
      actionsContainer: wrap.querySelector(".ai-actions"),
      bodyEls: [
        ...Array.from(wrap.querySelectorAll(".ai-cards-grid")),
        ...Array.from(wrap.querySelectorAll(".ai-slider")),
      ],
    });
  });

  document.querySelectorAll(".wa-dashboard-wrap").forEach((wrap) => {
    const titleEl = wrap.querySelector(".wa-dashboard-header h3");
    if (!titleEl || normalizeText(titleEl.textContent) !== "whatsapp orders") return;

    setupCard({
      title: "WhatsApp Orders",
      header: wrap.querySelector(".wa-dashboard-header"),
      bodyEls: [
        ...Array.from(wrap.querySelectorAll(".wa-cards-grid")),
        ...Array.from(wrap.querySelectorAll(".wa-slider")),
        ...Array.from(wrap.querySelectorAll(".wa-order-list")),
      ],
    });
  });

  document.querySelectorAll(".loyalty-wrap").forEach((wrap) => {
    setupCard({
      title: "Loyalty Scratch Membership",
      header: wrap.querySelector(".loyalty-header"),
      bodyEls: Array.from(wrap.querySelectorAll(".loyalty-grid")),
    });
  });
}

/* ---------------------------------------------------------
   TODAY SUMMARY – MORE DETAILS TOGGLE
   (Called from onclick="")
--------------------------------------------------------- */
window.toggleSummaryDetails = function () {
  const box = document.getElementById("summaryDetails");
  if (!box) return;

  const willShow = box.style.display === "none" || box.style.display === "";
  box.style.display = willShow ? "block" : "none";

  const label = document.querySelector("[data-summary-details-label]");
  const icon = label ? label.closest("button")?.querySelector("i") : null;
  if (label) label.textContent = willShow ? "Show Less" : "More Details";
  if (icon) {
    icon.classList.toggle("bi-chevron-up", willShow);
    icon.classList.toggle("bi-list-ul", !willShow);
  }
};

/* ---------------------------------------------------------
   ACTION CARD DROPDOWN (⋮ MENU)
   (Commerce / Accounts / Billing etc.)
--------------------------------------------------------- */
window.toggleActionMenu = function (id) {
  const menu = document.getElementById(id);
  if (!menu) return;

  document.querySelectorAll(".action-menu").forEach((el) => {
    if (el !== menu) el.style.display = "none";
  });

  menu.style.display = menu.style.display === "block" ? "none" : "block";
};
