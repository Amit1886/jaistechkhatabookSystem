(function () {
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return "";
  }

  function toast(type, message) {
    window.dispatchEvent(
      new CustomEvent("ui:toast", { detail: { type: type || "info", message: message || "" } })
    );
  }

  function isPurchaseMode() {
    const orderType = document.getElementById("orderType");
    return orderType && String(orderType.value || "").toLowerCase() === "purchase";
  }

  async function fetchBestSupplier(productId) {
    const resp = await fetch(`/api/best-supplier/${encodeURIComponent(productId)}/`, {
      headers: { Accept: "application/json" },
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const ct = resp.headers.get("content-type") || "";
    if (ct.indexOf("application/json") === -1) throw new Error("Not JSON response");
    return await resp.json();
  }

  function findRowParts(row) {
    if (!row) return {};
    return {
      row,
      productSelect: row.querySelector("select.product"),
      compareBtn: row.querySelector(".compare-suppliers-btn"),
      recoEl: row.querySelector(".supplier-recommendation"),
      qtyEl: row.querySelector("input.qty"),
      priceEl: row.querySelector("input.price"),
    };
  }

  function updateCompareVisibility(row) {
    const parts = findRowParts(row);
    if (!parts.compareBtn || !parts.productSelect) return;
    const hasProduct = !!parts.productSelect.value;
    if (isPurchaseMode() && hasProduct) {
      parts.compareBtn.style.display = "";
    } else {
      parts.compareBtn.style.display = "none";
      if (parts.recoEl) parts.recoEl.style.display = "none";
    }
  }

  function updateAllRows() {
    document.querySelectorAll("#orderBody tr.item-row").forEach(updateCompareVisibility);
  }

  function buildModalRow(opt, best) {
    const isBest = best && String(opt.supplier_product_id) === String(best.supplier_product_id);
    const tr = document.createElement("tr");
    if (isBest) tr.className = "table-success";
    tr.innerHTML = `
      <td class="fw-bold">${opt.supplier_name || "Supplier"}</td>
      <td class="text-end fw-bold">₹${opt.price}</td>
      <td class="text-center">${opt.moq || 1}</td>
      <td class="text-center">${opt.delivery_days || 0} d</td>
      <td class="text-center">${Number(opt.avg_rating || 0).toFixed(2)} <span class="text-muted small">(${opt.rating_count || 0})</span></td>
      <td class="text-center">${isBest ? '<span class="badge bg-success fw-bold">Recommended</span>' : '<span class="text-muted">-</span>'}</td>
    `;
    return tr;
  }

  function wireProductChange(row) {
    const parts = findRowParts(row);
    if (!parts.productSelect) return;

    parts.productSelect.addEventListener("change", async () => {
      updateCompareVisibility(row);
      if (!isPurchaseMode()) return;
      const productId = parts.productSelect.value;
      if (!productId) return;

      try {
        const data = await fetchBestSupplier(productId);
        const best = data.best;
        if (best && parts.recoEl) {
          parts.recoEl.textContent = `Recommended: ${best.supplier_name} @ ₹${best.price} (MOQ ${best.moq}, ${best.delivery_days}d)`;
          parts.recoEl.style.display = "";
          row.dataset.bestSupplierId = String(best.supplier_id);
          row.dataset.bestPrice = String(best.price);
          row.dataset.bestMoq = String(best.moq || 1);
        } else if (parts.recoEl) {
          parts.recoEl.style.display = "none";
        }
      } catch (e) {
        if (parts.recoEl) parts.recoEl.style.display = "none";
      }
    });
  }

  function wireCompareButton(row, modal) {
    const parts = findRowParts(row);
    if (!parts.compareBtn || !parts.productSelect) return;

    parts.compareBtn.addEventListener("click", async () => {
      if (!isPurchaseMode()) {
        toast("warning", "Switch to Purchase mode to compare suppliers.");
        return;
      }
      const productId = parts.productSelect.value;
      if (!productId) return;

      // Modal state
      const tbody = document.getElementById("supplierCompareTbody");
      const applyBtn = document.getElementById("spcApplyBtn");
      const productNameEl = document.getElementById("spcProductName");
      if (!tbody || !applyBtn || !productNameEl) return;

      const selectedOpt = parts.productSelect.options[parts.productSelect.selectedIndex];
      productNameEl.textContent = selectedOpt ? selectedOpt.textContent : "-";
      tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">Loading…</td></tr>`;
      applyBtn.disabled = true;

      // Store active row
      window.__SPC_ACTIVE_ROW__ = row;

      modal.show();
      try {
        const data = await fetchBestSupplier(productId);
        const best = data.best;
        const opts = data.options || [];
        tbody.innerHTML = "";
        if (!opts.length) {
          tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No supplier mapping found.</td></tr>`;
          return;
        }
        opts.forEach((opt) => tbody.appendChild(buildModalRow(opt, best)));

        if (best) {
          applyBtn.disabled = false;
          applyBtn.dataset.bestSupplierId = String(best.supplier_id);
          applyBtn.dataset.bestPrice = String(best.price);
          applyBtn.dataset.bestMoq = String(best.moq || 1);
        }
      } catch (e) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger">Could not load comparison.</td></tr>`;
      }
    });
  }

  function wireApplyButton(modal) {
    const applyBtn = document.getElementById("spcApplyBtn");
    if (!applyBtn) return;
    applyBtn.addEventListener("click", () => {
      const row = window.__SPC_ACTIVE_ROW__;
      if (!row) return;

      const supplierId = applyBtn.dataset.bestSupplierId;
      const bestPrice = applyBtn.dataset.bestPrice;
      const bestMoq = parseInt(applyBtn.dataset.bestMoq || "1", 10);

      const partySelect = document.getElementById("partySelect");
      if (partySelect && supplierId) {
        partySelect.value = supplierId;
        partySelect.dispatchEvent(new Event("change", { bubbles: true }));
      }

      const parts = findRowParts(row);
      if (parts.priceEl && bestPrice) {
        parts.priceEl.value = bestPrice;
        parts.priceEl.dispatchEvent(new Event("input", { bubbles: true }));
      }
      if (parts.qtyEl && Number.isFinite(bestMoq) && bestMoq > 0) {
        const currentQty = parseInt(parts.qtyEl.value || "1", 10) || 1;
        if (currentQty < bestMoq) {
          parts.qtyEl.value = String(bestMoq);
          parts.qtyEl.dispatchEvent(new Event("input", { bubbles: true }));
        }
      }

      modal.hide();
      toast("success", "Recommended supplier applied to purchase order.");
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (typeof bootstrap === "undefined") return;
    const modalEl = document.getElementById("supplierCompareModal");
    if (!modalEl) return;
    const modal = new bootstrap.Modal(modalEl);

    // Wire existing rows
    document.querySelectorAll("#orderBody tr.item-row").forEach((row) => {
      wireProductChange(row);
      wireCompareButton(row, modal);
      updateCompareVisibility(row);
    });

    wireApplyButton(modal);

    // React to order type switch
    const orderType = document.getElementById("orderType");
    if (orderType) {
      orderType.addEventListener("change", updateAllRows);
    }

    // Rows can be added dynamically (F4) by add_order scripts; observe for new rows.
    const body = document.getElementById("orderBody");
    if (body && window.MutationObserver) {
      const obs = new MutationObserver(() => {
        document.querySelectorAll("#orderBody tr.item-row").forEach((row) => {
          if (row.dataset.spcWired === "1") return;
          row.dataset.spcWired = "1";
          wireProductChange(row);
          wireCompareButton(row, modal);
          updateCompareVisibility(row);
        });
      });
      obs.observe(body, { childList: true, subtree: false });
    }
  });
})();

