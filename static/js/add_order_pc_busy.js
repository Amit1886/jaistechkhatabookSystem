(() => {
  "use strict";

  const MIN_SEARCH_CHARS = 1;
  const MAX_DROPDOWN_RESULTS = 50;
  const ZOOM_STORAGE_KEY = "add_order_pc_zoom";
  const FULLWIDTH_STORAGE_KEY = "add_order_pc_full_width";
  const PARTY_MIN_SEARCH_CHARS = 1;
  const SUNDRY_STORAGE_KEY = "add_order_pc_bill_sundry_v1";

  let rowTemplate = null;
  const stockCache = new Map();
  let billSundryLines = [];
  let smartKhataCreditSeq = 0;

  function isPcBusyMode() {
    return (
      document.body.classList.contains("mode-pc") &&
      document.querySelector(".busy-order-pc")
    );
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function parseMoney(value) {
    const number = Number.parseFloat(String(value ?? "").replace(/[^0-9.-]/g, ""));
    return Number.isFinite(number) ? number : 0;
  }

  function clampNumber(value, min, max) {
    if (!Number.isFinite(value)) return min;
    return Math.max(min, Math.min(max, value));
  }

  function getMainOrderCard() {
    return document.getElementById("mainOrderCard");
  }

  function getPcWrapper() {
    return document.querySelector(".busy-order-pc");
  }

  function getStoredInt(key, fallback) {
    const raw = localStorage.getItem(key);
    const parsed = Number.parseInt(raw ?? "", 10);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function applyZoom(percent) {
    const card = getMainOrderCard();
    if (!card) return;

    const safePercent = clampNumber(percent, 80, 130);
    const scale = safePercent / 100;
    card.style.zoom = String(scale);
    card.dataset.zoom = String(safePercent);

    localStorage.setItem(ZOOM_STORAGE_KEY, String(safePercent));

    const range = document.getElementById("pcZoomRange");
    if (range && range.value !== String(safePercent)) range.value = String(safePercent);

    const label = document.getElementById("pcZoomValue");
    if (label) label.textContent = `${safePercent}%`;

    // When zoom changes, row height changes; re-fill blank rows for the viewport.
    queueEnsureRowsFillViewport();
  }

  function adjustZoom(delta) {
    const card = getMainOrderCard();
    const current =
      clampNumber(
        Number.parseInt(card?.dataset?.zoom || "", 10) || getStoredInt(ZOOM_STORAGE_KEY, 100),
        80,
        130
      );
    applyZoom(current + delta);
  }

  function applyFullWidth(enabled) {
    const wrapper = getPcWrapper();
    if (!wrapper) return;

    wrapper.classList.toggle("busy-full-width", enabled);
    localStorage.setItem(FULLWIDTH_STORAGE_KEY, enabled ? "1" : "0");

    const cb = document.getElementById("pcFullWidth");
    if (cb) cb.checked = enabled;
  }

  function focusFirstVisible(selector) {
    const elements = Array.from(document.querySelectorAll(selector));
    const element = elements.find((el) => el && el.offsetParent !== null) || elements[0];
    if (element) element.focus();
  }

  function keepSingleElementById(id) {
    const scope = getMainOrderCard() || document;
    const safe = typeof CSS !== "undefined" && CSS.escape ? CSS.escape(id) : id;
    const nodes = Array.from(scope.querySelectorAll(`#${safe}`));
    if (nodes.length <= 1) return nodes[0] || null;

    const keep = nodes.find((n) => n && n.offsetParent !== null) || nodes[0];
    nodes.forEach((n) => {
      if (n !== keep) n.remove();
    });
    return keep;
  }

  function collectProductsFromDom() {
    const firstSelect = document.querySelector("#orderBody .item-row .product");
    if (!firstSelect) return [];

    return Array.from(firstSelect.querySelectorAll("option"))
      .filter((opt) => opt.value)
      .map((opt) => ({
        id: opt.value,
        name: opt.textContent?.trim() || "",
        nameLower: (opt.textContent || "").toLowerCase(),
        price: parseMoney(opt.dataset.price),
        barcode: (opt.dataset.barcode || "").trim(),
        unit: (opt.dataset.unit || "").trim(),
        stock: parseMoney(opt.dataset.stock),
      }));
  }

  function collectPartiesFromDom() {
    const select = document.getElementById("partySelect");
    if (!select) return [];

    return Array.from(select.querySelectorAll("option"))
      .filter((opt) => opt.value)
      .map((opt) => ({
        id: opt.value,
        name: (opt.textContent || "").trim(),
        nameLower: (opt.textContent || "").toLowerCase(),
      }));
  }

  function ensureSingleRowControls(row) {
    // Ensure S.No. + Unit columns exist (PC Busy only).
    if (!row.querySelector("td.pc-sno")) {
      const productCell =
        row.querySelector(".product-search")?.closest("td") ||
        row.querySelector("select.product")?.closest("td");
      if (productCell) {
        const sno = document.createElement("td");
        sno.className = "pc-sno text-center";
        sno.innerHTML = `<span class="pc-sno-text"></span>`;
        productCell.parentNode.insertBefore(sno, productCell);
      }
    }

    if (!row.querySelector(".unit")) {
      const qtyCell = row.querySelector(".qty")?.closest("td");
      if (qtyCell) {
        const unitCell = document.createElement("td");
        unitCell.className = "pc-unit";
        unitCell.innerHTML = `<input type="text" class="form-control unit text-center fw-bold" readonly tabindex="-1" aria-label="Unit" />`;
        qtyCell.parentNode.insertBefore(unitCell, qtyCell.nextSibling);
      }
    }

    const productSearchInputs = row.querySelectorAll(".product-search");
    productSearchInputs.forEach((el, idx) => {
      if (idx > 0) el.remove();
    });

    const removeButtons = row.querySelectorAll(".remove-btn");
    removeButtons.forEach((el, idx) => {
      if (idx > 0) el.remove();
    });

    const removeButton = row.querySelector(".remove-btn");
    if (removeButton) removeButton.textContent = "×";
    if (removeButton) removeButton.tabIndex = -1;

    const dropdown = row.querySelector(".product-dropdown");
    if (!dropdown) {
      const productCell =
        row.querySelector(".product-search")?.closest("td") ||
        row.querySelector("select.product")?.closest("td");
      if (productCell) {
        const newDd = document.createElement("div");
        newDd.className = "product-dropdown busy-dd dropdown-menu";
        productCell.appendChild(newDd);
      }
    } else {
      dropdown.classList.add("busy-dd");
    }

    // Ensure discount hidden fields exist (backend ignores safely).
    const amountCell = row.querySelector(".amount")?.closest("td") || row.querySelector("td:last-child");
    if (amountCell) {
      if (!row.querySelector("input.discount_percent")) {
        const dp = document.createElement("input");
        dp.type = "hidden";
        dp.className = "discount_percent";
        dp.name = "discount_percent[]";
        dp.value = "0";
        amountCell.appendChild(dp);
      }
      if (!row.querySelector("input.discount_amount")) {
        const da = document.createElement("input");
        da.type = "hidden";
        da.className = "discount_amount";
        da.name = "discount_amount[]";
        da.value = "0";
        amountCell.appendChild(da);
      }
    }

    const amountInput = row.querySelector(".amount");
    if (amountInput) {
      amountInput.readOnly = false;
      amountInput.removeAttribute("readonly");
    }
  }

  function clearRow(row) {
    const productSearch = row.querySelector(".product-search");
    const select = row.querySelector(".product");
    const qty = row.querySelector(".qty");
    const unit = row.querySelector(".unit");
    const price = row.querySelector(".price");
    const amount = row.querySelector(".amount");
    const dp = row.querySelector("input.discount_percent");
    const da = row.querySelector("input.discount_amount");

    if (productSearch) productSearch.value = "";
    if (select) select.value = "";
    if (qty) qty.value = "1";
    if (unit) unit.value = "";
    if (price) price.value = "";
    if (amount) amount.value = "";
    if (dp) dp.value = "0";
    if (da) da.value = "0";

    const dropdown = row.querySelector(".product-dropdown");
    if (dropdown) dropdown.style.display = "none";
  }

  function ensureRowTemplate() {
    if (rowTemplate) return;

    const tbody = document.getElementById("orderBody");
    if (!tbody) return;
    const firstRow = tbody.querySelector("tr.item-row");
    if (!firstRow) return;

    ensureSingleRowControls(firstRow);

    rowTemplate = firstRow.cloneNode(true);
    ensureSingleRowControls(rowTemplate);
    clearRow(rowTemplate);

    // Clear first row for initial entry (do this only once), but do not wipe prefilled rows
    // (e.g., quotation -> order conversion / edit flows).
    const firstSelectValue = firstRow.querySelector(".product")?.value || "";
    const firstSearchValue = firstRow.querySelector(".product-search")?.value?.trim() || "";
    const firstPriceValue = firstRow.querySelector(".price")?.value || "";
    const hasPrefill = Boolean(firstSelectValue || firstSearchValue || String(firstPriceValue || "").trim());
    if (!hasPrefill) clearRow(firstRow);
  }

  function addBlankRow() {
    ensureRowTemplate();

    const tbody = document.getElementById("orderBody");
    if (!tbody || !rowTemplate) return null;

    const clone = rowTemplate.cloneNode(true);
    ensureSingleRowControls(clone);
    clearRow(clone);
    tbody.appendChild(clone);
    return clone;
  }

  function ensureRows(desiredCount) {
    ensureRowTemplate();

    const tbody = document.getElementById("orderBody");
    if (!tbody) return;

    while (tbody.querySelectorAll("tr.item-row").length < desiredCount) {
      addBlankRow();
    }

    // Normalize all rows (safe).
    tbody.querySelectorAll("tr.item-row").forEach((row) => ensureSingleRowControls(row));
    updateSerialNumbers();
  }

  function ensureRowsFillViewport() {
    // Fill visible table area with blank rows to avoid an empty "gap" under the last row.
    // (Busy/Tally-like voucher grid: always shows many entry lines.)
    const fallback = 12;
    ensureRowTemplate();
    const container = document.querySelector("#step-2 .table-responsive");
    const table = document.getElementById("orderTable");
    const tbody = document.getElementById("orderBody");
    if (!container || !table || !tbody) return ensureRows(fallback);

    const thead = table.querySelector("thead");
    const headerH = thead?.getBoundingClientRect?.().height || 0;
    const containerH = container.getBoundingClientRect?.().height || container.clientHeight || 0;

    const firstRow = tbody.querySelector("tr.item-row");
    let rowH = firstRow?.getBoundingClientRect?.().height || 28;
    rowH = clampNumber(rowH, 22, 64);

    const usable = Math.max(0, containerH - headerH - 10);
    const visibleRows = rowH > 0 ? Math.floor(usable / rowH) : fallback;
    // Allow more rows for large viewports / low browser zoom (e.g., Chrome at 33%).
    const desired = Math.max(28, clampNumber(visibleRows + 2, fallback, 220));
    ensureRows(desired);

    // If our estimated row height was off, keep adding rows until the grid looks "filled".
    // (No blank white gap at the bottom of the table viewport.)
    try {
      let guard = 0;
      while (guard < 60) {
        const bodyH = tbody.getBoundingClientRect?.().height || 0;
        if (bodyH >= usable) break;
        const count = tbody.querySelectorAll("tr.item-row").length;
        if (count >= 220) break;
        addBlankRow();
        guard += 1;
      }
      // Normalize + serial numbers after adding.
      tbody.querySelectorAll("tr.item-row").forEach((row) => ensureSingleRowControls(row));
      updateSerialNumbers();
    } catch (e) {}
  }

  let _fillRowsTimer = null;
  function queueEnsureRowsFillViewport() {
    if (_fillRowsTimer) window.clearTimeout(_fillRowsTimer);
    _fillRowsTimer = window.setTimeout(() => {
      _fillRowsTimer = null;
      window.requestAnimationFrame(() => ensureRowsFillViewport());
    }, 50);
  }

  function focusFinishAction() {
    const helpBtn = document.querySelector(".busy-bottom-bar button[data-action='help']");
    // User flow: after finishing item entry, focus should land on F1 (Help) first,
    // then user navigates with arrow keys to other function buttons (e.g., F8 Sundry).
    if (helpBtn) {
      helpBtn.scrollIntoView?.({ block: "nearest" });
      helpBtn.focus();
      return true;
    }

    // Keep narration reachable even if bottom bar isn't mounted for some reason.
    const narration = document.getElementById("pcNarration");
    if (narration) {
      narration.scrollIntoView?.({ block: "nearest" });
      narration.focus();
      return true;
    }

    // Keep top-strip fields reachable if bottom bar isn't mounted for some reason.
    const reference = document.querySelector('input[name="reference"]');
    if (reference) {
      reference.scrollIntoView?.({ block: "nearest" });
      reference.focus();
      return true;
    }

    const primarySubmit = document.querySelector('#orderForm button[type="submit"]');
    if (primarySubmit) {
      primarySubmit.scrollIntoView?.({ block: "nearest" });
      primarySubmit.focus();
      return true;
    }
    const nextStepBtn = document.getElementById("nextStep");
    if (nextStepBtn) {
      nextStepBtn.scrollIntoView?.({ block: "nearest" });
      nextStepBtn.focus();
      return true;
    }
    const saveBtn = document.querySelector(".busy-bottom-bar button[data-action='save']");
    if (saveBtn) {
      saveBtn.scrollIntoView?.({ block: "nearest" });
      saveBtn.focus();
      return true;
    }
    return false;
  }

  function updateSerialNumbers() {
    const rows = Array.from(document.querySelectorAll("#orderBody tr.item-row"));
    rows.forEach((row, idx) => {
      const el = row.querySelector(".pc-sno-text");
      if (el) el.textContent = String(idx + 1);
    });
  }

  function normalizePcTableColumns() {
    const table = document.getElementById("orderTable");
    if (!table || table.dataset.pcBusyCols === "1") return;
    const headRow = table.querySelector("thead tr");
    if (!headRow) return;

    headRow.innerHTML = `
      <th class="fw-bold">S.No</th>
      <th class="fw-bold">Product/Item (F3)</th>
      <th class="fw-bold">Qty</th>
      <th class="fw-bold">Unit</th>
      <th class="fw-bold">Price</th>
      <th class="fw-bold">Amount</th>
      <th class="fw-bold">Action</th>
    `;
    table.dataset.pcBusyCols = "1";
  }

  function removePcAddRowButton() {
    const btn = document.getElementById("addRow");
    if (!btn) return;
    const wrap = btn.closest(".text-center.mb-4") || btn.parentElement;
    wrap?.remove?.();
  }

  function getActiveRow() {
    const active = document.activeElement;
    if (!active) return null;
    return active.closest("tr.item-row");
  }

  function calculateRowAmount(row) {
    const qty = parseMoney(row.querySelector(".qty")?.value);
    const price = parseMoney(row.querySelector(".price")?.value);
    const base = qty * price;

    const discountPercent = clampNumber(parseMoney(row.querySelector("input.discount_percent")?.value), 0, 100);
    const discountAmount = Math.max(0, parseMoney(row.querySelector("input.discount_amount")?.value));

    let discount = 0;
    if (discountPercent > 0) discount = (base * discountPercent) / 100;
    if (discountAmount > 0) discount = discountAmount;

    const net = Math.max(0, base - discount);
    const amountInput = row.querySelector(".amount");
    const isEditingAmount = amountInput && document.activeElement === amountInput;
    if (amountInput && !isEditingAmount) {
      amountInput.value = Number.isFinite(net) ? net.toFixed(2) : "";
    }
    if (amountInput) {
      const label =
        discountPercent > 0
          ? `Discount: ${discountPercent}%`
          : discountAmount > 0
            ? `Discount: ₹${discountAmount.toFixed(2)}`
            : "";
      amountInput.title = label;
    }
    return net;
  }

  function normalizeBillSundryLines(lines) {
    if (!Array.isArray(lines)) return [];
    return lines
      .map((l) => ({
        name: String(l?.name || "").trim(),
        narration: String(l?.narration || "").trim(),
        rate: String(l?.rate || "").trim(),
        amount: parseMoney(l?.amount),
      }))
      .filter((l) => l.name || l.narration || l.rate || l.amount);
  }

  function getBillSundryTotal() {
    return normalizeBillSundryLines(billSundryLines).reduce((sum, l) => sum + (Number.isFinite(l.amount) ? l.amount : 0), 0);
  }

  function loadBillSundryFromStorage() {
    try {
      const raw = localStorage.getItem(SUNDRY_STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      billSundryLines = normalizeBillSundryLines(parsed);
    } catch (e) {}
  }

  function persistBillSundryToStorage() {
    try {
      localStorage.setItem(SUNDRY_STORAGE_KEY, JSON.stringify(normalizeBillSundryLines(billSundryLines)));
    } catch (e) {}
  }

  function ensureBillSundryHiddenInput() {
    const form = document.getElementById("orderForm");
    if (!form) return null;
    let input = form.querySelector('input[name="bill_sundry_json"]');
    if (!input) {
      input = document.createElement("input");
      input.type = "hidden";
      input.name = "bill_sundry_json";
      input.id = "pcBillSundryJson";
      form.appendChild(input);
    }
    return input;
  }

  function syncBillSundryHiddenInput() {
    const input = ensureBillSundryHiddenInput();
    if (!input) return;
    try {
      input.value = JSON.stringify(normalizeBillSundryLines(billSundryLines));
    } catch (e) {
      input.value = "[]";
    }
  }

  function ensureGstHiddenInputs() {
    const form = document.getElementById("orderForm");
    if (!form) return { enabled: null, rate: null };

    let enabled = form.querySelector('input[name="gst_enabled"]');
    if (!enabled) {
      enabled = document.createElement("input");
      enabled.type = "hidden";
      enabled.name = "gst_enabled";
      enabled.id = "pcGstEnabledHidden";
      form.appendChild(enabled);
    }

    let rate = form.querySelector('input[name="gst_rate"]');
    if (!rate) {
      rate = document.createElement("input");
      rate.type = "hidden";
      rate.name = "gst_rate";
      rate.id = "pcGstRateHidden";
      form.appendChild(rate);
    }

    return { enabled, rate };
  }

  function syncGstHiddenInputs(gstEnabled, gstRate) {
    const inputs = ensureGstHiddenInputs();
    if (!inputs.enabled || !inputs.rate) return;
    inputs.enabled.value = gstEnabled ? "1" : "0";
    inputs.rate.value = String(Number.isFinite(gstRate) ? gstRate : 0);
  }

  function calculateTotals() {
    const tbody = document.getElementById("orderBody");
    if (!tbody) return;

    let subtotal = 0;
    tbody.querySelectorAll("tr.item-row").forEach((row) => {
      subtotal += calculateRowAmount(row);
    });

    const gstEnabled = document.getElementById("pcGstEnabled")?.checked ?? true;
    const gstRate = clampNumber(parseMoney(document.getElementById("pcGstRate")?.value), 0, 28);

    const tax = gstEnabled ? (subtotal * gstRate) / 100 : 0;
    const sundry = getBillSundryTotal();
    const grand = subtotal + tax + sundry;

    syncGstHiddenInputs(gstEnabled, gstRate);

    // Some templates contain duplicated IDs; update all occurrences safely.
    document.querySelectorAll("#subTotal").forEach((el) => (el.textContent = subtotal.toFixed(2)));
    document.querySelectorAll("#tax").forEach((el) => (el.textContent = tax.toFixed(2)));
    document.querySelectorAll("#grandTotal").forEach((el) => (el.textContent = grand.toFixed(2)));

    const gstLabel = document.getElementById("pcGstLabel");
    if (gstLabel) gstLabel.textContent = gstEnabled ? `GST (${gstRate}%):` : "GST (Off):";

    updateSaleTypePanel();
    updateVoucherPanel();
    updateItemPanel(getActiveRow());
  }

  function hideDropdown(row) {
    const dd = row.querySelector(".product-dropdown");
    if (!dd) return;
    dd.style.display = "none";
    dd.innerHTML = "";
    dd.dataset.activeIndex = "0";
  }

  function hidePartyDropdown() {
    const dd = document.getElementById("partyDropdown");
    if (!dd) return;
    dd.classList.add("dropdown-hidden");
    dd.style.display = "none";
    dd.innerHTML = "";
    dd.dataset.activeIndex = "0";
  }

  function setActivePartyIndex(index) {
    const dd = document.getElementById("partyDropdown");
    if (!dd || dd.style.display === "none") return;
    const items = Array.from(dd.querySelectorAll(".busy-dd-item"));
    if (!items.length) return;

    const nextIndex = clampNumber(index, 0, items.length - 1);
    dd.dataset.activeIndex = String(nextIndex);
    items.forEach((btn, i) => btn.classList.toggle("active", i === nextIndex));
    items[nextIndex].scrollIntoView({ block: "nearest" });
  }

  function applyParty(partyId) {
    const select = document.getElementById("partySelect");
    const search = document.getElementById("partySearch");
    if (!select || !search) return false;

    select.value = String(partyId || "");
    const selected = select.selectedOptions?.[0];
    if (selected) search.value = (selected.textContent || "").trim();

    hidePartyDropdown();
    setTimeout(() => focusFirstVisible("#orderBody .item-row .product-search"), 0);
    return true;
  }

  function pickActiveParty() {
    const dd = document.getElementById("partyDropdown");
    if (!dd || dd.style.display === "none") return false;
    const items = Array.from(dd.querySelectorAll(".busy-dd-item"));
    if (!items.length) return false;

    const activeIndex = clampNumber(parseInt(dd.dataset.activeIndex || "0", 10), 0, items.length - 1);
    const activeItem = items[activeIndex];
    const id = activeItem?.dataset?.id;
    if (!id) return false;
    return applyParty(id);
  }

  function matchParties(partiesIndex, query) {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    if (q.length < PARTY_MIN_SEARCH_CHARS) return [];

    const results = [];
    for (const p of partiesIndex) {
      if (p.nameLower.includes(q)) results.push(p);
      if (results.length >= 25) break;
    }
    return results;
  }

  function renderPartyDropdown(matches) {
    const dd = document.getElementById("partyDropdown");
    if (!dd) return;

    if (!matches.length) {
      hidePartyDropdown();
      return;
    }

    dd.classList.remove("dropdown-hidden");
    dd.style.display = "block";
    dd.dataset.activeIndex = "0";
    dd.innerHTML = matches
      .map(
        (p, idx) =>
          `<button type="button" class="busy-dd-item${idx === 0 ? " active" : ""}" data-id="${escapeHtml(
            p.id
          )}">${escapeHtml(p.name)}</button>`
      )
      .join("");
  }

  function renderDropdown(row, matches) {
    const dd = row.querySelector(".product-dropdown");
    if (!dd) return;

    if (!matches.length) {
      hideDropdown(row);
      return;
    }

    dd.style.display = "block";
    dd.dataset.activeIndex = "0";
    dd.innerHTML = matches
      .map(
        (p, idx) =>
          `<button type="button" class="busy-dd-item${idx === 0 ? " active" : ""}" data-id="${escapeHtml(
            p.id
          )}">${escapeHtml(p.name)}<span class="busy-dd-meta">₹${p.price.toFixed(2)}${p.unit ? ` | ${escapeHtml(p.unit)}` : ""}${Number.isFinite(p.stock) && p.stock ? ` | Stock: ${p.stock}` : ""}</span></button>`
      )
      .join("");
  }

  function setActiveDropdownIndex(row, index) {
    const dd = row.querySelector(".product-dropdown");
    if (!dd || dd.style.display === "none") return;
    const items = Array.from(dd.querySelectorAll(".busy-dd-item"));
    if (!items.length) return;

    const nextIndex = clampNumber(index, 0, items.length - 1);
    dd.dataset.activeIndex = String(nextIndex);
    items.forEach((btn, i) => btn.classList.toggle("active", i === nextIndex));
    items[nextIndex].scrollIntoView({ block: "nearest" });
  }

  function pickDropdownActive(row, options = {}) {
    const dd = row.querySelector(".product-dropdown");
    if (!dd || dd.style.display === "none") return false;
    const items = Array.from(dd.querySelectorAll(".busy-dd-item"));
    if (!items.length) return false;

    const activeIndex = clampNumber(parseInt(dd.dataset.activeIndex || "0", 10), 0, items.length - 1);
    const activeItem = items[activeIndex];
    if (!activeItem) return false;
    const id = activeItem.dataset.id;
    if (!id) return false;
    applyProductToRow(row, id, options);
    return true;
  }

  function applyProductToRow(row, productId, options = {}) {
    const select = row.querySelector(".product");
    const productSearch = row.querySelector(".product-search");
    if (!select || !productSearch) return;

    select.value = productId;
    const selected = select.selectedOptions?.[0];
    if (selected) productSearch.value = selected.textContent?.trim() || "";

    // price autofill
    const price = parseMoney(selected?.dataset?.price);
    const priceInput = row.querySelector(".price");
    if (priceInput && price) priceInput.value = price.toFixed(2);

    // unit autofill
    const unit = (selected?.dataset?.unit || "").trim();
    const unitInput = row.querySelector(".unit");
    if (unitInput) unitInput.value = unit;

    hideDropdown(row);
    calculateTotals();

    setTimeout(() => {
      const nextFocus = options.nextFocus || "qty";
      if (nextFocus === "nextRow") {
        focusNextRowProduct(row);
        return;
      }
      if (nextFocus === "price") {
        row.querySelector(".price")?.focus();
        return;
      }
      if (nextFocus === "amount") {
        row.querySelector(".amount")?.focus();
        return;
      }
      row.querySelector(".qty")?.focus();
    }, 0);
  }

  function matchProducts(productsIndex, query) {
    const q = query.trim().toLowerCase();
    if (!q) return [];

    // Barcode exact match (fast path)
    const barcodeMatch = productsIndex.find((p) => p.barcode && p.barcode === query.trim());
    if (barcodeMatch) return [barcodeMatch];

    if (q.length < MIN_SEARCH_CHARS) return [];

    const results = [];
    for (const p of productsIndex) {
      if (p.nameLower.includes(q)) results.push(p);
      if (results.length >= MAX_DROPDOWN_RESULTS) break;
    }
    return results;
  }

  function focusRowFieldByClass(row, className, direction) {
    let target = row;
    while (target) {
      target = direction > 0 ? target.nextElementSibling : target.previousElementSibling;
      if (!target) {
        if (direction > 0) {
          const tbody = document.getElementById("orderBody");
          const count = tbody?.querySelectorAll?.("tr.item-row")?.length || 0;
          if (count) ensureRows(count + 1);
          const next = row.nextElementSibling;
          const field = next?.querySelector?.(`.${className}`);
          if (field) {
            field.scrollIntoView?.({ block: "nearest" });
            field.focus();
          }
        }
        return;
      }
      if (!target.classList.contains("item-row")) continue;

      const field = target.querySelector(`.${className}`);
      if (field) {
        field.scrollIntoView?.({ block: "nearest" });
        field.focus();
        return;
      }
    }
  }

  function updatePriceFromAmount(row) {
    const qtyInput = row.querySelector(".qty");
    const priceInput = row.querySelector(".price");
    const amountInput = row.querySelector(".amount");
    if (!qtyInput || !priceInput || !amountInput) return;

    const qty = Math.max(0, parseMoney(qtyInput.value));
    const net = Math.max(0, parseMoney(amountInput.value));

    if (!qty) {
      priceInput.value = "";
      return;
    }

    const discountPercent = clampNumber(parseMoney(row.querySelector("input.discount_percent")?.value), 0, 100);
    const discountAmount = Math.max(0, parseMoney(row.querySelector("input.discount_amount")?.value));

    let base = net;
    if (discountAmount > 0) {
      base = net + discountAmount;
    } else if (discountPercent > 0 && discountPercent < 100) {
      base = net / (1 - discountPercent / 100);
    }

    const price = base / qty;
    priceInput.value = Number.isFinite(price) ? price.toFixed(2) : "";
  }

  function focusNextRowProduct(row, skipAutoAdd = false) {
    let next = row.nextElementSibling;
    if (!next) {
      // If skipAutoAdd is true, move focus to next step button instead of adding a row
      if (skipAutoAdd) {
        const nextStepBtn = document.getElementById("nextStep");
        if (nextStepBtn) {
          nextStepBtn.scrollIntoView?.({ block: "nearest" });
          nextStepBtn.focus();
        }
        return;
      }
      
      const tbody = document.getElementById("orderBody");
      const count = tbody?.querySelectorAll?.("tr.item-row")?.length || 0;
      if (count) ensureRows(count + 1);
      next = row.nextElementSibling;
    }

    const input = next?.querySelector?.(".product-search");
    if (input) {
      input.scrollIntoView?.({ block: "nearest" });
      input.focus();
    }
  }

  function trapModalFocus(modalEl) {
    if (!modalEl) return;
    modalEl.addEventListener("keydown", (e) => {
      if (e.key !== "Tab") return;
      const focusable = Array.from(
        modalEl.querySelectorAll(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      ).filter((el) => el.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (e.shiftKey) {
        if (active === first || !modalEl.contains(active)) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (active === last) {
          e.preventDefault();
          first.focus();
        }
      }
    });
  }

  function mountPcControls() {
    const summaryBody = document.querySelector("#step-2 .summary-card .card-body");
    if (!summaryBody) return;

    if (!document.getElementById("pcGstEnabled")) {
      const controls = document.createElement("div");
      controls.className = "pc-busy-controls";
      controls.innerHTML = `
        <div class="pc-busy-row">
          <label class="pc-busy-label"><input type="checkbox" id="pcGstEnabled" checked> GST</label>
          <select id="pcGstRate" class="pc-busy-select" aria-label="GST rate">
            <option value="0">0%</option>
            <option value="5">5%</option>
            <option value="12">12%</option>
            <option value="18" selected>18%</option>
            <option value="28">28%</option>
          </select>
        </div>
        <div class="pc-busy-row">
          <label class="pc-busy-label">Zoom</label>
          <div class="pc-zoom-ctrl" role="group" aria-label="Zoom controls">
            <button type="button" class="pc-zoom-btn" id="pcZoomOut" title="Ctrl+-">-</button>
            <input type="range" id="pcZoomRange" min="80" max="130" value="100" aria-label="Zoom percentage">
            <button type="button" class="pc-zoom-btn" id="pcZoomIn" title="Ctrl++">+</button>
            <span class="pc-zoom-value" id="pcZoomValue">100%</span>
          </div>
        </div>
        <div class="pc-busy-row">
          <label class="pc-busy-label"><input type="checkbox" id="pcFullWidth"> Full Width</label>
        </div>
        <div class="pc-busy-row">
          <label class="pc-busy-label">Narration</label>
        </div>
        <textarea id="pcNarration" name="notes" class="pc-busy-textarea" rows="2" placeholder="Narration (Alt+N)"></textarea>
      `;
      summaryBody.insertBefore(controls, summaryBody.firstChild);

      // Disable legacy step-3 notes name to avoid duplicate POST key.
      const legacyNotes = document.querySelector('#step-3 textarea[name="notes"]');
      if (legacyNotes) {
        legacyNotes.disabled = true;
        legacyNotes.removeAttribute("name");
      }
    }

    // Add label hook if missing (template may contain duplicated markup).
    if (!document.getElementById("pcGstLabel")) {
      const candidates = Array.from(summaryBody.querySelectorAll("span.fw-bold, span"));
      const gstSpan = candidates.find((el) => (el.textContent || "").toUpperCase().includes("GST"));
      if (gstSpan) gstSpan.id = "pcGstLabel";
    }

    document.getElementById("pcGstEnabled")?.addEventListener("change", calculateTotals);
    document.getElementById("pcGstRate")?.addEventListener("change", calculateTotals);

    document.getElementById("pcZoomOut")?.addEventListener("click", () => adjustZoom(-5));
    document.getElementById("pcZoomIn")?.addEventListener("click", () => adjustZoom(5));
    document.getElementById("pcZoomRange")?.addEventListener("input", (e) => applyZoom(parseInt(e.target.value, 10)));
    document.getElementById("pcFullWidth")?.addEventListener("change", (e) => applyFullWidth(!!e.target.checked));
  }

  function mountSidePanels() {
    const sideCol = document.querySelector("#step-2 .row.justify-content-center > [class*='col-']");
    if (!sideCol) return;

    const summaryCard = sideCol.querySelector(".summary-card");
    if (!summaryCard) return;

    if (document.getElementById("pcSidePanels")) return;

    const panels = document.createElement("div");
    panels.id = "pcSidePanels";
    panels.className = "busy-side-panels";
    panels.innerHTML = `
      <div class="busy-panel preview-panel">
        <div class="busy-panel-title">Preview</div>
        <div class="busy-panel-body">
          <div class="busy-preview-grid">
            <div class="busy-preview-box">
              <img id="pcPreviewImg1" alt="Preview 1" />
              <div class="busy-preview-actions">
                <button type="button" class="busy-preview-btn primary" data-action="upload1">Upload</button>
                <button type="button" class="busy-preview-btn" data-action="clear1">Clear</button>
              </div>
              <input type="file" accept="image/*" id="pcPreviewFile1" style="display:none" />
            </div>
            <div class="busy-preview-box">
              <img id="pcPreviewImg2" alt="Preview 2" />
              <div class="busy-preview-actions">
                <button type="button" class="busy-preview-btn primary" data-action="upload2">Upload</button>
                <button type="button" class="busy-preview-btn" data-action="clear2">Clear</button>
              </div>
              <input type="file" accept="image/*" id="pcPreviewFile2" style="display:none" />
            </div>
          </div>
        </div>
      </div>
      <div class="busy-panel">
        <div class="busy-panel-title">Sale Type Description</div>
        <div class="busy-panel-body" id="pcSaleTypeBody">-</div>
      </div>
      <div class="busy-panel">
        <div class="busy-panel-title">Item Info.</div>
        <div class="busy-panel-body scroll" id="pcItemInfoBody">Select an item row…</div>
      </div>
      <div class="busy-panel">
        <div class="busy-panel-title">Voucher Info.</div>
        <div class="busy-panel-body scroll" id="pcVoucherInfoBody">-</div>
      </div>
    `;
    sideCol.insertBefore(panels, summaryCard);

    const PREVIEW_KEY_1 = "add_order_pc_preview_img_1";
    const PREVIEW_KEY_2 = "add_order_pc_preview_img_2";

    function loadPreviewFromStorage() {
      const img1 = document.getElementById("pcPreviewImg1");
      const img2 = document.getElementById("pcPreviewImg2");

      const stored1 = localStorage.getItem(PREVIEW_KEY_1) || "";
      const stored2 = localStorage.getItem(PREVIEW_KEY_2) || "";

      // If user hasn't uploaded, show default (images removed - use placeholder if needed)
      if (img1) img1.src = stored1 || "";
      if (img2) img2.src = stored2 || "";

      img1?.addEventListener?.("error", () => (img1.src = stored1 || ""));
      img2?.addEventListener?.("error", () => (img2.src = stored2 || ""));
    }

    function bindPreviewUploader(btnAction, fileId, imgId, storageKey) {
      const file = document.getElementById(fileId);
      const img = document.getElementById(imgId);
      if (!file || !img) return;

      panels.addEventListener("click", (e) => {
        const btn = e.target.closest(`button[data-action="${btnAction}"]`);
        if (!btn) return;
        file.click();
      });

      file.addEventListener("change", () => {
        const selected = file.files?.[0];
        if (!selected) return;
        const reader = new FileReader();
        reader.onload = () => {
          const dataUrl = String(reader.result || "");
          img.src = dataUrl;
          try {
            localStorage.setItem(storageKey, dataUrl);
          } catch (e) {}
        };
        reader.readAsDataURL(selected);
      });
    }

    function bindPreviewClear(btnAction, imgId, storageKey) {
      const img = document.getElementById(imgId);
      if (!img) return;
      panels.addEventListener("click", (e) => {
        const btn = e.target.closest(`button[data-action="${btnAction}"]`);
        if (!btn) return;
        img.src = "";
        localStorage.removeItem(storageKey);
      });
    }

    loadPreviewFromStorage();
    bindPreviewUploader("upload1", "pcPreviewFile1", "pcPreviewImg1", PREVIEW_KEY_1);
    bindPreviewUploader("upload2", "pcPreviewFile2", "pcPreviewImg2", PREVIEW_KEY_2);
    bindPreviewClear("clear1", "pcPreviewImg1", PREVIEW_KEY_1);
    bindPreviewClear("clear2", "pcPreviewImg2", PREVIEW_KEY_2);
  }

  function getFocusableInModal(modal) {
    if (!modal) return [];
    const dialog = modal.querySelector(".busy-modal-dialog") || modal;
    const focusables = Array.from(
      dialog.querySelectorAll(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    ).filter((el) => el.offsetParent !== null);
    return focusables;
  }

  function focusNextInModal(modal, direction) {
    const focusables = getFocusableInModal(modal);
    if (!focusables.length) return;
    const active = document.activeElement;
    const idx = focusables.indexOf(active);
    const safeIdx = idx >= 0 ? idx : 0;
    const nextIdx = (safeIdx + (direction > 0 ? 1 : -1) + focusables.length) % focusables.length;
    focusables[nextIdx].focus();
  }

  function updateSaleTypePanel() {
    const el = document.getElementById("pcSaleTypeBody");
    if (!el) return;

    const orderTypeSel = document.getElementById("orderType");
    const typeValue = orderTypeSel?.value || "";
    const typeLabel = orderTypeSel?.selectedOptions?.[0]?.textContent?.trim() || "-";

    const gstEnabled = document.getElementById("pcGstEnabled")?.checked ?? true;
    const gstRate = clampNumber(parseMoney(document.getElementById("pcGstRate")?.value), 0, 28);

    const lines = [];
    lines.push(typeLabel);
    if (typeValue === "sale") lines.push("Export Sales / Retail billing style (tax may apply).");
    if (typeValue === "purchase") lines.push("Purchase entry (stock inward).");
    lines.push(gstEnabled ? `GST enabled (Rate: ${gstRate}%)` : "GST disabled (0%)");

    el.textContent = lines.filter(Boolean).join("\n");
  }

  function updateVoucherPanel() {
    const el = document.getElementById("pcVoucherInfoBody");
    if (!el) return;

    const partyName =
      document.getElementById("partySearch")?.value?.trim() ||
      document.getElementById("partySelect")?.selectedOptions?.[0]?.textContent?.trim() ||
      "-";
    const now = new Date();

    const itemsCount = Array.from(document.querySelectorAll("#orderBody tr.item-row")).filter((row) => {
      const sel = row.querySelector(".product");
      return !!sel?.value;
    }).length;

    const subtotal = parseMoney(document.getElementById("subTotal")?.textContent);
    const tax = parseMoney(document.getElementById("tax")?.textContent);
    const grand = parseMoney(document.getElementById("grandTotal")?.textContent);
    const sundry = getBillSundryTotal();

    const lines = [];
    lines.push(`Party: ${partyName}`);
    lines.push(`Date: ${now.toLocaleDateString()}  ${now.toLocaleTimeString()}`);
    lines.push(`Items: ${itemsCount}`);
    lines.push(`Subtotal: ₹${subtotal.toFixed(2)}`);
    lines.push(`GST: ₹${tax.toFixed(2)}`);
    if (sundry) lines.push(`Bill Sundry: ₹${sundry.toFixed(2)}`);
    lines.push(`Grand Total: ₹${grand.toFixed(2)}`);

    el.textContent = lines.join("\n");
  }

  function updateSmartKhataCreditInfo() {
    const wrap = document.getElementById("smartKhataCreditInfo");
    const badge = document.getElementById("smartKhataCreditBadge");
    const meta = document.getElementById("smartKhataCreditMeta");
    const warn = document.getElementById("smartKhataCreditWarn");
    if (!wrap || !badge || !meta || !warn) return;

    const orderType = (document.getElementById("orderType")?.value || "").toLowerCase();
    const partyId = (document.getElementById("partySelect")?.value || "").trim();

    // Only show for Sales orders where party is a customer.
    if (!partyId || orderType !== "sale") {
      wrap.style.display = "none";
      warn.style.display = "none";
      return;
    }

    const seq = ++smartKhataCreditSeq;
    badge.className = "badge bg-light text-dark";
    badge.textContent = "Credit Score: Loading...";
    meta.textContent = "";
    warn.style.display = "none";
    wrap.style.display = "";

    fetch(`/api/customer-credit-score/?party_id=${encodeURIComponent(partyId)}`, { headers: { "Accept": "application/json" } })
      .then((r) => (r.ok ? r.json() : Promise.reject(r)))
      .then((data) => {
        if (seq !== smartKhataCreditSeq) return;
        const score = Number.parseInt(String(data?.credit_score ?? "0"), 10) || 0;
        const level = String(data?.level || "").trim() || "-";
        const totalDue = String(data?.total_due ?? "");
        const avgDelay = Number.parseInt(String(data?.average_payment_delay ?? "0"), 10) || 0;

        // Badge color
        if (score >= 80) badge.className = "badge bg-success";
        else if (score >= 60) badge.className = "badge bg-warning text-dark";
        else if (score >= 40) badge.className = "badge text-dark";
        else badge.className = "badge bg-danger";

        if (score >= 40 && score < 60) badge.style.background = "#f97316";
        else badge.style.background = "";

        badge.textContent = `Credit Score: ${score}`;
        meta.textContent = `Level: ${level} • Due: ₹${totalDue || "0.00"} • Avg Delay: ${avgDelay}d`;

        if (score < 40) {
          warn.textContent = `Warning: This customer has a credit score of ${score} (High Risk).`;
          warn.style.display = "";
        } else {
          warn.style.display = "none";
        }
      })
      .catch(() => {
        if (seq !== smartKhataCreditSeq) return;
        // Not a customer / API not available; hide to avoid confusing UI.
        wrap.style.display = "none";
        warn.style.display = "none";
      });
  }

  function updateItemPanel(row) {
    const el = document.getElementById("pcItemInfoBody");
    if (!el) return;

    if (!row) {
      el.textContent = "Select an item row…";
      return;
    }

    const select = row.querySelector(".product");
    const name = row.querySelector(".product-search")?.value?.trim() || select?.selectedOptions?.[0]?.textContent?.trim() || "-";
    const unit =
      row.querySelector(".unit")?.value?.trim() ||
      (select?.selectedOptions?.[0]?.dataset?.unit || "").trim();
    const stock = parseMoney(select?.selectedOptions?.[0]?.dataset?.stock);
    const qty = parseMoney(row.querySelector(".qty")?.value);
    const price = parseMoney(row.querySelector(".price")?.value);
    const amount = parseMoney(row.querySelector(".amount")?.value);
    const dp = clampNumber(parseMoney(row.querySelector("input.discount_percent")?.value), 0, 100);
    const da = Math.max(0, parseMoney(row.querySelector("input.discount_amount")?.value));

    const gstEnabled = document.getElementById("pcGstEnabled")?.checked ?? true;
    const gstRate = clampNumber(parseMoney(document.getElementById("pcGstRate")?.value), 0, 28);

    const lines = [];
    lines.push(`Item: ${name}`);
    lines.push(`Qty: ${qty || 0}`);
    if (unit) lines.push(`Unit: ${unit}`);
    if (Number.isFinite(stock) && stock) lines.push(`Stock: ${stock}${unit ? ` ${unit}` : ""}`);
    lines.push(`Price: ₹${price.toFixed(2)}`);
    if (dp > 0) lines.push(`Discount: ${dp}%`);
    if (da > 0) lines.push(`Discount Amt: ₹${da.toFixed(2)}`);
    lines.push(`Amount: ₹${amount.toFixed(2)}`);
    lines.push(gstEnabled ? `Tax Rate: ${gstRate}%` : "Tax Rate: 0%");

    el.textContent = lines.join("\n");
  }

  function mountBottomBar() {
    const card = document.getElementById("mainOrderCard");
    if (!card || card.querySelector(".busy-bottom-bar")) return;

    const bar = document.createElement("div");
    bar.className = "busy-bottom-bar";
    bar.innerHTML = `
      <button type="button" class="bb-btn" data-action="help"><span class="k">F1</span> Help</button>
      <button type="button" class="bb-btn" data-action="party"><span class="k">F2</span> Party</button>
      <button type="button" class="bb-btn" data-action="item"><span class="k">F3</span> Item</button>
      <button type="button" class="bb-btn" data-action="addRow"><span class="k">F4</span> Add Row</button>
      <button type="button" class="bb-btn" data-action="discount"><span class="k">F9</span> Discount</button>
      <button type="button" class="bb-btn" data-action="sundry"><span class="k">F8</span> Sundry</button>
      <button type="button" class="bb-btn" data-action="print"><span class="k">F7</span> Print</button>
      <button type="button" class="bb-btn primary" data-action="save"><span class="k">F5</span> Save</button>
      <button type="button" class="bb-btn" data-action="quit"><span class="k">Esc</span> Quit</button>
    `;
    card.appendChild(bar);

    bar.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-action]");
      if (!btn) return;
      handleAction(btn.dataset.action);
    });

    // Bottom bar keyboard UX:
    // - Arrow keys move between buttons
    // - Enter/Space activates the focused button (opens Sundry/Discount/etc)
    bar.addEventListener("keydown", (e) => {
      const active = document.activeElement;
      if (!active || active.tagName !== "BUTTON" || !active.classList.contains("bb-btn")) return;

      const buttons = Array.from(bar.querySelectorAll("button.bb-btn")).filter((b) => !b.disabled);
      if (!buttons.length) return;

      const idx = buttons.indexOf(active);
      if (idx < 0) return;

      const prev = () => buttons[(idx - 1 + buttons.length) % buttons.length];
      const next = () => buttons[(idx + 1) % buttons.length];

      if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
        e.preventDefault();
        e.stopPropagation();
        prev().focus();
        return;
      }
      if (e.key === "ArrowRight" || e.key === "ArrowDown") {
        e.preventDefault();
        e.stopPropagation();
        next().focus();
        return;
      }

      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        e.stopPropagation();
        const action = active.dataset.action;
        if (action) handleAction(action);
      }
    });
  }

  function createDiscountModal() {
    if (document.getElementById("pcDiscountModal")) return;

    const modal = document.createElement("div");
    modal.id = "pcDiscountModal";
    modal.className = "busy-modal";
    modal.innerHTML = `
      <div class="busy-modal-dialog" role="dialog" aria-modal="true" aria-label="Item Price & Discount">
        <div class="busy-modal-title">
          <span>Item Price & Discount</span>
          <button type="button" class="busy-modal-x" data-action="cancel" aria-label="Close">×</button>
        </div>
        <div class="busy-modal-body">
          <div class="busy-modal-topline" id="pcDiscItemName">Item: -</div>
          <div class="busy-modal-grid">
            <div class="busy-modal-left">
              <div class="busy-modal-row2">
                <div class="busy-modal-label">Price / Pcs</div>
                <input type="number" step="0.01" min="0" id="pcRowPrice" class="busy-modal-input" />
              </div>
              <div class="busy-modal-row2">
                <div class="busy-modal-label">Discount</div>
                <input type="number" step="0.01" min="0" id="pcDiscValue" class="busy-modal-input" />
              </div>
              <div class="busy-modal-row2">
                <div class="busy-modal-label">Discount / Pcs.</div>
                <input type="text" id="pcDiscPerPcs" class="busy-modal-input" readonly />
              </div>
            </div>
            <div class="busy-modal-right">
              <div class="busy-modal-structure">(Structure Name : Simple Discount, % of Price)</div>
              <div class="busy-modal-cols">
                <div class="busy-col">
                  <div class="busy-col-head">Value</div>
                  <input type="text" id="pcCalcValue" class="busy-modal-input" readonly />
                </div>
                <div class="busy-col">
                  <div class="busy-col-head">Basis</div>
                  <select id="pcDiscBasis" class="busy-modal-select">
                    <option value="percent" selected>%</option>
                    <option value="amount">₹</option>
                  </select>
                </div>
                <div class="busy-col">
                  <div class="busy-col-head">Discount Amt</div>
                  <input type="text" id="pcCalcDiscountAmt" class="busy-modal-input" readonly />
                </div>
                <div class="busy-col">
                  <div class="busy-col-head">Effective Price</div>
                  <input type="text" id="pcCalcEffectivePrice" class="busy-modal-input" readonly />
                </div>
              </div>
              <div class="busy-stock-box" aria-label="Warehouse stock">
                <div class="busy-stock-head">
                  <div class="busy-stock-title">Warehouse Stock</div>
                  <label class="busy-stock-zero"><input type="checkbox" id="pcStockHideZero" /> Hide zero</label>
                </div>
                <div class="busy-stock-list" id="pcStockList">-</div>
              </div>
            </div>
          </div>
          <div class="busy-modal-hint">[ Esc - Quit ]  [ F2 - Done ]</div>
        </div>
        <div class="busy-modal-actions">
          <button type="button" class="busy-modal-btn primary" data-action="apply">Done (F2)</button>
          <button type="button" class="busy-modal-btn" data-action="cancel">Cancel</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    trapModalFocus(modal);

    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeDiscountModal();
      const btn = e.target.closest("button[data-action]");
      if (!btn) return;
      if (btn.dataset.action === "apply") applyDiscountFromModal();
      if (btn.dataset.action === "cancel") closeDiscountModal();
    });

    modal.querySelector("#pcStockHideZero")?.addEventListener("change", () => {
      const rows = Array.from(document.querySelectorAll("#orderBody tr.item-row"));
      const rowIndex = parseInt(modal.dataset.rowIndex || "-1", 10);
      const row = rows[rowIndex];
      if (row) updateDiscountModalStock(row);
    });
  }

  function openDiscountModal(options = {}) {
    createDiscountModal();
    const modal = document.getElementById("pcDiscountModal");
    if (!modal) return;
    const row = options.row || getActiveRow();
    if (!row) return;

    const dp = parseMoney(row.querySelector("input.discount_percent")?.value);
    const da = parseMoney(row.querySelector("input.discount_amount")?.value);
    const type = da > 0 ? "amount" : "percent";
    const val = da > 0 ? da : dp;
    const price = parseMoney(row.querySelector(".price")?.value);

    modal.dataset.rowIndex = String(Array.from(document.querySelectorAll("#orderBody tr.item-row")).indexOf(row));
    modal.style.display = "flex";
    modal.dataset.returnFocus = options.returnFocus || "price";
    modal.dataset.afterApplyFocus = options.afterApplyFocus || "price";

    const basis = modal.querySelector("#pcDiscBasis");
    if (basis) basis.value = type;

    const priceInput = modal.querySelector("#pcRowPrice");
    if (priceInput) priceInput.value = price ? String(price.toFixed(2)) : "";

    const discInput = modal.querySelector("#pcDiscValue");
    if (discInput) discInput.value = val ? String(val) : "";

    syncDiscountModalCalculations();

    const focusTarget = options.focus === "price" ? priceInput : discInput;
    if (focusTarget) {
      focusTarget.focus();
      focusTarget.select?.();
    }

    updateDiscountModalStock(row);
  }

  function getProductNameForRow(row) {
    if (!row) return "-";
    const select = row.querySelector(".product");
    return (
      row.querySelector(".product-search")?.value?.trim() ||
      select?.selectedOptions?.[0]?.textContent?.trim() ||
      "-"
    );
  }

  async function fetchProductStock(productId) {
    const key = String(productId || "");
    if (!key) return null;
    if (stockCache.has(key)) return stockCache.get(key);

    const res = await fetch(`/commerce/api/product-stock/${encodeURIComponent(key)}/`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw new Error(`Stock API failed (${res.status})`);
    const data = await res.json();
    stockCache.set(key, data);
    return data;
  }

  function renderDiscountModalStock(data, { hideZero } = {}) {
    const list = document.getElementById("pcStockList");
    if (!list) return;

    if (!data) {
      list.textContent = "-";
      return;
    }

    const unit = String(data.product?.unit || "").trim();
    const rows = Array.isArray(data.warehouses) ? data.warehouses : [];
    const filtered = hideZero ? rows.filter((r) => parseMoney(r.quantity) !== 0) : rows;

    if (!filtered.length) {
      const total = Number.isFinite(parseMoney(data.total)) ? parseMoney(data.total) : 0;
      list.textContent = unit ? `Total Stock: ${total.toFixed(2)} ${unit}` : `Total Stock: ${total.toFixed(2)}`;
      return;
    }

    list.innerHTML = `
      <div class="busy-stock-row head"><span>Material Centre</span><span class="r">Stock${unit ? ` (${escapeHtml(unit)})` : ""}</span></div>
      ${filtered
        .map((w) => {
          const qty = parseMoney(w.quantity);
          return `<div class="busy-stock-row"><span>${escapeHtml(w.name || "-")}</span><span class="r">${Number.isFinite(qty) ? qty.toFixed(2) : "0.00"}</span></div>`;
        })
        .join("")}
    `;
  }

  function updateDiscountModalStock(row) {
    const modal = document.getElementById("pcDiscountModal");
    if (!modal || modal.style.display !== "flex") return;

    const itemNameEl = document.getElementById("pcDiscItemName");
    if (itemNameEl) itemNameEl.textContent = `Item: ${getProductNameForRow(row)}`;

    const hideZero = document.getElementById("pcStockHideZero")?.checked ?? false;
    const productId = row?.querySelector?.(".product")?.value || "";
    const list = document.getElementById("pcStockList");
    if (!list) return;

    if (!productId) {
      list.textContent = "Select product to view stock.";
      return;
    }

    list.textContent = "Loading stock...";
    fetchProductStock(productId)
      .then((data) => renderDiscountModalStock(data, { hideZero }))
      .catch(() => {
        list.textContent = "Stock not available.";
      });
  }

  function closeDiscountModal() {
    const modal = document.getElementById("pcDiscountModal");
    if (!modal) return;
    modal.style.display = "none";

    const rows = Array.from(document.querySelectorAll("#orderBody tr.item-row"));
    const rowIndex = parseInt(modal.dataset.rowIndex || "-1", 10);
    const row = rows[rowIndex];
    const returnFocus = modal.dataset.returnFocus || "price";

    modal.dataset.rowIndex = "";
    modal.dataset.returnFocus = "";
    modal.dataset.afterApplyFocus = "";

    // Restore focus to row field (avoid getting stuck in hidden modal).
    if (row) {
      if (returnFocus === "qty") row.querySelector(".qty")?.focus();
      else if (returnFocus === "amount") row.querySelector(".amount")?.focus();
      else row.querySelector(".price")?.focus();
    }
  }

  function applyDiscountFromModal() {
    const modal = document.getElementById("pcDiscountModal");
    if (!modal) return;
    const rows = Array.from(document.querySelectorAll("#orderBody tr.item-row"));
    const rowIndex = parseInt(modal.dataset.rowIndex || "-1", 10);
    const row = rows[rowIndex];
    if (!row) return;

    const type = modal.querySelector("#pcDiscBasis")?.value || "percent";
    const value = Math.max(0, parseMoney(modal.querySelector("#pcDiscValue")?.value));
    const price = Math.max(0, parseMoney(modal.querySelector("#pcRowPrice")?.value));

    const dp = row.querySelector("input.discount_percent");
    const da = row.querySelector("input.discount_amount");
    if (dp) dp.value = "0";
    if (da) da.value = "0";

    const priceInput = row.querySelector(".price");
    if (priceInput && Number.isFinite(price)) {
      priceInput.value = price ? price.toFixed(2) : "";
    }

    if (type === "amount") {
      if (da) da.value = String(value);
    } else {
      if (dp) dp.value = String(clampNumber(value, 0, 100));
    }

    const afterFocus = modal.dataset.afterApplyFocus || "price";
    modal.dataset.returnFocus = afterFocus;
    closeDiscountModal();
    calculateTotals();
    if (afterFocus === "nextRow") {
      focusNextRowProduct(row);
      return;
    }
    if (afterFocus === "qty") row.querySelector(".qty")?.focus();
    else if (afterFocus === "amount") row.querySelector(".amount")?.focus();
    else row.querySelector(".price")?.focus();
  }

  function syncDiscountModalCalculations() {
    const modal = document.getElementById("pcDiscountModal");
    if (!modal) return;

    const basis = modal.querySelector("#pcDiscBasis")?.value || "percent";
    const price = Math.max(0, parseMoney(modal.querySelector("#pcRowPrice")?.value));
    const value = Math.max(0, parseMoney(modal.querySelector("#pcDiscValue")?.value));

    let discountAmt = 0;
    if (basis === "amount") discountAmt = value;
    else discountAmt = (price * clampNumber(value, 0, 100)) / 100;

    const effective = Math.max(0, price - discountAmt);

    const calcValue = modal.querySelector("#pcCalcValue");
    const calcDiscAmt = modal.querySelector("#pcCalcDiscountAmt");
    const calcEff = modal.querySelector("#pcCalcEffectivePrice");
    const discPerPcs = modal.querySelector("#pcDiscPerPcs");

    if (calcValue) calcValue.value = basis === "amount" ? `₹${value.toFixed(2)}` : `${clampNumber(value, 0, 100).toFixed(2)}%`;
    if (calcDiscAmt) calcDiscAmt.value = `₹${discountAmt.toFixed(2)}`;
    if (calcEff) calcEff.value = `₹${effective.toFixed(2)}`;
    if (discPerPcs) discPerPcs.value = `₹${discountAmt.toFixed(2)}`;
  }

  function createPrintModal() {
    if (document.getElementById("pcPrintModal")) return;

    const modal = document.createElement("div");
    modal.id = "pcPrintModal";
    modal.className = "busy-modal";
    modal.innerHTML = `
      <div class="busy-modal-dialog print-modal-dialog" role="dialog" aria-modal="true" aria-label="Invoice Printing">
        <div class="busy-modal-title print-modal-title">
          <span>Invoice Printing</span>
          <button type="button" class="busy-modal-x" data-action="cancel" aria-label="Close">×</button>
        </div>
        <div class="busy-modal-body print-modal-body">
          <div class="print-modal-grid">
            <div>
              <div class="print-modal-field">
                <div class="busy-modal-label">Format</div>
                <select id="pcPrintFormat" class="busy-modal-select">
                  <option value="A4" selected>A4 (Full Page)</option>
                  <option value="A5">A5 (Half Page)</option>
                </select>
              </div>
              <div class="print-modal-field">
                <div class="busy-modal-label">No. of copies</div>
                <input type="number" min="1" step="1" id="pcPrintCopies" class="busy-modal-input" value="1" />
              </div>
              <div class="print-modal-field">
                <div class="busy-modal-label">Print Title</div>
                <input type="text" id="pcPrintCopyTitle" class="busy-modal-input" placeholder="Optional" />
              </div>
              <div class="busy-modal-hint">[ Esc - Quit ]  [ F2 - Print ]  [ F3 - Preview ]</div>
            </div>
            <div>
              <div class="print-preview-box" id="pcPrintPreviewBox" data-tab="text">
                <div class="print-preview-title">
                  <span>Preview</span>
                  <div class="print-preview-tabs" role="tablist" aria-label="Preview tabs">
                    <button type="button" class="ppt-btn active" data-preview-tab="text">Text</button>
                    <button type="button" class="ppt-btn" data-preview-tab="invoice">Invoice</button>
                  </div>
                </div>
                <div class="print-preview-body">
                  <pre id="pcPrintPreviewText" class="print-preview-pre">-</pre>
                  <iframe id="pcPrintPreviewFrame" class="print-preview-frame" title="Invoice Preview"></iframe>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="busy-modal-actions print-modal-actions">
          <button type="button" class="busy-modal-btn primary" data-action="print">Print (F2)</button>
          <button type="button" class="busy-modal-btn" data-action="preview">Preview (F3)</button>
          <button type="button" class="busy-modal-btn" data-action="download">Download</button>
          <button type="button" class="busy-modal-btn" data-action="whatsapp">WhatsApp</button>
          <button type="button" class="busy-modal-btn" data-action="email">Email</button>
          <button type="button" class="busy-modal-btn" data-action="sms">SMS</button>
          <button type="button" class="busy-modal-btn" data-action="close">Close</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    trapModalFocus(modal);

    modal.addEventListener("click", (e) => {
      if (e.target === modal) closePrintModal();
      const tabBtn = e.target.closest("button[data-preview-tab]");
      if (tabBtn) {
        setPrintPreviewTab(tabBtn.dataset.previewTab);
        return;
      }
      const btn = e.target.closest("button[data-action]");
      if (!btn) return;
      const action = btn.dataset.action;
      if (action === "cancel" || action === "close") closePrintModal();
      else if (action === "print") runPrintFlow({ autoPrint: true });
      else if (action === "preview") runPrintFlow({ autoPrint: false });
      else if (action === "download") downloadOrderHtml();
      else if (action === "whatsapp") shareOrder("whatsapp");
      else if (action === "email") shareOrder("email");
      else if (action === "sms") shareOrder("sms");
    });

    modal.querySelector("#pcPrintFormat")?.addEventListener("change", updatePrintPreview);
    modal.querySelector("#pcPrintCopies")?.addEventListener("input", updatePrintPreview);
    modal.querySelector("#pcPrintCopyTitle")?.addEventListener("input", updatePrintPreview);
  }

  function createBillSundryModal() {
    if (document.getElementById("pcSundryModal")) return;

    const modal = document.createElement("div");
    modal.id = "pcSundryModal";
    modal.className = "busy-modal";
    modal.innerHTML = `
      <div class="busy-modal-dialog sundry-modal-dialog" role="dialog" aria-modal="true" aria-label="Bill Sundry & Narration">
        <div class="busy-modal-title sundry-modal-title">
          <span>Bill Sundry & Narration</span>
          <button type="button" class="busy-modal-x" data-action="cancel" aria-label="Close">×</button>
        </div>
        <div class="busy-modal-body sundry-modal-body">
          <div class="sundry-modal-grid">
            <div class="busy-tax-summary">
              <div class="panel-title">Tax Summary</div>
              <div class="tax-grid-head">
                <span>Tax Rate</span>
                <span>Taxable Amt.</span>
                <span>GST</span>
              </div>
              <div class="tax-grid-body" id="pcTaxSummaryGrid"></div>
              <div class="tax-total" id="pcTaxSummaryTotals">-</div>
              <div class="tax-total" id="pcSundryTotals">-</div>
              <div class="tax-total" id="pcSundryGrand">-</div>
            </div>
            <div class="busy-bill-sundry">
              <div class="panel-title">Bill Sundry</div>
              <datalist id="pcSundryList">
                <option value="Expenses"></option>
                <option value="Transport"></option>
                <option value="Round Off (+)"></option>
                <option value="Round Off (-)"></option>
                <option value="Discount"></option>
                <option value="TDS"></option>
                <option value="Tax"></option>
                <option value="CGST"></option>
                <option value="SGST"></option>
                <option value="Cash Pay"></option>
                <option value="Online Pay"></option>
              </datalist>
              <table class="busy-sundry-table" id="pcSundryTable" aria-label="Bill Sundry table">
                <thead>
                  <tr>
                    <th style="width:48px">S.N.</th>
                    <th style="width:180px">Bill Sundry</th>
                    <th>Narration</th>
                    <th style="width:80px">@</th>
                    <th style="width:140px">Amount (Rs.)</th>
                  </tr>
                </thead>
                <tbody></tbody>
              </table>
            </div>
          </div>
          <div class="busy-modal-hint">[ Esc - Quit ]  [ F2 - Done ]  [ ↓ - Next Row ]  [ Enter (Amount) - Done ]</div>
        </div>
        <div class="busy-modal-actions">
          <button type="button" class="busy-modal-btn primary" data-action="apply">Done (F2)</button>
          <button type="button" class="busy-modal-btn" data-action="cancel">Cancel</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    trapModalFocus(modal);

    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeBillSundryModal();
      const btn = e.target.closest("button[data-action]");
      if (!btn) return;
      if (btn.dataset.action === "apply") applyBillSundryFromModal();
      if (btn.dataset.action === "cancel") closeBillSundryModal();
    });

    // Excel-like navigation inside the table.
    modal.addEventListener("keydown", (e) => {
      const field = e.target.closest("input,select,textarea");
      if (!field) return;
      const row = field.closest("tr");
      if (!row) return;

      const col = field.dataset.col || "";

      const rowIsEmpty = (r) => {
        if (!r) return true;
        const inputs = Array.from(r.querySelectorAll("input,select,textarea"));
        return inputs.every((el) => String(el.value || "").trim() === "");
      };

      const rowHasAnyData = (r) => {
        if (!r) return false;
        const inputs = Array.from(r.querySelectorAll("input,select,textarea"));
        return inputs.some((el) => String(el.value || "").trim() !== "");
      };

      if (e.key === "Enter") {
        // Quick exit: if user is on Amount column and next row is blank, treat Enter as Done.
        if (col === "amount" && rowHasAnyData(row)) {
          const nextRow = row.nextElementSibling;
          if (!nextRow || rowIsEmpty(nextRow)) {
            e.preventDefault();
            applyBillSundryFromModal();
            return;
          }
        }

        e.preventDefault();
        focusSundryField(row, col, 1);
        return;
      }

      if (e.key === "ArrowDown") {
        e.preventDefault();
        focusSundryField(row, col, 1);
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        focusSundryField(row, col, -1);
      }
    });

    modal.addEventListener("input", (e) => {
      if (!e.target.closest("#pcSundryTable")) return;
      updateBillSundryModalSummary();
    });
  }

  function buildSundryRow() {
    const tr = document.createElement("tr");
    tr.className = "sundry-row";
    tr.innerHTML = `
      <td class="c"><span class="sundry-sno"></span></td>
      <td><input type="text" class="sundry-name" data-col="name" list="pcSundryList" /></td>
      <td><input type="text" class="sundry-narration" data-col="narration" /></td>
      <td><input type="text" class="sundry-rate" data-col="rate" /></td>
      <td><input type="number" step="0.01" class="sundry-amount" data-col="amount" /></td>
    `;
    return tr;
  }

  function ensureSundryRows(desiredCount) {
    const tbody = document.querySelector("#pcSundryTable tbody");
    if (!tbody) return;
    while (tbody.querySelectorAll("tr.sundry-row").length < desiredCount) {
      tbody.appendChild(buildSundryRow());
    }
    Array.from(tbody.querySelectorAll("tr.sundry-row")).forEach((row, idx) => {
      const sno = row.querySelector(".sundry-sno");
      if (sno) sno.textContent = String(idx + 1);
    });
  }

  function focusSundryField(currentRow, col, direction) {
    const tbody = currentRow?.closest?.("tbody");
    if (!tbody) return;

    let next = direction > 0 ? currentRow.nextElementSibling : currentRow.previousElementSibling;
    if (!next && direction > 0) {
      ensureSundryRows(tbody.querySelectorAll("tr.sundry-row").length + 1);
      next = currentRow.nextElementSibling;
    }
    if (!next) return;

    const safeCol = typeof CSS !== "undefined" && CSS.escape ? CSS.escape(col) : col;
    const selector = col ? `[data-col="${safeCol}"]` : "input,select,textarea";
    const field = next.querySelector(selector) || next.querySelector("input,select,textarea");
    if (field) {
      field.focus();
      field.select?.();
    }
  }

  function readBillSundryFromModal() {
    const tbody = document.querySelector("#pcSundryTable tbody");
    if (!tbody) return [];
    return Array.from(tbody.querySelectorAll("tr.sundry-row")).map((row) => ({
      name: row.querySelector(".sundry-name")?.value || "",
      narration: row.querySelector(".sundry-narration")?.value || "",
      rate: row.querySelector(".sundry-rate")?.value || "",
      amount: row.querySelector(".sundry-amount")?.value || "",
    }));
  }

  function fillBillSundryModal(lines) {
    const data = normalizeBillSundryLines(lines);
    ensureSundryRows(Math.max(10, data.length + 2));

    const tbody = document.querySelector("#pcSundryTable tbody");
    if (!tbody) return;

    Array.from(tbody.querySelectorAll("tr.sundry-row")).forEach((row, idx) => {
      const line = data[idx];
      row.querySelector(".sundry-name").value = line?.name || "";
      row.querySelector(".sundry-narration").value = line?.narration || "";
      row.querySelector(".sundry-rate").value = line?.rate || "";
      row.querySelector(".sundry-amount").value = line ? String(line.amount || "") : "";
    });
  }

  function updateBillSundryModalSummary() {
    const grid = document.getElementById("pcTaxSummaryGrid");
    const totals = document.getElementById("pcTaxSummaryTotals");
    const sundryTotals = document.getElementById("pcSundryTotals");
    const grandEl = document.getElementById("pcSundryGrand");
    if (!grid || !totals || !sundryTotals || !grandEl) return;

    const snapshot = getOrderSnapshot();
    const draftLines = normalizeBillSundryLines(readBillSundryFromModal());
    const sundryTotal = draftLines.reduce((sum, l) => sum + (Number.isFinite(l.amount) ? l.amount : 0), 0);

    const rate = snapshot.gstEnabled ? snapshot.gstRate : 0;
    const gst = snapshot.gstEnabled ? (snapshot.subtotal * rate) / 100 : 0;
    const cgst = gst / 2;
    const sgst = gst / 2;

    grid.innerHTML = `
      <span>${rate ? `${rate}%` : "0%"}</span>
      <span>${snapshot.subtotal.toFixed(2)}</span>
      <span>${gst.toFixed(2)}</span>
    `;

    totals.textContent = `CGST: ${cgst.toFixed(2)}   SGST: ${sgst.toFixed(2)}`;
    sundryTotals.textContent = `Bill Sundry: ${sundryTotal.toFixed(2)}`;
    grandEl.textContent = `Grand Total: ${(snapshot.subtotal + gst + sundryTotal).toFixed(2)}`;
  }

  function openBillSundryModal() {
    createBillSundryModal();
    const modal = document.getElementById("pcSundryModal");
    if (!modal) return;
    modal.style.display = "flex";
    fillBillSundryModal(billSundryLines);
    updateBillSundryModalSummary();
    setTimeout(() => modal.querySelector(".sundry-name")?.focus(), 0);
  }

  function closeBillSundryModal() {
    const modal = document.getElementById("pcSundryModal");
    if (!modal) return;
    modal.style.display = "none";
    const row = getActiveRow();
    row?.querySelector?.(".product-search")?.focus?.();
  }

  function applyBillSundryFromModal() {
    billSundryLines = normalizeBillSundryLines(readBillSundryFromModal());
    persistBillSundryToStorage();
    syncBillSundryHiddenInput();
    closeBillSundryModal();
    calculateTotals();
    updatePrintPreview();
    // After applying, move focus to the bottom function-key bar (F1 first) for keyboard-only flow.
    setTimeout(() => focusFinishAction(), 0);
  }

  function getOrderSnapshot() {
    const orderTypeSel = document.getElementById("orderType");
    const orderType = orderTypeSel?.value || "";
    const orderTypeLabel = orderTypeSel?.selectedOptions?.[0]?.textContent?.trim() || "Order";

    const partyName = document.getElementById("partySearch")?.value?.trim() || "-";
    const gstEnabled = document.getElementById("pcGstEnabled")?.checked ?? true;
    const gstRate = clampNumber(parseMoney(document.getElementById("pcGstRate")?.value), 0, 28);

    const rows = Array.from(document.querySelectorAll("#orderBody tr.item-row"));
    const items = rows
      .map((row) => {
        const select = row.querySelector(".product");
        const id = select?.value || "";
        if (!id) return null;

        const name =
          row.querySelector(".product-search")?.value?.trim() ||
          select?.selectedOptions?.[0]?.textContent?.trim() ||
          "-";
        const qty = Math.max(0, parseMoney(row.querySelector(".qty")?.value));
        const price = Math.max(0, parseMoney(row.querySelector(".price")?.value));
        const amount = Math.max(0, parseMoney(row.querySelector(".amount")?.value));
        const dp = clampNumber(parseMoney(row.querySelector("input.discount_percent")?.value), 0, 100);
        const da = Math.max(0, parseMoney(row.querySelector("input.discount_amount")?.value));
        return { id, name, qty, price, amount, discountPercent: dp, discountAmount: da };
      })
      .filter(Boolean);

    const subtotal = items.reduce((sum, it) => sum + (Number.isFinite(it.amount) ? it.amount : 0), 0);
    const tax = gstEnabled ? (subtotal * gstRate) / 100 : 0;
    const sundryLines = normalizeBillSundryLines(billSundryLines);
    const sundryTotal = sundryLines.reduce((sum, l) => sum + (Number.isFinite(l.amount) ? l.amount : 0), 0);
    const grandTotal = subtotal + tax + sundryTotal;

    return {
      orderType,
      orderTypeLabel,
      partyName,
      narration: document.getElementById("pcNarration")?.value?.trim() || "",
      gstEnabled,
      gstRate,
      items,
      subtotal,
      tax,
      sundryLines,
      sundryTotal,
      grandTotal,
      generatedAt: new Date(),
    };
  }

  function buildShareText(snapshot) {
    const lines = [];
    lines.push(`${snapshot.orderTypeLabel}`);
    lines.push(`Party: ${snapshot.partyName}`);
    lines.push(`Date: ${snapshot.generatedAt.toLocaleString()}`);
    lines.push(`Items: ${snapshot.items.length}`);
    lines.push(`Total: ${snapshot.grandTotal.toFixed(2)}`);
    if (snapshot.sundryLines?.length) lines.push(`Bill Sundry: ${snapshot.sundryTotal.toFixed(2)}`);
    if (snapshot.narration) lines.push(`Narration: ${snapshot.narration}`);
    lines.push("");
    snapshot.items.slice(0, 18).forEach((it, idx) => {
      lines.push(`${idx + 1}. ${it.name}  x${it.qty}  @${it.price.toFixed(2)}  = ${it.amount.toFixed(2)}`);
    });
    if (snapshot.items.length > 18) lines.push(`...and ${snapshot.items.length - 18} more`);
    return lines.join("\n");
  }

  function updatePrintPreview() {
    const el = document.getElementById("pcPrintPreviewText");
    if (!el) return;
    const snapshot = getOrderSnapshot();
    el.textContent = buildShareText(snapshot);
  }

  function setPrintPreviewTab(tab) {
    const box = document.getElementById("pcPrintPreviewBox");
    if (!box) return;
    const next = tab === "invoice" ? "invoice" : "text";
    box.dataset.tab = next;

    box.querySelectorAll("button[data-preview-tab]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.previewTab === next);
    });
  }

  function getPrintOptionsFromModal() {
    const format = document.getElementById("pcPrintFormat")?.value || "A4";
    const copies = document.getElementById("pcPrintCopies")?.value || "1";
    const title = document.getElementById("pcPrintCopyTitle")?.value || "";
    return { format, copies, title };
  }

  function buildPrintHtml(snapshot, options = {}) {
    const format = options.format || "A4";
    const copies = clampNumber(Number.parseInt(options.copies || "1", 10) || 1, 1, 20);
    const title = String(options.title || "").trim();

    const pageSizeCss = format === "A5" ? "A5" : "A4";
    const safeTitle = escapeHtml(title);

    const pages = [];
    for (let c = 1; c <= copies; c++) {
      const copyLabel = safeTitle
        ? `${safeTitle}${copies > 1 ? ` - Copy ${c}` : ""}`
        : copies > 1
          ? `Copy ${c}`
          : "";
      pages.push(`
        <section class="sheet">
          <div class="hdr">
            <div class="hleft">
              <div class="h1">${escapeHtml(snapshot.orderTypeLabel || "Order")}</div>
              <div class="hmeta">Party: ${escapeHtml(snapshot.partyName)}</div>
              <div class="hmeta">Date: ${escapeHtml(snapshot.generatedAt.toLocaleString())}</div>
              ${snapshot.narration ? `<div class="hmeta">Narration: ${escapeHtml(snapshot.narration)}</div>` : ""}
            </div>
            <div class="hright">
              ${copyLabel ? `<div class="copy">${copyLabel}</div>` : ""}
              <div class="tot">Grand Total: ${snapshot.grandTotal.toFixed(2)}</div>
            </div>
          </div>

          <table class="tbl">
            <thead>
              <tr>
                <th style="width:40px">#</th>
                <th>Item</th>
                <th style="width:70px">Qty</th>
                <th style="width:90px">Price</th>
                <th style="width:110px">Amount</th>
              </tr>
            </thead>
            <tbody>
              ${snapshot.items
                .map(
                  (it, idx) => `
                    <tr>
                      <td class="c">${idx + 1}</td>
                      <td>${escapeHtml(it.name)}</td>
                      <td class="r">${Number.isFinite(it.qty) ? it.qty : 0}</td>
                      <td class="r">${Number.isFinite(it.price) ? it.price.toFixed(2) : "0.00"}</td>
                      <td class="r">${Number.isFinite(it.amount) ? it.amount.toFixed(2) : "0.00"}</td>
                    </tr>
                  `
                )
                .join("")}
            </tbody>
          </table>

          ${snapshot.sundryLines?.length
            ? `
              <table class="sundry">
                <thead>
                  <tr>
                    <th style="width:40px">#</th>
                    <th>Bill Sundry</th>
                    <th>Narration</th>
                    <th style="width:110px">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  ${snapshot.sundryLines
                    .map(
                      (l, idx) => `
                        <tr>
                          <td class="c">${idx + 1}</td>
                          <td>${escapeHtml(l.name || "-")}${l.rate ? ` <span class="muted">@ ${escapeHtml(l.rate)}</span>` : ""}</td>
                          <td>${escapeHtml(l.narration || "")}</td>
                          <td class="r">${Number.isFinite(l.amount) ? l.amount.toFixed(2) : "0.00"}</td>
                        </tr>
                      `
                    )
                    .join("")}
                </tbody>
              </table>
            `
            : ""}

          <div class="sum">
            <div class="row"><span>Subtotal</span><span>${snapshot.subtotal.toFixed(2)}</span></div>
            <div class="row"><span>GST</span><span>${snapshot.gstEnabled ? `${snapshot.tax.toFixed(2)} (${snapshot.gstRate}%)` : "0.00 (Off)"}</span></div>
            ${snapshot.sundryLines?.length ? `<div class="row"><span>Bill Sundry</span><span>${snapshot.sundryTotal.toFixed(2)}</span></div>` : ""}
            <div class="row grand"><span>Grand Total</span><span>${snapshot.grandTotal.toFixed(2)}</span></div>
          </div>
        </section>
      `);
    }

    return `<!doctype html>
      <html>
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Order Print</title>
        <style>
          @page { size: ${pageSizeCss}; margin: 10mm; }
          * { box-sizing: border-box; }
          body { font-family: Tahoma, Arial, sans-serif; color: #111; margin: 0; }
          .sheet { page-break-after: always; padding: 0; }
          .hdr { display: flex; justify-content: space-between; gap: 12px; border-bottom: 2px solid #444; padding: 0 0 8px 0; margin-bottom: 10px; }
          .h1 { font-size: 18px; font-weight: 900; }
          .hmeta { font-size: 12px; margin-top: 2px; }
          .copy { font-weight: 900; font-size: 12px; text-align: right; }
          .tot { font-weight: 900; font-size: 14px; margin-top: 6px; text-align: right; }
          .tbl { width: 100%; border-collapse: collapse; }
          .tbl th, .tbl td { border: 1px solid #666; padding: 6px; font-size: 12px; }
          .tbl th { background: #f0f0f0; text-transform: uppercase; font-size: 11px; }
          .sundry { width: 100%; border-collapse: collapse; margin-top: 10px; }
          .sundry th, .sundry td { border: 1px solid #666; padding: 6px; font-size: 12px; }
          .sundry th { background: #f7f7ff; text-transform: uppercase; font-size: 11px; }
          .muted { color: #555; font-size: 11px; font-weight: 800; }
          .r { text-align: right; }
          .c { text-align: center; }
          .sum { margin-top: 12px; display: grid; gap: 4px; width: min(320px, 100%); margin-left: auto; }
          .sum .row { display: flex; justify-content: space-between; border: 1px solid #666; padding: 6px; font-weight: 800; }
          .sum .grand { background: #f7f7ff; font-size: 13px; }
        </style>
      </head>
      <body>
        ${pages.join("")}
      </body>
      </html>`;
  }

  function openHtmlWindow(html, { autoPrint } = {}) {
    const w = window.open("", "_blank", "noopener,noreferrer,width=980,height=720");
    if (!w) return false;
    w.document.open();
    w.document.write(html);
    w.document.close();
    w.focus();
    if (autoPrint) setTimeout(() => w.print?.(), 250);
    return true;
  }

  function runPrintFlow({ autoPrint }) {
    const snapshot = getOrderSnapshot();
    if (!snapshot.items.length) {
      alert("No items in the order to print.");
      return;
    }
    const options = getPrintOptionsFromModal();
    const html = buildPrintHtml(snapshot, options);
    const frame = document.getElementById("pcPrintPreviewFrame");
    if (frame) {
      setPrintPreviewTab("invoice");

      let printed = false;
      const triggerPrint = () => {
        if (!autoPrint || printed) return;
        printed = true;
        try {
          frame.contentWindow?.focus?.();
          frame.contentWindow?.print?.();
        } catch (e) {}
      };

      frame.onload = () => setTimeout(triggerPrint, 150);
      frame.srcdoc = html;
      // Fallback if onload doesn't fire reliably.
      setTimeout(triggerPrint, 650);
      return;
    }

    if (!openHtmlWindow(html, { autoPrint })) {
      alert("Popup blocked. Please allow popups for preview/print.");
    }
  }

  function downloadText(filename, text, mime = "text/plain") {
    const blob = new Blob([text], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  function downloadOrderHtml() {
    const snapshot = getOrderSnapshot();
    if (!snapshot.items.length) {
      alert("No items in the order to download.");
      return;
    }
    const options = getPrintOptionsFromModal();
    const html = buildPrintHtml(snapshot, options);
    const dateTag = snapshot.generatedAt.toISOString().slice(0, 10);
    downloadText(`order_${dateTag}.html`, html, "text/html");
  }

  function shareOrder(channel) {
    const snapshot = getOrderSnapshot();
    const text = buildShareText(snapshot);

    if (channel === "whatsapp") {
      const url = `https://wa.me/?text=${encodeURIComponent(text)}`;
      window.open(url, "_blank", "noopener");
      return;
    }
    if (channel === "email") {
      const subject = encodeURIComponent(`Order - ${snapshot.partyName}`);
      const body = encodeURIComponent(text);
      window.location.href = `mailto:?subject=${subject}&body=${body}`;
      return;
    }
    if (channel === "sms") {
      const body = encodeURIComponent(text);
      window.location.href = `sms:?&body=${body}`;
    }
  }

  function openPrintModal() {
    createPrintModal();
    updatePrintPreview();
    setPrintPreviewTab("text");
    const modal = document.getElementById("pcPrintModal");
    if (!modal) return;
    modal.style.display = "flex";
    setTimeout(() => document.getElementById("pcPrintFormat")?.focus(), 0);
  }

  function closePrintModal() {
    const modal = document.getElementById("pcPrintModal");
    if (!modal) return;
    modal.style.display = "none";
    const row = getActiveRow();
    row?.querySelector?.(".product-search")?.focus?.();
  }

  function handleAction(action) {
    if (action === "help") {
      if (typeof window.showKeyboardHelp === "function") window.showKeyboardHelp();
      return;
    }
    if (action === "party") return focusFirstVisible("#partySearch, #partySelect");
    if (action === "item") return focusFirstVisible("#orderBody .item-row .product-search");
    if (action === "addRow") return ensureRows(document.querySelectorAll("#orderBody tr.item-row").length + 1);
    if (action === "discount") return openDiscountModal();
    if (action === "sundry") return openBillSundryModal();
    if (action === "print") return openPrintModal();
    if (action === "save") {
      const form = document.getElementById("orderForm");
      if (!form) return;
      if (form.requestSubmit) form.requestSubmit();
      else form.submit();
      return;
    }
    if (action === "quit") {
      // Best effort: go back
      window.history.back();
    }
  }

  function showKeyboardHelp() {
    const modal = document.getElementById("keyboardHelp");
    if (!modal) return;
    modal.style.display = "flex";
  }

  function hideKeyboardHelp() {
    const modal = document.getElementById("keyboardHelp");
    if (!modal) return;
    modal.style.display = "none";
  }

  function renderSundryList() {
    const tbody = document.getElementById("sundryListBody");
    const container = document.getElementById("sundryListContainer");
    if (!tbody || !container) return;

    const lines = normalizeBillSundryLines(billSundryLines);
    tbody.innerHTML = "";

    if (lines.length === 0) {
      container.style.display = "none";
      return;
    }

    container.style.display = "block";

    lines.forEach((line, index) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="fw-bold">${escapeHtml(line.name)}</td>
        <td class="text-end fw-bold">₹ ${(Number.isFinite(line.amount) ? line.amount : 0).toFixed(2)}</td>
        <td class="text-center">
          <button type="button" class="btn btn-sm btn-danger remove-sundry-btn" data-index="${index}" aria-label="Delete ${escapeHtml(line.name)}" title="Delete (D)">✕</button>
        </td>
      `;
      tbody.appendChild(tr);

      const removeBtn = tr.querySelector(".remove-sundry-btn");
      removeBtn.addEventListener("click", () => {
        billSundryLines.splice(index, 1);
        persistBillSundryToStorage();
        syncBillSundryHiddenInput();
        calculateTotals();
        renderSundryList();
      });
    });
  }

  function installKeyboardShortcuts() {
    document.addEventListener("keydown", (e) => {
      const modalOpen = document.getElementById("pcDiscountModal")?.style?.display === "flex";
      const printOpen = document.getElementById("pcPrintModal")?.style?.display === "flex";
      const sundryOpen = document.getElementById("pcSundryModal")?.style?.display === "flex";
      const helpOpen = document.getElementById("keyboardHelp")?.style?.display === "flex";

      if (modalOpen) {
        const modal = document.getElementById("pcDiscountModal");
        if (e.key === "Escape") {
          e.preventDefault();
          closeDiscountModal();
          return;
        }
        if (e.key === "F2") {
          e.preventDefault();
          applyDiscountFromModal();
          return;
        }
        if (e.key === "Tab") {
          e.preventDefault();
          focusNextInModal(modal, e.shiftKey ? -1 : 1);
          return;
        }
        if (e.key === "Enter") {
          const active = document.activeElement;
          const inField =
            active &&
            modal &&
            modal.contains(active) &&
            (active.tagName === "INPUT" || active.tagName === "SELECT" || active.tagName === "TEXTAREA");
          if (inField) {
            e.preventDefault();
            focusNextInModal(modal, 1);
            return;
          }
          e.preventDefault();
          applyDiscountFromModal();
          return;
        }
        return;
      }

      if (printOpen) {
        const modal = document.getElementById("pcPrintModal");
        if (e.key === "Escape") {
          e.preventDefault();
          closePrintModal();
          return;
        }
        if (e.key === "F2") {
          e.preventDefault();
          runPrintFlow({ autoPrint: true });
          return;
        }
        if (e.key === "F3") {
          e.preventDefault();
          runPrintFlow({ autoPrint: false });
          return;
        }
        if (e.key === "Tab") {
          e.preventDefault();
          focusNextInModal(modal, e.shiftKey ? -1 : 1);
          return;
        }
        if (e.key === "Enter") {
          const active = document.activeElement;
          const inField =
            active &&
            modal &&
            modal.contains(active) &&
            (active.tagName === "INPUT" || active.tagName === "SELECT" || active.tagName === "TEXTAREA");
          if (inField) {
            e.preventDefault();
            focusNextInModal(modal, 1);
            return;
          }
          return;
        }
        return;
      }

      if (sundryOpen) {
        if (e.key === "Escape") {
          e.preventDefault();
          closeBillSundryModal();
          return;
        }
        if (e.key === "F2") {
          e.preventDefault();
          applyBillSundryFromModal();
          return;
        }
        return;
      }

      if (helpOpen) {
        if (e.key === "Escape") {
          e.preventDefault();
          hideKeyboardHelp();
        }
        return;
      }

      // Don't hijack browser zoom shortcuts (Ctrl +/- / 0). Use Ctrl+Alt instead for UI zoom.
      if (e.ctrlKey && e.altKey && (e.key === "+" || e.key === "=" || e.code === "NumpadAdd")) {
        e.preventDefault();
        adjustZoom(5);
        return;
      }
      if (e.ctrlKey && e.altKey && (e.key === "-" || e.code === "NumpadSubtract")) {
        e.preventDefault();
        adjustZoom(-5);
        return;
      }
      if (e.ctrlKey && e.altKey && (e.key === "0" || e.code === "Numpad0")) {
        e.preventDefault();
        applyZoom(100);
        return;
      }

      if (e.key === "F1") {
        e.preventDefault();
        showKeyboardHelp();
      }
      if (e.key === "F2") {
        e.preventDefault();
        handleAction("party");
      }
      if (e.key === "F3") {
        e.preventDefault();
        handleAction("item");
      }
      if (e.key === "F4") {
        e.preventDefault();
        handleAction("addRow");
      }
      if (e.key === "F5") {
        e.preventDefault();
        handleAction("save");
      }
      if (e.key === "F7") {
        e.preventDefault();
        handleAction("print");
      }
      if (e.key === "F8") {
        e.preventDefault();
        handleAction("sundry");
      }
      if (e.key === "F9") {
        e.preventDefault();
        handleAction("discount");
      }
      if (e.key === "F10") {
        e.preventDefault();
        focusFinishAction();
      }
      if (e.ctrlKey && e.key === "Enter") {
        e.preventDefault();
        handleAction("save");
      }

      // Delete key on focused sundry button
      if (e.key === "Delete" || (e.key === "d" && !e.ctrlKey && !e.altKey && !e.shiftKey && document.activeElement?.classList?.contains("remove-sundry-btn"))) {
        const focusedBtn = document.activeElement;
        if (focusedBtn?.classList?.contains("remove-sundry-btn")) {
          e.preventDefault();
          focusedBtn.click();
        }
      }
      if (e.key === "Escape") {
        // Busy-like behavior: clear field
        const active = document.activeElement;
        if (active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA")) {
          // If product dropdown is open, close it (don't clear text).
          if (active.classList.contains("product-search")) {
            const row = active.closest("tr.item-row");
            const dd = row?.querySelector(".product-dropdown");
            const open = dd && dd.style.display !== "none" && dd.innerHTML.trim().length > 0;
            if (open) {
              e.preventDefault();
              hideDropdown(row);
              return;
            }
          }

          e.preventDefault();
          active.value = "";
          if (active.classList.contains("product-search")) {
            const row = active.closest("tr.item-row");
            if (row) {
              const select = row.querySelector(".product");
              if (select) select.value = "";
              calculateTotals();
            }
          }
        }
      }
      if (e.altKey && (e.key === "n" || e.key === "N")) {
        e.preventDefault();
        document.getElementById("pcNarration")?.focus();
      }

      if (e.ctrlKey && (e.key === "p" || e.key === "P")) {
        e.preventDefault();
        handleAction("print");
      }
    });
  }

  function wirePartyPicker(partiesIndex) {
    const input = document.getElementById("partySearch");
    const dropdown = document.getElementById("partyDropdown");
    if (!input || !dropdown) return;

    dropdown.classList.add("busy-dd");

    const wrap = input.parentElement;
    if (wrap) {
      wrap.style.position = "relative";
      dropdown.style.position = "absolute";
      dropdown.style.left = "0";
      dropdown.style.right = "0";
    }

    function positionDropdown() {
      if (!wrap) return;
      dropdown.style.top = `${input.offsetTop + input.offsetHeight + 2}px`;
    }

    positionDropdown();
    window.addEventListener("resize", positionDropdown);

    input.addEventListener("input", () => {
      const matches = matchParties(partiesIndex, input.value);
      renderPartyDropdown(matches);
      positionDropdown();
    });

    input.addEventListener("keydown", (e) => {
      const open = dropdown.style.display !== "none" && dropdown.innerHTML.trim().length > 0;

      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        e.stopPropagation();

        if (!open) {
          const matches = matchParties(partiesIndex, input.value);
          renderPartyDropdown(matches);
          positionDropdown();
        }

        const current = parseInt(dropdown.dataset.activeIndex || "0", 10);
        setActivePartyIndex(e.key === "ArrowDown" ? current + 1 : current - 1);
        return;
      }

      if (e.key === "Escape" && open) {
        e.preventDefault();
        e.stopPropagation();
        hidePartyDropdown();
        return;
      }

      if (e.key === "Enter" || e.key === "Tab") {
        if (open) {
          e.preventDefault();
          e.stopPropagation();
          pickActiveParty();
          return;
        }

        // If already selected, move on.
        const select = document.getElementById("partySelect");
        if (select && select.value) {
          e.preventDefault();
          e.stopPropagation();
          focusFirstVisible("#orderBody .item-row .product-search");
          return;
        }

        // If one clear match, select it.
        const matches = matchParties(partiesIndex, input.value);
        if (matches.length === 1) {
          e.preventDefault();
          e.stopPropagation();
          applyParty(matches[0].id);
          return;
        }
      }
    });

    dropdown.addEventListener("click", (e) => {
      const btn = e.target.closest(".busy-dd-item");
      if (!btn) return;
      applyParty(btn.dataset.id);
    });

    document.addEventListener("click", (e) => {
      if (e.target === input || dropdown.contains(e.target)) return;
      hidePartyDropdown();
    });
  }

  function wireTableInteractions(productsIndex) {
    const tbody = document.getElementById("orderBody");
    if (!tbody) return;

    tbody.addEventListener("change", (e) => {
      const row = e.target.closest("tr.item-row");
      if (!row) return;

      if (e.target.classList && e.target.classList.contains("product")) {
        const select = e.target;
        const selected = select.selectedOptions?.[0];

        const productSearch = row.querySelector(".product-search");
        if (productSearch && selected) productSearch.value = selected.textContent?.trim() || "";

        const unit = (selected?.dataset?.unit || "").trim();
        const unitInput = row.querySelector(".unit");
        if (unitInput) unitInput.value = unit;

        const priceInput = row.querySelector(".price");
        const currentPrice = parseMoney(priceInput?.value);
        const autoPrice = parseMoney(selected?.dataset?.price);
        if (priceInput && autoPrice && (!currentPrice || currentPrice <= 0)) {
          priceInput.value = autoPrice.toFixed(2);
        }

        hideDropdown(row);
        calculateTotals();
        updateItemPanel(row);
      }
    });

    tbody.addEventListener("click", (e) => {
      const btn = e.target.closest(".remove-btn");
      if (btn) {
        const row = btn.closest("tr.item-row");
        if (row) {
          clearRow(row);
          calculateTotals();
          row.querySelector(".product-search")?.focus();
        }
        return;
      }

      const ddItem = e.target.closest(".busy-dd-item");
      if (ddItem) {
        const row = ddItem.closest("tr.item-row");
        if (row) applyProductToRow(row, ddItem.dataset.id);
      }
    });

    tbody.addEventListener("input", (e) => {
      const row = e.target.closest("tr.item-row");
      if (!row) return;
      if (e.target.classList.contains("amount")) {
        updatePriceFromAmount(row);
        calculateTotals();
        return;
      }
      if (e.target.classList.contains("qty") || e.target.classList.contains("price")) {
        calculateTotals();
      }
    });

    tbody.addEventListener("keydown", (e) => {
      const row = e.target.closest("tr.item-row");
      if (!row) return;

      if (e.target.classList.contains("product-search")) {
        if (e.ctrlKey && e.key === "Enter") {
          e.preventDefault();
          e.stopPropagation();
          handleAction("save");
          return;
        }

        const dd = row.querySelector(".product-dropdown");
        const open = dd && dd.style.display !== "none" && dd.innerHTML.trim().length > 0;

        if (open && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
          e.preventDefault();
          const current = parseInt(dd.dataset.activeIndex || "0", 10);
          setActiveDropdownIndex(row, e.key === "ArrowDown" ? current + 1 : current - 1);
          return;
        }

        if (!open && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
          e.preventDefault();
          focusRowFieldByClass(row, "product-search", e.key === "ArrowDown" ? 1 : -1);
          return;
        }

        if (e.key === "Backspace" && String(e.target.value || "") === "") {
          const select = row.querySelector(".product");
          if (select && select.value) {
            select.value = "";
            hideDropdown(row);
            calculateTotals();
          }
          return;
        }

        if (e.key === "Escape" && open) {
          e.preventDefault();
          e.stopPropagation();
          hideDropdown(row);
          return;
        }

        if (e.key === "Enter" || e.key === "Tab") {
          e.preventDefault();
          e.stopPropagation();

          const nextFocus = e.key === "Enter" ? "nextRow" : "qty";
          if (pickDropdownActive(row, { nextFocus })) return;

          const select = row.querySelector(".product");
          if (select && select.value) {
            hideDropdown(row);
            if (nextFocus === "nextRow") focusNextRowProduct(row);
            else row.querySelector(".qty")?.focus();
            return;
          }

          // If user pressed Enter on an empty row, treat it as "finish entries" (keyboard-only flow).
          if (e.key === "Enter" && String(e.target.value || "").trim() === "") {
            hideDropdown(row);
            focusFinishAction();
            return;
          }

          const matches = matchProducts(productsIndex, e.target.value);
          if (matches.length >= 1) {
            // Fast entry: pick the first match if user didn't explicitly choose.
            applyProductToRow(row, matches[0].id, { nextFocus });
            return;
          }

          // Busy-like: don't leave cell until a product is selected.
          return;
        }
      }

      if (e.target.classList.contains("qty")) {
        if (e.key === "ArrowDown" || e.key === "ArrowUp") {
          e.preventDefault();
          focusRowFieldByClass(row, "qty", e.key === "ArrowDown" ? 1 : -1);
          return;
        }

        if (e.key === "Backspace" && String(e.target.value || "") === "") {
          e.preventDefault();
          row.querySelector(".product-search")?.focus();
          return;
        }

        if (e.key === "Enter" || e.key === "Tab") {
          e.preventDefault();
          e.stopPropagation();
          openDiscountModal({ row, focus: "price", returnFocus: "qty", afterApplyFocus: "nextRow" });
          return;
        }
      }

      if (e.target.classList.contains("price")) {
        if (e.key === "ArrowDown" || e.key === "ArrowUp") {
          e.preventDefault();
          focusRowFieldByClass(row, "price", e.key === "ArrowDown" ? 1 : -1);
          return;
        }

        if (e.key === "Backspace" && String(e.target.value || "") === "") {
          e.preventDefault();
          row.querySelector(".qty")?.focus();
          return;
        }

        if (e.key === "Enter" || e.key === "Tab") {
          e.preventDefault();
          e.stopPropagation();
          row.querySelector(".amount")?.focus();
          return;
        }
      }

      if (e.target.classList.contains("amount")) {
        if (e.ctrlKey && e.key === "Enter") {
          e.preventDefault();
          e.stopPropagation();
          handleAction("save");
          return;
        }

        if (e.key === "ArrowDown" || e.key === "ArrowUp") {
          e.preventDefault();
          focusRowFieldByClass(row, "amount", e.key === "ArrowDown" ? 1 : -1);
          return;
        }

        if (e.key === "Backspace" && String(e.target.value || "") === "") {
          e.preventDefault();
          row.querySelector(".price")?.focus();
          return;
        }

        if (e.key === "Enter" || e.key === "Tab") {
          e.preventDefault();
          e.stopPropagation();
          
          // Check if this is the last row with data
          const tbody = document.getElementById("orderBody");
          const rows = Array.from(tbody?.querySelectorAll?.("tr.item-row") || []);
          const rowIndex = rows.indexOf(row);
          const lastRowWithData = rows.findIndex((r, idx) => idx > rowIndex && !r.querySelector(".product").value) - 1;
          const isLastPopulated = lastRowWithData === -1 && rowIndex === rows.findIndex((r, idx) => idx >= rowIndex && r.querySelector(".product").value === "");
          
          // If this is effectively the last data row, don't auto-add, go to next step
          const hasEmptyRowAfter = rows.some((r, idx) => idx > rowIndex && !r.querySelector(".product").value);
          focusNextRowProduct(row, !hasEmptyRowAfter);
          return;
        }
      }

    });

    tbody.addEventListener("keyup", (e) => {
      if (!e.target.classList.contains("product-search")) return;
      const row = e.target.closest("tr.item-row");
      if (!row) return;

      const query = e.target.value;
      if (query.trim().length < MIN_SEARCH_CHARS) {
        // Still allow barcode exact match via matchProducts.
        const matches = matchProducts(productsIndex, query);
        if (matches.length === 1 && matches[0].barcode && matches[0].barcode === query.trim()) {
          applyProductToRow(row, matches[0].id);
          return;
        }
        hideDropdown(row);
        return;
      }
      const matches = matchProducts(productsIndex, query);

      // Auto-pick exact barcode match
      if (matches.length === 1 && matches[0].barcode && matches[0].barcode === query.trim()) {
        applyProductToRow(row, matches[0].id);
        return;
      }

      renderDropdown(row, matches);
    });
  }

  function init() {
    if (!isPcBusyMode()) return;

    window.__ADD_ORDER_PC_BUSY__ = true;

    // Ensure helper functions are globally available
    window.showKeyboardHelp = window.showKeyboardHelp || function() {
        const modal = document.getElementById('keyboardHelp');
        if (modal) modal.style.display = 'flex';
    };
    window.hideKeyboardHelp = window.hideKeyboardHelp || function() {
        const modal = document.getElementById('keyboardHelp');
        if (modal) modal.style.display = 'none';
    };

    // Template sometimes has duplicated IDs due to legacy markup; normalize in PC mode.
    keepSingleElementById("orderType");
    keepSingleElementById("partySearch");

    // If the template pre-selects a party (e.g. via query params), reflect it in the search input.
    try {
      const partySelect = document.getElementById("partySelect");
      const partySearch = document.getElementById("partySearch");
      if (partySelect && partySearch && !partySearch.value.trim()) {
        const opt = partySelect.selectedOptions?.[0];
        if (opt && opt.value) partySearch.value = (opt.textContent || "").trim();
      }
    } catch (e) {}

    // Remove/hide sections that create extra blank space in PC Busy layout.
    document.querySelectorAll(".sundry-section-inline").forEach((el) => {
      el.style.display = "none";
    });
    const footer = document.querySelector("#mainOrderCard > .card-footer");
    if (footer) footer.style.display = "none";

    mountPcControls();
    mountSidePanels();
    mountBottomBar();

    // Ensure core recalculation works even if the template doesn't include legacy summary-card markup.
    document.getElementById("pcGstEnabled")?.addEventListener("change", calculateTotals);
    document.getElementById("pcGstRate")?.addEventListener("change", calculateTotals);
    document.getElementById("orderType")?.addEventListener("change", calculateTotals);
    document.getElementById("orderType")?.addEventListener("change", updateSmartKhataCreditInfo);
    document.getElementById("partySelect")?.addEventListener("change", () => {
      updateVoucherPanel();
      updateSmartKhataCreditInfo();
    });
    // Initial render (template may preselect party/order type)
    updateSmartKhataCreditInfo();
    const step1 = document.getElementById("step-1");
    if (step1) {
      step1.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;
        if (e.ctrlKey || e.altKey || e.metaKey || e.shiftKey) return;
        const target = e.target;
        if (!target) return;

        // In busy top strip, treat Enter like Tab for text/date/number/select inputs.
        const tag = (target.tagName || "").toLowerCase();
        const type = (target.getAttribute && target.getAttribute("type")) ? String(target.getAttribute("type")).toLowerCase() : "";
        const isFocusableField =
          tag === "select" ||
          tag === "textarea" ||
          (tag === "input" && !["checkbox", "radio", "button", "submit", "hidden"].includes(type));

        if (!isFocusableField) return;

        const focusables = Array.from(
          step1.querySelectorAll(
            'button:not([disabled]), a[href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
          )
        ).filter((el) => el.offsetParent !== null);

        if (!focusables.length) return;
        const idx = focusables.indexOf(target);
        const nextIdx = idx >= 0 ? Math.min(focusables.length - 1, idx + 1) : 0;
        const next = focusables[nextIdx];
        if (!next || next === target) return;

        e.preventDefault();
        next.focus();
      });
    }

    // In PC Busy layout, wizard "Next/Previous" would switch to hidden steps.
    // Repurpose it as a keyboard-friendly "finish entries" jump.
    const nextStepBtn = document.getElementById("nextStep");
    if (nextStepBtn) {
      nextStepBtn.type = "button";
      nextStepBtn.addEventListener("click", (e) => {
        e.preventDefault();
        focusFinishAction();
      });
    }
    const prevStepBtn = document.getElementById("prevStep");
    if (prevStepBtn) {
      prevStepBtn.type = "button";
      prevStepBtn.addEventListener("click", (e) => {
        e.preventDefault();
        handleAction("party");
      });
    }
    createDiscountModal();
    createPrintModal();
    loadBillSundryFromStorage();
    syncBillSundryHiddenInput();
    renderSundryList();

    // Setup inline sundry form handlers
    const applySundryBtn = document.getElementById("applySundry");
    const closeSundryBtn = document.getElementById("closeSundry");
    const sundryNameInput = document.getElementById("sundryName");
    const sundryAmountInput = document.getElementById("sundryAmount");

    if (applySundryBtn) {
      applySundryBtn.addEventListener("click", () => {
        const name = (sundryNameInput?.value || "").trim();
        const amount = parseMoney(sundryAmountInput?.value);
        if (name && amount > 0) {
          billSundryLines.push({ name, amount });
          persistBillSundryToStorage();
          syncBillSundryHiddenInput();
          sundryNameInput.value = "";
          sundryAmountInput.value = "";
          calculateTotals();
          renderSundryList();
          sundryNameInput.focus();
          sundryNameInput.scrollIntoView?.({ block: "nearest" });
        } else {
          alert("Please enter a valid sundry description and amount.");
        }
      });
    }

    if (closeSundryBtn) {
      closeSundryBtn.addEventListener("click", () => {
        sundryNameInput.value = "";
        sundryAmountInput.value = "";
        sundryNameInput.focus();
      });
    }

    // Keyboard handlers for sundry form
    if (sundryNameInput) {
      sundryNameInput.addEventListener("keydown", (e) => {
        if (e.key === "Tab" && !e.shiftKey) {
          e.preventDefault();
          sundryAmountInput?.focus();
        } else if (e.key === "Enter") {
          e.preventDefault();
          applySundryBtn?.click();
        } else if (e.key === "Escape") {
          e.preventDefault();
          closeSundryBtn?.click();
        }
      });
    }

    if (sundryAmountInput) {
      sundryAmountInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          applySundryBtn?.click();
        } else if (e.key === "Escape") {
          e.preventDefault();
          closeSundryBtn?.click();
        } else if (e.key === "Shift" && e.key === "Tab") {
          e.preventDefault();
          sundryNameInput?.focus();
        } else if (e.key === "Tab") {
          e.preventDefault();
          document.getElementById("nextStep")?.focus();
        }
      });
    }

    // Modal live calculations
    document.addEventListener("input", (e) => {
      if (!document.getElementById("pcDiscountModal")) return;
      if (e.target?.id === "pcDiscValue" || e.target?.id === "pcRowPrice") syncDiscountModalCalculations();
    });
    document.addEventListener("change", (e) => {
      if (!document.getElementById("pcDiscountModal")) return;
      if (e.target?.id === "pcDiscBasis") syncDiscountModalCalculations();
    });

    const productsIndex = collectProductsFromDom();
    const partiesIndex = collectPartiesFromDom();
    normalizePcTableColumns();
    removePcAddRowButton();

    // Restore PC preferences
    const storedZoom = getStoredInt(ZOOM_STORAGE_KEY, 100);
    const normalizedZoom = storedZoom >= 95 && storedZoom <= 105 ? storedZoom : 100;
    applyZoom(normalizedZoom);
    if (normalizedZoom !== storedZoom) localStorage.setItem(ZOOM_STORAGE_KEY, String(normalizedZoom));
    applyFullWidth(getStoredInt(FULLWIDTH_STORAGE_KEY, 0) === 1);

    ensureRowsFillViewport();
    window.addEventListener("resize", queueEnsureRowsFillViewport);
    window.setTimeout(queueEnsureRowsFillViewport, 200);

    wireTableInteractions(productsIndex);
    wirePartyPicker(partiesIndex);
    installKeyboardShortcuts();
    calculateTotals();

    // Top strip: show weekday label (matches classic busy UI).
    function syncOrderDayLabel() {
      const input = document.querySelector('input[name="order_date"]');
      const out = document.getElementById("orderDayLabel");
      if (!input || !out) return;
      const raw = String(input.value || "").trim();
      if (!raw) {
        out.textContent = "-";
        return;
      }
      const d = new Date(raw + "T00:00:00");
      if (Number.isNaN(d.getTime())) {
        out.textContent = "-";
        return;
      }
      const day = d.toLocaleDateString(undefined, { weekday: "short" });
      out.textContent = day || "-";
    }
    document.querySelector('input[name="order_date"]')?.addEventListener("change", syncOrderDayLabel);
    syncOrderDayLabel();

    // Focus Party first like Busy.
    setTimeout(() => focusFirstVisible("#partySearch, #partySelect"), 50);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Expose help controls for inline template buttons, if any.
  window.showKeyboardHelp = showKeyboardHelp;
  window.hideKeyboardHelp = hideKeyboardHelp;
  window.openPcPrintModal = openPrintModal;
  window.openPcDiscountModal = openDiscountModal;
})();
