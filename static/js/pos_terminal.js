(function () {
  const STORE_KEY = "billentra_pos_state_v2";
  const HOLD_KEY = "billentra_pos_holds_v2";
  const QUEUE_KEY = "billentra_pos_offline_queue_v2";
  const DESIGN_KEY = "billentra_pos_design_v1";
  const HARDWARE_KEY = "billentra_pos_hardware_v1";

  const state = {
    products: [],
    categories: [],
    category: "all",
    priceMode: "retail",
    cart: [],
    customerName: "Walk-in Customer",
    discountTotal: 0,
    paymentMode: "cash",
    lastBill: null,
    checkoutBusy: false,
    partyId: null,
    customerMobile: "",
  };

  const $ = (id) => document.getElementById(id);

  function money(value) {
    const num = Number(value || 0);
    return Number.isFinite(num) ? num : 0;
  }

  function fmt(value) {
    return money(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function csrf() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    if (match) return decodeURIComponent(match[1]);
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : "";
  }

  function toast(message, type) {
    window.dispatchEvent(new CustomEvent("ui:toast", { detail: { message, type: type || "info" } }));
  }

  function setStatus(message) {
    const el = $("pos-status");
    if (el) el.textContent = message;
  }

  function speak(message) {
    if (!("speechSynthesis" in window)) return;
    const utterance = new SpeechSynthesisUtterance(message);
    utterance.rate = 1.02;
    utterance.pitch = 0.95;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  }

  function hardwareConfig() {
    return JSON.parse(localStorage.getItem(HARDWARE_KEY) || "{}");
  }

  function saveHardwareConfig(config) {
    localStorage.setItem(HARDWARE_KEY, JSON.stringify(config || {}));
  }

  function beep() {
    const sound = $("scan-sound");
    if (sound) sound.play().catch(function () {});
    if (navigator.vibrate) navigator.vibrate(18);
  }

  function priceFor(product) {
    if (state.priceMode === "wholesale") return money(product.wholesale_price || product.b2b_price || product.b2c_price);
    if (state.priceMode === "b2b") return money(product.b2b_price || product.wholesale_price || product.b2c_price);
    return money(product.b2c_price || product.mrp);
  }

  function saveState() {
    localStorage.setItem(STORE_KEY, JSON.stringify({
      cart: state.cart,
      customerName: state.customerName,
      discountTotal: state.discountTotal,
      paymentMode: state.paymentMode,
      priceMode: state.priceMode,
      partyId: state.partyId,
      customerMobile: state.customerMobile,
    }));
  }

  function restoreState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORE_KEY) || "{}");
    state.cart = Array.isArray(saved.cart) ? saved.cart : [];
      state.customerName = saved.customerName || state.customerName;
      state.discountTotal = money(saved.discountTotal);
      state.paymentMode = saved.paymentMode || state.paymentMode;
      state.priceMode = saved.priceMode || state.priceMode;
      state.partyId = saved.partyId || null;
      state.customerMobile = saved.customerMobile || "";
    } catch (err) {}
  }

  function totals() {
    let subtotal = 0;
    let tax = 0;
    let qty = 0;
    state.cart.forEach(function (line) {
      const base = money(line.qty) * money(line.unit_price);
      const lineDiscount = money(line.discount);
      const taxable = Math.max(base - lineDiscount, 0);
      subtotal += base;
      tax += taxable * (money(line.gst_percent) / 100);
      qty += money(line.qty);
    });
    const total = Math.max(subtotal - money(state.discountTotal) + tax, 0);
    return { subtotal, tax, total, qty, discount: money(state.discountTotal) };
  }

  function addProduct(product, qty) {
    const existing = state.cart.find(function (line) { return line.product_id === product.id; });
    if (existing) {
      existing.qty += qty || 1;
    } else {
      state.cart.push({
        product_id: product.id,
        name: product.name,
        sku: product.sku,
        barcode: product.barcode,
        qty: qty || 1,
        unit_price: priceFor(product),
        gst_percent: money(product.gst_percent),
        discount: 0,
      });
    }
    beep();
    saveState();
    renderCart();
  }

  function removeLine(index) {
    state.cart.splice(index, 1);
    saveState();
    renderCart();
  }

  function changeQty(index, delta) {
    const line = state.cart[index];
    if (!line) return;
    line.qty = Math.max(1, money(line.qty) + delta);
    saveState();
    renderCart();
  }

  function setLineQty(index) {
    const line = state.cart[index];
    if (!line) return;
    const value = prompt("Quantity", line.qty);
    if (value === null) return;
    line.qty = Math.max(1, parseInt(value, 10) || 1);
    saveState();
    renderCart();
  }

  function renderCart() {
    const box = $("line-items");
    const t = totals();
    $("pos-customer-label").textContent = state.customerName || "Walk-in Customer";
    $("pos-item-count").textContent = String(t.qty);
    $("pos-subtotal").textContent = fmt(t.subtotal);
    $("pos-discount").textContent = fmt(t.discount);
    $("pos-tax").textContent = fmt(t.tax);
    $("total").textContent = fmt(t.total);
    document.querySelectorAll("[data-pay-mode]").forEach(function (btn) {
      btn.classList.toggle("active", btn.dataset.payMode === state.paymentMode);
    });
    if (!box) return;
    if (!state.cart.length) {
      box.innerHTML = '<div class="text-muted text-center py-4">No items in bill</div>';
      return;
    }
    box.innerHTML = state.cart.map(function (line, index) {
      const lineTotal = (money(line.qty) * money(line.unit_price)) - money(line.discount);
      return `
        <div class="pos-cart-line">
          <div>
            <strong>${index + 1}. ${line.name}</strong>
            <small>${line.sku || line.barcode || ""} | GST ${fmt(line.gst_percent)}%</small>
            <div class="pos-line-controls">
              <button type="button" data-line-minus="${index}">-</button>
              <button type="button" data-line-qty="${index}">${line.qty}</button>
              <button type="button" data-line-plus="${index}">+</button>
              <button type="button" data-line-discount="${index}">Disc</button>
              <button type="button" data-line-remove="${index}">X</button>
            </div>
          </div>
          <div class="pos-line-total">
            ${fmt(lineTotal)}
            <small>${fmt(line.unit_price)} each</small>
          </div>
        </div>
      `;
    }).join("");
  }

  function renderCentralLinks(bill) {
    const box = $("pos-central-links");
    if (!box) return;
    if (!bill || !bill.invoice_id || !bill.commerce_order_id) {
      box.hidden = true;
      box.innerHTML = "";
      return;
    }
    box.hidden = false;
    box.innerHTML = `
      <a href="/commerce/invoices/${bill.invoice_id}/" target="_blank" rel="noopener">Open Invoice</a>
      <a href="/commerce/orders/${bill.commerce_order_id}/" target="_blank" rel="noopener">Open Order</a>
    `;
  }

  function renderProducts() {
    const box = $("pos-products");
    if (!box) return;
    const rows = state.products.filter(function (p) {
      return state.category === "all" || p.category === state.category;
    });
    if (!rows.length) {
      box.innerHTML = '<div class="text-muted p-3">No products found</div>';
      return;
    }
    box.innerHTML = rows.map(function (p) {
      return `
        <button type="button" class="pos-product-tile" data-product-id="${p.id}">
          <div>
            <div class="pos-product-name">${p.name}</div>
            <div class="pos-product-meta">${p.sku || p.barcode || ""}</div>
          </div>
          <div>
            <div class="pos-product-price">${fmt(priceFor(p))}</div>
            <div class="pos-product-meta">${p.category || "General"} | Stock ${p.stock}</div>
          </div>
        </button>
      `;
    }).join("");
  }

  function renderCategories() {
    const box = $("pos-categories");
    if (!box) return;
    const cats = ["all"].concat(state.categories);
    box.innerHTML = cats.map(function (cat) {
      const label = cat === "all" ? "All" : cat;
      return `<button type="button" class="${state.category === cat ? "active" : ""}" data-category="${cat}">${label}</button>`;
    }).join("");
  }

  async function loadCatalog(query) {
    setStatus("Loading catalog");
    const params = new URLSearchParams({ mode: state.priceMode });
    if (query) params.set("q", query);
    if (state.category !== "all") params.set("category", state.category);
    const res = await fetch("/api/v1/pos/catalog/?" + params.toString(), { credentials: "same-origin" });
    if (!res.ok) throw new Error("Catalog failed");
    const data = await res.json();
    state.products = data.products || [];
    state.categories = data.categories || [];
    renderCategories();
    renderProducts();
    setStatus(query ? (state.products.length + " products found") : "Ready");
  }

  async function scanOrSearch() {
    const input = $("barcode-input");
    const q = (input.value || "").trim();
    if (!q) {
      input.focus();
      return;
    }
    await loadCatalog(q);
    const exact = state.products.find(function (p) {
      return [p.barcode, p.sku, String(p.id)].includes(q);
    });
    if (exact) {
      addProduct(exact, 1);
      input.value = "";
      setStatus("Added " + exact.name);
      return;
    }
    if (state.products.length === 1) {
      addProduct(state.products[0], 1);
      input.value = "";
      return;
    }
    setStatus(state.products.length + " products found");
  }

  function openModal(title, html, onReady) {
    $("pos-modal-title").textContent = title;
    $("pos-modal-body").innerHTML = html;
    $("pos-modal").hidden = false;
    if (onReady) onReady();
  }

  function closeModal() {
    $("pos-modal").hidden = true;
  }

  function customerModal() {
    openModal("Customer", `
      <div class="pos-form-grid">
        <label>Search Customer<input id="modal-customer-search" placeholder="Type name, mobile, GST"></label>
        <label>Select Existing Customer
          <select id="modal-party-id">
            <option value="">Walk-in / Manual Customer</option>
          </select>
        </label>
        <label>Customer Name<input id="modal-customer-name" value="${state.customerName || ""}"></label>
        <label>Mobile<input id="modal-customer-mobile" value="${state.customerMobile || ""}" placeholder="Optional mobile"></label>
        <button type="button" class="pos-primary" id="save-customer">Save Customer</button>
      </div>
    `, async function () {
      const select = $("modal-party-id");
      function applySelectedCustomer() {
        const selected = select.selectedOptions[0];
        if (!selected || !selected.value) {
          state.partyId = null;
          return;
        }
        state.partyId = selected.value;
        $("modal-customer-name").value = selected.dataset.name || selected.textContent;
        $("modal-customer-mobile").value = selected.dataset.mobile || "";
      }
      async function loadCustomers(query) {
        const res = await fetch("/api/v1/pos/customers/?" + new URLSearchParams({ q: query || "" }).toString(), { credentials: "same-origin" });
        if (!res.ok) throw new Error("Customer search failed");
        const data = await res.json();
        select.innerHTML = '<option value="">Walk-in / Manual Customer</option>';
        const customers = data.customers || [];
        customers.forEach(function (customer) {
          const opt = document.createElement("option");
          opt.value = customer.id;
          opt.textContent = customer.name + (customer.mobile ? " - " + customer.mobile : "") + " | Bal " + customer.balance;
          opt.dataset.name = customer.name;
          opt.dataset.mobile = customer.mobile || "";
          if (String(state.partyId || "") === String(customer.id)) opt.selected = true;
          select.appendChild(opt);
        });
        if (query && customers.length) {
          const exact = customers.find(function (customer) {
            const needle = String(query || "").toLowerCase();
            return String(customer.name || "").toLowerCase() === needle || String(customer.mobile || "").includes(needle);
          });
          select.value = String((exact || customers[0]).id);
          applySelectedCustomer();
        } else if (state.partyId) {
          applySelectedCustomer();
        }
      }
      try {
        await loadCustomers("");
      } catch (err) {}
      let timer = null;
      $("modal-customer-search").oninput = function () {
        clearTimeout(timer);
        const value = this.value;
        timer = setTimeout(function () { loadCustomers(value).catch(function () {}); }, 220);
      };
      select.onchange = function () {
        applySelectedCustomer();
      };
      $("save-customer").onclick = function () {
        state.partyId = $("modal-party-id").value || null;
        state.customerName = $("modal-customer-name").value || $("modal-customer-search").value || "Walk-in Customer";
        state.customerMobile = $("modal-customer-mobile").value || "";
        saveState();
        renderCart();
        setStatus("Customer: " + state.customerName);
        closeModal();
      };
    });
  }

  function discountModal() {
    openModal("Discount", `
      <div class="pos-form-grid">
        <label>Bill Discount Amount<input id="modal-discount" type="number" min="0" step="0.01" value="${state.discountTotal}"></label>
        <button type="button" class="pos-primary" id="save-discount">Apply Discount</button>
      </div>
    `, function () {
      $("save-discount").onclick = function () {
        state.discountTotal = money($("modal-discount").value);
        saveState();
        renderCart();
        closeModal();
      };
    });
  }

  function addCustomModal() {
    openModal("Custom Item", `
      <div class="pos-form-grid">
        <label>Name<input id="custom-name" value="Custom Item"></label>
        <div class="row2">
          <label>Price<input id="custom-price" type="number" min="0" step="0.01" value="0"></label>
          <label>GST %<input id="custom-gst" type="number" min="0" step="0.01" value="0"></label>
        </div>
        <button type="button" class="pos-primary" id="save-custom">Add Item</button>
      </div>
    `, function () {
      $("save-custom").onclick = function () {
        state.cart.push({
          product_id: null,
          name: $("custom-name").value || "Custom Item",
          sku: "CUSTOM",
          barcode: "",
          qty: 1,
          unit_price: money($("custom-price").value),
          gst_percent: money($("custom-gst").value),
          discount: 0,
        });
        saveState();
        renderCart();
        closeModal();
      };
    });
  }

  function holdBill() {
    if (!state.cart.length) {
      toast("Cart is empty.", "warning");
      return;
    }
    const holds = JSON.parse(localStorage.getItem(HOLD_KEY) || "[]");
    const hold = {
      id: "HOLD-" + Date.now(),
      at: new Date().toLocaleString(),
      customerName: state.customerName,
      discountTotal: state.discountTotal,
      cart: state.cart,
    };
    holds.unshift(hold);
    localStorage.setItem(HOLD_KEY, JSON.stringify(holds.slice(0, 20)));
    state.cart = [];
    state.discountTotal = 0;
    saveState();
    renderCart();
    renderHolds();
    setStatus("Bill held");
  }

  function renderHolds() {
    const box = $("pos-held-list");
    if (!box) return;
    const holds = JSON.parse(localStorage.getItem(HOLD_KEY) || "[]");
    if (!holds.length) {
      box.innerHTML = '<span class="text-muted">No held bills</span>';
      return;
    }
    box.innerHTML = holds.map(function (h, idx) {
      const total = (h.cart || []).reduce(function (a, line) { return a + money(line.qty) * money(line.unit_price); }, 0);
      return `<button type="button" data-hold-index="${idx}">${h.id} | ${fmt(total)}</button>`;
    }).join("");
  }

  function retrieveHold(index) {
    const holds = JSON.parse(localStorage.getItem(HOLD_KEY) || "[]");
    const hold = holds[index];
    if (!hold) return;
    state.cart = hold.cart || [];
    state.customerName = hold.customerName || "Walk-in Customer";
    state.discountTotal = money(hold.discountTotal);
    holds.splice(index, 1);
    localStorage.setItem(HOLD_KEY, JSON.stringify(holds));
    saveState();
    renderCart();
    renderHolds();
    setStatus("Held bill retrieved");
  }

  function retrieveModal() {
    const holds = JSON.parse(localStorage.getItem(HOLD_KEY) || "[]");
    openModal("Retrieve Bill", `
      <div class="pos-held-list">
        ${holds.map(function (h, idx) { return `<button type="button" data-modal-hold="${idx}">${h.id} | ${h.customerName}</button>`; }).join("") || '<span class="text-muted">No held bills</span>'}
      </div>
    `);
  }

  async function checkout(paymentMode) {
    if (state.checkoutBusy) {
      toast("Checkout already in progress.", "warning");
      return;
    }
    if (!state.cart.length) {
      toast("Cart is empty.", "warning");
      return;
    }
    const t = totals();
    const mode = paymentMode || state.paymentMode || "cash";
    let tender = t.total;
    if (mode === "cash" || mode === "split") {
      const value = prompt("Tender amount", fmt(t.total).replace(/,/g, ""));
      if (value === null) return;
      tender = money(value);
      if (tender < t.total) {
        toast("Tender amount is less than total.", "error");
        return;
      }
    }
    const payload = {
      client_ref: "POS-" + Date.now().toString(36).toUpperCase() + "-" + Math.random().toString(36).slice(2, 8).toUpperCase(),
      terminal_id: "WEB-POS",
      price_mode: state.priceMode,
      party_id: state.partyId,
      customer_name: state.customerName,
      customer_mobile: state.customerMobile,
      discount_total: state.discountTotal,
      payment_mode: mode === "split" ? "cash" : mode,
      payments: [{ mode: mode === "split" ? "cash" : mode, amount: tender }],
      items: state.cart,
    };
    try {
      state.checkoutBusy = true;
      const payButton = $("pay-btn");
      if (payButton) payButton.disabled = true;
      setStatus("Checkout");
      const res = await fetch("/api/v1/pos/checkout/", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(function () { return {}; });
      if (!res.ok) {
        setStatus("Checkout blocked");
        toast(data.detail || "Checkout failed.", "error");
        return;
      }
      state.lastBill = data;
      printReceipt(data);
      renderCentralLinks(data);
      state.cart = [];
      state.discountTotal = 0;
      saveState();
      renderCart();
      setStatus("Saved: Invoice " + data.invoice_number + " / Order #" + data.commerce_order_id);
      toast("Payment accepted. Change " + fmt(data.change), "success");
      speak("Payment accepted. Bill printed.");
    } catch (err) {
      const queue = JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]");
      queue.push({ payload, at: Date.now() });
      localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
      setStatus("Offline queued");
      toast("Network/API issue. Bill saved in offline queue.", "warning");
    } finally {
      state.checkoutBusy = false;
      const payButton = $("pay-btn");
      if (payButton) payButton.disabled = false;
    }
  }

  async function syncQueue() {
    const queue = JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]");
    if (!queue.length) {
      toast("No pending bills.", "info");
      return;
    }
    const remaining = [];
    for (const entry of queue) {
      try {
        const res = await fetch("/api/v1/pos/checkout/", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
          body: JSON.stringify(entry.payload),
        });
        if (!res.ok) remaining.push(entry);
      } catch (err) {
        remaining.push(entry);
      }
    }
    localStorage.setItem(QUEUE_KEY, JSON.stringify(remaining));
    toast("Sync complete. Pending " + remaining.length, remaining.length ? "warning" : "success");
  }

  function printReceipt(bill) {
    const t = totals();
    const config = hardwareConfig();
    const upiId = config.upiId || "merchant@upi";
    const bankName = config.bankName || "Demo Bank";
    const accountNo = config.accountNo || "0000000000";
    const ifsc = config.ifsc || "DEMO0000001";
    const payTotal = bill ? bill.total : t.total;
    const qrText = encodeURIComponent("upi://pay?pa=" + upiId + "&pn=Billentra&am=" + payTotal + "&cu=INR");
    const qrSvg = "https://api.qrserver.com/v1/create-qr-code/?size=120x120&data=" + qrText;
    const rows = state.cart.map(function (line) {
      return `<tr><td>${line.name}<br><small>${line.qty} x ${fmt(line.unit_price)}</small></td><td style="text-align:right">${fmt(money(line.qty) * money(line.unit_price))}</td></tr>`;
    }).join("");
    const html = `
      <html><head><title>Receipt</title>
      <style>
        body{font-family:monospace;width:280px;margin:0;padding:10px;color:#111}
        h2{text-align:center;margin:0 0 4px;font-size:16px}
        .meta{text-align:center;font-size:11px;border-bottom:1px dashed #111;padding-bottom:6px;margin-bottom:6px}
        table{width:100%;border-collapse:collapse;font-size:12px}
        td{padding:4px 0;border-bottom:1px dashed #ddd;vertical-align:top}
        .total{font-size:16px;font-weight:bold;border-top:1px dashed #111;margin-top:6px;padding-top:6px;display:flex;justify-content:space-between}
      </style></head><body>
        <h2>Billentra POS</h2>
        <div class="meta">
          ${bill ? bill.bill_number : "Draft Receipt"}<br>
          ${bill && bill.invoice_number ? "Invoice: " + bill.invoice_number + "<br>" : ""}
          ${bill && bill.commerce_order_id ? "Order ID: " + bill.commerce_order_id + "<br>" : ""}
          ${bill ? bill.created_at : new Date().toLocaleString()}<br>${state.customerName}
        </div>
        <table>${rows}</table>
        <div class="total"><span>Total</span><span>${fmt(bill ? bill.total : t.total)}</span></div>
        <img class="pos-receipt-qr" src="${qrSvg}" alt="Payment QR">
        <div class="meta" style="border:0;margin-top:8px">
          UPI: ${upiId}<br>
          Bank: ${bankName}<br>
          A/C: ${accountNo}<br>
          IFSC: ${ifsc}<br>
          Thank you
        </div>
      </body></html>`;
    const win = window.open("", "_blank", "width=340,height=680");
    if (!win) {
      window.print();
      return;
    }
    win.document.open();
    win.document.write(html);
    win.document.close();
    win.focus();
    setTimeout(function () { win.print(); }, 250);
  }

  function designerModal() {
    const design = JSON.parse(localStorage.getItem(DESIGN_KEY) || "{}");
    openModal("POS Design", `
      <div class="pos-form-grid">
        <div class="row2">
          <label>Brand Color<input id="design-brand" type="color" value="${design.brand || "#0f766e"}"></label>
          <label>Tile Size<input id="design-tile" type="range" min="110" max="190" value="${design.tile || 132}"></label>
        </div>
        <button type="button" class="pos-primary" id="save-design">Apply Design</button>
      </div>
    `, function () {
      $("save-design").onclick = function () {
        const next = { brand: $("design-brand").value, tile: $("design-tile").value };
        localStorage.setItem(DESIGN_KEY, JSON.stringify(next));
        applyDesign();
        closeModal();
      };
    });
  }

  function applyDesign() {
    const design = JSON.parse(localStorage.getItem(DESIGN_KEY) || "{}");
    if (design.brand) document.documentElement.style.setProperty("--pos-brand", design.brand);
    if (design.tile) document.documentElement.style.setProperty("--pos-tile", design.tile + "px");
  }

  function hardwareModal() {
    const config = hardwareConfig();
    openModal("Hardware", `
      <div class="pos-form-grid">
        <div class="row2">
          <label>Printer Type
            <select id="hw-printer-type">
              <option value="browser" ${config.printerType === "browser" ? "selected" : ""}>Browser / Any Printer</option>
              <option value="thermal58" ${config.printerType === "thermal58" ? "selected" : ""}>Thermal 58mm</option>
              <option value="thermal80" ${config.printerType === "thermal80" ? "selected" : ""}>Thermal 80mm</option>
              <option value="a4" ${config.printerType === "a4" ? "selected" : ""}>A4 Invoice</option>
            </select>
          </label>
          <label>UPI ID<input id="hw-upi" value="${config.upiId || "merchant@upi"}"></label>
        </div>
        <div class="row2">
          <label>Bank Name<input id="hw-bank" value="${config.bankName || "Demo Bank"}"></label>
          <label>IFSC<input id="hw-ifsc" value="${config.ifsc || "DEMO0000001"}"></label>
        </div>
        <label>Account Number<input id="hw-account" value="${config.accountNo || "0000000000"}"></label>
        <button type="button" class="pos-primary" id="connect-serial">Connect Barcode/Scale Serial</button>
        <button type="button" class="pos-secondary" id="camera-scan">Camera Barcode / QR Scan</button>
        <button type="button" class="pos-secondary" id="test-print">Test Thermal Print</button>
        <button type="button" class="pos-primary" id="save-hardware">Save Settings</button>
        <div class="text-muted">USB/keyboard barcode scanners work automatically in the scan box. Browser print supports all installed printers.</div>
      </div>
    `, function () {
      $("test-print").onclick = function () { printReceipt(null); };
      $("save-hardware").onclick = function () {
        saveHardwareConfig({
          printerType: $("hw-printer-type").value,
          upiId: $("hw-upi").value,
          bankName: $("hw-bank").value,
          ifsc: $("hw-ifsc").value,
          accountNo: $("hw-account").value,
        });
        toast("POS hardware/payment settings saved.", "success");
        closeModal();
      };
      $("camera-scan").onclick = cameraScannerModal;
      $("connect-serial").onclick = async function () {
        if (!("serial" in navigator)) {
          toast("Web Serial is not supported in this browser.", "warning");
          return;
        }
        try {
          const port = await navigator.serial.requestPort();
          await port.open({ baudRate: 9600 });
          toast("Serial device connected.", "success");
        } catch (err) {
          toast("Serial connection cancelled.", "warning");
        }
      };
    });
  }

  function cameraScannerModal() {
    openModal("Camera Scan", `
      <div class="pos-form-grid">
        <video class="pos-camera-preview" id="pos-camera" autoplay muted playsinline></video>
        <button type="button" class="pos-secondary" id="stop-camera">Stop Camera</button>
        <div class="text-muted">QR/barcode camera scanning uses the browser BarcodeDetector when available.</div>
      </div>
    `, async function () {
      const video = $("pos-camera");
      let stream = null;
      let stopped = false;
      $("stop-camera").onclick = function () {
        stopped = true;
        if (stream) stream.getTracks().forEach(function (track) { track.stop(); });
        closeModal();
      };
      if (!("BarcodeDetector" in window)) {
        toast("Camera BarcodeDetector is not supported in this browser.", "warning");
        return;
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        video.srcObject = stream;
        const detector = new BarcodeDetector({ formats: ["qr_code", "ean_13", "ean_8", "code_128", "code_39"] });
        async function loop() {
          if (stopped) return;
          try {
            const codes = await detector.detect(video);
            if (codes && codes.length) {
              $("barcode-input").value = codes[0].rawValue || "";
              stopped = true;
              stream.getTracks().forEach(function (track) { track.stop(); });
              closeModal();
              await scanOrSearch();
              return;
            }
          } catch (err) {}
          requestAnimationFrame(loop);
        }
        loop();
      } catch (err) {
        toast("Camera permission denied.", "error");
      }
    });
  }

  function voiceModal() {
    openModal("Voice Billing", `
      <div class="pos-form-grid">
        <button type="button" class="pos-primary" id="start-voice">Start Voice Billing</button>
        <button type="button" class="pos-secondary" id="voice-help">Speak Help</button>
        <div class="text-muted">
          Try: "add milk", "search bottle", "pay cash", "hold bill", "print bill", "clear bill".
        </div>
      </div>
    `, function () {
      $("voice-help").onclick = function () {
        speak("Voice billing ready. Say add product name, pay cash, hold bill, print bill, or clear bill.");
      };
      $("start-voice").onclick = startVoice;
    });
  }

  function startVoice() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      toast("Voice recognition is not supported in this browser.", "warning");
      return;
    }
    const rec = new SR();
    rec.lang = "en-IN";
    rec.interimResults = false;
    rec.onresult = async function (event) {
      const text = (event.results[0][0].transcript || "").toLowerCase();
      setStatus("Voice: " + text);
      if (text.includes("hold")) return holdBill();
      if (text.includes("print")) return printReceipt(state.lastBill);
      if (text.includes("clear")) {
        state.cart = [];
        state.discountTotal = 0;
        saveState();
        renderCart();
        return;
      }
      if (text.includes("pay")) {
        if (text.includes("upi")) state.paymentMode = "upi";
        if (text.includes("card")) state.paymentMode = "card";
        if (text.includes("cash")) state.paymentMode = "cash";
        renderCart();
        return checkout(state.paymentMode);
      }
      const query = text.replace("add", "").replace("search", "").trim();
      if (query) {
        $("barcode-input").value = query;
        await scanOrSearch();
      }
    };
    rec.onerror = function () { toast("Voice command failed.", "warning"); };
    rec.start();
    speak("Listening.");
  }

  function bindEvents() {
    let liveSearchTimer = null;
    $("barcode-input").addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        scanOrSearch();
      }
    });
    $("barcode-input").addEventListener("input", function () {
      clearTimeout(liveSearchTimer);
      const query = (this.value || "").trim();
      if (query.length < 3) return;
      liveSearchTimer = setTimeout(function () {
        loadCatalog(query).catch(function () {
          setStatus("Search failed");
        });
      }, 140);
    });
    $("pos-search-btn").onclick = scanOrSearch;
    $("pos-price-mode").value = state.priceMode;
    $("pos-price-mode").onchange = function () {
      state.priceMode = this.value;
      saveState();
      renderProducts();
    };
    $("pos-fullscreen").onclick = function () {
      if (!document.fullscreenElement) document.documentElement.requestFullscreen().catch(function () {});
      else document.exitFullscreen().catch(function () {});
    };
    $("pos-hardware").onclick = hardwareModal;
    $("pos-voice").onclick = voiceModal;
    $("pos-designer").onclick = designerModal;
    $("pos-modal-close").onclick = closeModal;
    $("pay-btn").onclick = function () { checkout(state.paymentMode); };
    $("print-btn").onclick = function () { printReceipt(state.lastBill); };
    $("sync-btn").onclick = syncQueue;

    document.addEventListener("click", function (event) {
      const tile = event.target.closest("[data-product-id]");
      if (tile) {
        const product = state.products.find(function (p) { return String(p.id) === String(tile.dataset.productId); });
        if (product) addProduct(product, 1);
      }
      const cat = event.target.closest("[data-category]");
      if (cat) {
        state.category = cat.dataset.category;
        renderCategories();
        renderProducts();
      }
      const action = event.target.closest("[data-pos-action]");
      if (action) runAction(action.dataset.posAction);
      const pay = event.target.closest("[data-pay-mode]");
      if (pay) {
        state.paymentMode = pay.dataset.payMode;
        renderCart();
        setStatus("Payment mode: " + state.paymentMode.toUpperCase());
      }
      const hold = event.target.closest("[data-hold-index]");
      if (hold) retrieveHold(Number(hold.dataset.holdIndex));
      const modalHold = event.target.closest("[data-modal-hold]");
      if (modalHold) {
        retrieveHold(Number(modalHold.dataset.modalHold));
        closeModal();
      }
      const minus = event.target.closest("[data-line-minus]");
      if (minus) changeQty(Number(minus.dataset.lineMinus), -1);
      const plus = event.target.closest("[data-line-plus]");
      if (plus) changeQty(Number(plus.dataset.linePlus), 1);
      const qty = event.target.closest("[data-line-qty]");
      if (qty) setLineQty(Number(qty.dataset.lineQty));
      const rem = event.target.closest("[data-line-remove]");
      if (rem) removeLine(Number(rem.dataset.lineRemove));
      const disc = event.target.closest("[data-line-discount]");
      if (disc) {
        const line = state.cart[Number(disc.dataset.lineDiscount)];
        if (line) {
          const value = prompt("Line discount", line.discount || 0);
          if (value !== null) line.discount = money(value);
          saveState();
          renderCart();
        }
      }
    });

    document.addEventListener("keydown", function (event) {
      const key = event.key;
      if (key === "F1") { event.preventDefault(); addCustomModal(); }
      if (key === "F2") { event.preventDefault(); if (state.cart.length) setLineQty(state.cart.length - 1); }
      if (key === "F3") { event.preventDefault(); discountModal(); }
      if (key === "F4") { event.preventDefault(); customerModal(); }
      if (key === "F5") { event.preventDefault(); holdBill(); }
      if (key === "F6") { event.preventDefault(); retrieveModal(); }
      if (key === "F7") { event.preventDefault(); checkout(state.paymentMode); }
      if (key === "F8") { event.preventDefault(); printReceipt(state.lastBill); }
      if (key === "Escape") { state.cart = []; state.discountTotal = 0; saveState(); renderCart(); }
    });
  }

  function runAction(action) {
    if (action === "add-custom") addCustomModal();
    if (action === "qty" && state.cart.length) setLineQty(state.cart.length - 1);
    if (action === "discount") discountModal();
    if (action === "customer") customerModal();
    if (action === "hold") holdBill();
    if (action === "retrieve") retrieveModal();
    if (action === "payment") checkout(state.paymentMode);
    if (action === "print") printReceipt(state.lastBill);
    if (action === "clear") {
      state.cart = [];
      state.discountTotal = 0;
      saveState();
      renderCart();
    }
  }

  async function init() {
    applyDesign();
    restoreState();
    bindEvents();
    renderCart();
    renderCentralLinks(state.lastBill);
    renderHolds();
    try {
      await loadCatalog("");
    } catch (err) {
      setStatus("Offline catalog");
      toast("Catalog API not reachable.", "warning");
    }
    const input = $("barcode-input");
    if (input) input.focus();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
