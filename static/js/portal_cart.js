(function () {
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return "";
  }

  async function postJson(url, data) {
    const resp = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken") || "",
      },
      body: JSON.stringify(data || {}),
    });
    const json = await resp.json().catch(() => ({}));
    return { ok: resp.ok && json.ok, status: resp.status, json };
  }

  function setCartQty(qty) {
    const badge = document.getElementById("portalCartQty");
    if (!badge) return;
    badge.textContent = String(qty || 0);
  }

  function setMsg(text, isError) {
    const el = document.getElementById("portalCartMsg");
    if (!el) return;
    el.textContent = text || "";
    el.className = `mt-2 small ${isError ? "text-danger" : "text-muted"}`;
  }

  async function addToCart(productId, qty) {
    const q = Number(qty || 1);
    const res = await postJson("/portal/api/cart/add/", { product_id: productId, qty: q });
    if (!res.ok) {
      setMsg(res.json.error || "Failed to add to cart", true);
      return;
    }
    setCartQty(res.json.cart_qty || 0);
    setMsg("Added to cart.", false);
  }

  async function updateCartFromTable() {
    const table = document.getElementById("portalCartTable");
    if (!table) return;
    const rows = table.querySelectorAll("[data-product-row]");
    const items = [];
    rows.forEach((row) => {
      const pid = row.getAttribute("data-product-id");
      const qtyEl = row.querySelector("[data-cart-qty]");
      const qty = qtyEl ? Number(qtyEl.value || "0") : 0;
      items.push({ product_id: pid, qty });
    });
    const res = await postJson("/portal/api/cart/update/", { items });
    if (!res.ok) {
      setMsg(res.json.error || "Failed to update cart", true);
      return;
    }
    setCartQty(res.json.cart_qty || 0);
    setMsg(`Cart updated. Updated: ${res.json.updated || 0}, Removed: ${res.json.removed || 0}`, false);
    // Simple refresh to recalc totals on server side
    window.location.reload();
  }

  async function clearCart() {
    const res = await postJson("/portal/api/cart/clear/", {});
    if (!res.ok) {
      setMsg(res.json.error || "Failed to clear cart", true);
      return;
    }
    setMsg("Cart cleared.", false);
    window.location.reload();
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-add-cart]").forEach((btn) => {
      btn.addEventListener("click", function () {
        const pid = btn.getAttribute("data-product-id");
        const qtySel = btn.getAttribute("data-qty-input");
        let qty = 1;
        if (qtySel) {
          const el = document.querySelector(qtySel);
          if (el) qty = Number(el.value || "1");
        }
        addToCart(pid, qty);
      });
    });

    const updBtn = document.getElementById("portalCartUpdateBtn");
    if (updBtn) updBtn.addEventListener("click", updateCartFromTable);

    const clearBtn = document.getElementById("portalCartClearBtn");
    if (clearBtn) clearBtn.addEventListener("click", clearCart);
  });
})();

