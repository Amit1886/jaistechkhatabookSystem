const state = {
  tab: "dashboard",
  bootstrap: null,
  customers: [],
  products: [],
  invoices: [],
};

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const ch of children) {
    if (typeof ch === "string") node.appendChild(document.createTextNode(ch));
    else if (ch) node.appendChild(ch);
  }
  return node;
}

async function apiGet(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

async function apiPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

function setSyncBadge(sync) {
  const badge = document.getElementById("syncBadge");
  if (!sync) {
    badge.textContent = "Offline";
    badge.className = "badge badge-warn";
    return;
  }
  if (!sync.online) {
    badge.textContent = "Offline";
    badge.className = "badge badge-warn";
    return;
  }
  if (sync.state === "syncing") {
    badge.textContent = "Syncing…";
    badge.className = "badge badge-neutral";
    return;
  }
  if (sync.state === "error") {
    badge.textContent = "Sync Error";
    badge.className = "badge badge-err";
    return;
  }
  badge.textContent = "Online";
  badge.className = "badge badge-ok";
}

function renderTabs() {
  const tabs = document.getElementById("tabs");
  tabs.innerHTML = "";
  const items = [
    ["dashboard", "Dashboard"],
    ["customers", "Customers"],
    ["products", "Products"],
    ["invoices", "Invoices"],
    ["new_invoice", "New Invoice"],
  ];
  for (const [key, label] of items) {
    tabs.appendChild(
      el(
        "button",
        {
          class: "tab" + (state.tab === key ? " active" : ""),
          onclick: () => {
            state.tab = key;
            render();
          },
        },
        [label]
      )
    );
  }
}

function money(v) {
  const n = Number(v || 0);
  return n.toFixed(2);
}

function renderDashboard(root) {
  const b = state.bootstrap;
  const sales = (b && b.sales) || { total_sales: 0, total_paid: 0, total_balance: 0 };
  const counts = (b && b.counts) || { customers: 0, products: 0, invoices: 0 };
  const recent = (b && b.recent_invoices) || [];

  root.appendChild(
    el("div", { class: "card" }, [
      el("h2", {}, ["Sales Summary"]),
      el("div", { class: "grid" }, [
        el("div", { class: "pill primary" }, [
          el("div", { class: "label" }, ["Total"]),
          el("div", { class: "value" }, [money(sales.total_sales)]),
        ]),
        el("div", { class: "pill success" }, [
          el("div", { class: "label" }, ["Paid"]),
          el("div", { class: "value" }, [money(sales.total_paid)]),
        ]),
        el("div", { class: "pill danger" }, [
          el("div", { class: "label" }, ["Balance"]),
          el("div", { class: "value" }, [money(sales.total_balance)]),
        ]),
      ]),
    ])
  );

  root.appendChild(
    el("div", { class: "card" }, [
      el("h2", {}, ["Quick Setup"]),
      el("div", { class: "muted" }, [`Customers: ${counts.customers} • Products: ${counts.products}`]),
      el("div", { class: "row", style: "margin-top:10px" }, [
        el("button", { class: "btn btn-solid", onclick: () => (state.tab = "customers", render()) }, ["Add Customer"]),
        el("button", { class: "btn btn-solid", onclick: () => (state.tab = "products", render()) }, ["Add Product"]),
        el("button", { class: "btn btn-solid", onclick: () => (state.tab = "new_invoice", render()) }, ["New Invoice"]),
      ]),
    ])
  );

  root.appendChild(el("div", { class: "card" }, [
    el("h2", {}, ["Recent Invoices"]),
    recent.length === 0
      ? el("div", { class: "muted" }, ['No invoices yet. Create one (offline).'])
      : el("table", { class: "table" }, [
          el("thead", {}, [
            el("tr", {}, [el("th", {}, ["Number"]), el("th", {}, ["Status"]), el("th", {}, ["Total"]), el("th", {}, ["Balance"])]),
          ]),
          el("tbody", {}, recent.map((inv) =>
            el("tr", {}, [
              el("td", {}, [String(inv.number || "")]),
              el("td", {}, [String(inv.status || "")]),
              el("td", {}, [money(inv.total)]),
              el("td", {}, [money(inv.balance)]),
            ])
          )),
        ]),
  ]));
}

function renderCustomers(root) {
  root.appendChild(el("div", { class: "card" }, [
    el("h2", {}, ["Customers (Offline)"]),
    el("div", { class: "form" }, [
      el("input", { id: "c_name", placeholder: "Name" }),
      el("input", { id: "c_phone", placeholder: "Phone (optional)" }),
      el("input", { id: "c_address", placeholder: "Address (optional)" }),
      el("button", {
        class: "btn btn-solid",
        onclick: async () => {
          const name = document.getElementById("c_name").value;
          const phone = document.getElementById("c_phone").value;
          const address = document.getElementById("c_address").value;
          await apiPost("/api/customers", { name, phone, address });
          await refreshData();
          state.tab = "customers";
          render();
        }
      }, ["Save Customer"]),
    ]),
  ]));

  root.appendChild(el("div", { class: "card" }, [
    el("h2", {}, ["Customer List"]),
    state.customers.length === 0 ? el("div", { class: "muted" }, ["No customers yet."]) :
      el("table", { class: "table" }, [
        el("thead", {}, [el("tr", {}, [el("th", {}, ["Name"]), el("th", {}, ["Phone"]), el("th", {}, ["Address"])])]),
        el("tbody", {}, state.customers.map((c) =>
          el("tr", {}, [el("td", {}, [c.name || ""]), el("td", {}, [c.phone || ""]), el("td", {}, [c.address || ""])])
        )),
      ]),
  ]));
}

function renderProducts(root) {
  root.appendChild(el("div", { class: "card" }, [
    el("h2", {}, ["Products (Offline)"]),
    el("div", { class: "form" }, [
      el("input", { id: "p_name", placeholder: "Name" }),
      el("input", { id: "p_sku", placeholder: "SKU (optional)" }),
      el("input", { id: "p_price", placeholder: "Price", value: "0" }),
      el("input", { id: "p_tax", placeholder: "Tax %", value: "0" }),
      el("button", {
        class: "btn btn-solid",
        onclick: async () => {
          const name = document.getElementById("p_name").value;
          const sku = document.getElementById("p_sku").value;
          const price = Number(document.getElementById("p_price").value || 0);
          const tax_percent = Number(document.getElementById("p_tax").value || 0);
          await apiPost("/api/products", { name, sku, price, tax_percent });
          await refreshData();
          state.tab = "products";
          render();
        }
      }, ["Save Product"]),
    ]),
  ]));

  root.appendChild(el("div", { class: "card" }, [
    el("h2", {}, ["Product List"]),
    state.products.length === 0 ? el("div", { class: "muted" }, ["No products yet."]) :
      el("table", { class: "table" }, [
        el("thead", {}, [el("tr", {}, [el("th", {}, ["Name"]), el("th", {}, ["SKU"]), el("th", {}, ["Price"]), el("th", {}, ["Tax %"])])]),
        el("tbody", {}, state.products.map((p) =>
          el("tr", {}, [el("td", {}, [p.name || ""]), el("td", {}, [p.sku || ""]), el("td", {}, [money(p.price)]), el("td", {}, [String(p.tax_percent ?? 0)])])
        )),
      ]),
  ]));
}

function renderInvoices(root) {
  root.appendChild(el("div", { class: "card" }, [
    el("h2", {}, ["Invoices (Offline)"]),
    el("div", { class: "muted" }, ["Tap New Invoice tab to create."]),
  ]));

  root.appendChild(el("div", { class: "card" }, [
    el("h2", {}, ["Invoice List"]),
    state.invoices.length === 0 ? el("div", { class: "muted" }, ["No invoices yet."]) :
      el("table", { class: "table" }, [
        el("thead", {}, [el("tr", {}, [el("th", {}, ["Number"]), el("th", {}, ["Status"]), el("th", {}, ["Total"]), el("th", {}, ["Balance"])])]),
        el("tbody", {}, state.invoices.map((inv) =>
          el("tr", {}, [el("td", {}, [inv.number || ""]), el("td", {}, [inv.status || ""]), el("td", {}, [money(inv.total)]), el("td", {}, [money(inv.balance)])])
        )),
      ]),
  ]));
}

function renderNewInvoice(root) {
  if (state.customers.length === 0 || state.products.length === 0) {
    root.appendChild(el("div", { class: "card" }, [
      el("h2", {}, ["New Invoice"]),
      el("div", { class: "muted" }, ["Add at least 1 customer and 1 product first."]),
      el("div", { class: "row", style: "margin-top:10px" }, [
        el("button", { class: "btn btn-solid", onclick: () => (state.tab = "customers", render()) }, ["Add Customer"]),
        el("button", { class: "btn btn-solid", onclick: () => (state.tab = "products", render()) }, ["Add Product"]),
      ]),
    ]));
    return;
  }

  const customerSelect = el("select", { id: "inv_customer" }, state.customers.map((c) => el("option", { value: c.id }, [c.name])));
  const itemRows = el("div", { id: "inv_items", class: "form" }, []);

  function addItemRow() {
    const productSelect = el("select", {}, state.products.map((p) => el("option", { value: p.id }, [p.name])));
    const qtyInput = el("input", { type: "number", value: "1", min: "1", step: "1" });
    itemRows.appendChild(el("div", { class: "row" }, [productSelect, qtyInput]));
  }

  addItemRow();

  root.appendChild(el("div", { class: "card" }, [
    el("h2", {}, ["Create Invoice (Offline)"]),
    el("div", { class: "form" }, [
      el("div", {}, [el("div", { class: "muted" }, ["Customer"]), customerSelect]),
      el("div", {}, [el("div", { class: "muted" }, ["Items"]), itemRows]),
      el("button", { class: "btn", onclick: addItemRow }, ["+ Add Item"]),
      el("input", { id: "inv_discount", placeholder: "Discount", value: "0" }),
      el("input", { id: "inv_paid", placeholder: "Paid", value: "0" }),
      el("button", {
        class: "btn btn-solid",
        onclick: async () => {
          const customer_id = document.getElementById("inv_customer").value;
          const discount = Number(document.getElementById("inv_discount").value || 0);
          const paid = Number(document.getElementById("inv_paid").value || 0);

          const items = [];
          for (const row of itemRows.children) {
            const sel = row.querySelector("select");
            const inp = row.querySelector("input");
            const product_id = sel.value;
            const qty = Number(inp.value || 0);
            if (qty > 0) items.push({ product_id, qty });
          }
          await apiPost("/api/invoices", { customer_id, items, discount, paid });
          await refreshData();
          state.tab = "invoices";
          render();
        }
      }, ["Create Invoice"]),
    ]),
  ]));
}

function render() {
  renderTabs();
  const root = document.getElementById("app");
  root.innerHTML = "";

  if (!state.bootstrap) {
    root.appendChild(el("div", { class: "card" }, ["Loading…"]));
    return;
  }

  if (state.tab === "dashboard") renderDashboard(root);
  else if (state.tab === "customers") renderCustomers(root);
  else if (state.tab === "products") renderProducts(root);
  else if (state.tab === "invoices") renderInvoices(root);
  else if (state.tab === "new_invoice") renderNewInvoice(root);
}

async function refreshData() {
  const b = await apiGet("/api/bootstrap");
  state.bootstrap = b;
  setSyncBadge(b.sync);

  const c = await apiGet("/api/customers");
  state.customers = c.rows || [];
  const p = await apiGet("/api/products");
  state.products = p.rows || [];
  const inv = await apiGet("/api/invoices");
  state.invoices = inv.rows || [];
}

async function init() {
  document.getElementById("btnSync").addEventListener("click", async () => {
    await apiPost("/api/sync/now", {});
    await refreshData();
    render();
  });
  await refreshData();
  render();
}

init().catch((e) => {
  const root = document.getElementById("app");
  root.innerHTML = "";
  root.appendChild(el("div", { class: "card" }, ["Error: " + String(e)]));
});

