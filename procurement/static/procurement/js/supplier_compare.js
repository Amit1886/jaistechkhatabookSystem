(function () {
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return "";
  }

  const csrfToken = getCookie("csrftoken");

  function toast(type, message) {
    window.dispatchEvent(
      new CustomEvent("ui:toast", { detail: { type: type || "info", message: message || "" } })
    );
  }

  function parseNum(val) {
    const n = Number(val);
    return Number.isFinite(n) ? n : 0;
  }

  function drawTrend(canvas, points) {
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width = canvas.clientWidth;
    const h = canvas.height = canvas.height || 140;
    ctx.clearRect(0, 0, w, h);

    if (!points || points.length < 2) {
      ctx.fillStyle = "#6b7280";
      ctx.font = "14px system-ui, -apple-system, Segoe UI, Roboto, Arial";
      ctx.fillText("No price history available.", 16, 28);
      return;
    }

    const padding = 28;
    const values = points.map((p) => parseNum(p.value));
    const min = Math.min.apply(null, values);
    const max = Math.max.apply(null, values);
    const span = max - min || 1;

    // Axis
    ctx.strokeStyle = "#e5e7eb";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, h - padding);
    ctx.lineTo(w - padding, h - padding);
    ctx.stroke();

    // Labels
    ctx.fillStyle = "#6b7280";
    ctx.font = "12px system-ui, -apple-system, Segoe UI, Roboto, Arial";
    ctx.fillText(`₹${max.toFixed(2)}`, 6, padding + 4);
    ctx.fillText(`₹${min.toFixed(2)}`, 6, h - padding);

    const xStep = (w - (padding * 2)) / (points.length - 1);
    const yScale = (h - (padding * 2)) / span;

    // Line
    ctx.strokeStyle = "#2563eb";
    ctx.lineWidth = 2;
    ctx.beginPath();
    points.forEach((p, idx) => {
      const x = padding + (idx * xStep);
      const y = (h - padding) - ((parseNum(p.value) - min) * yScale);
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Dots
    ctx.fillStyle = "#2563eb";
    points.forEach((p, idx) => {
      const x = padding + (idx * xStep);
      const y = (h - padding) - ((parseNum(p.value) - min) * yScale);
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  async function loadTrend(productId, supplierId) {
    const url = `/api/supplier-price-history/?product_id=${encodeURIComponent(productId)}&supplier_id=${encodeURIComponent(supplierId)}`;
    const resp = await fetch(url, { headers: { "Accept": "application/json" } });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const rows = await resp.json();
    const list = Array.isArray(rows) ? rows : (rows && Array.isArray(rows.results) ? rows.results : []);

    // Show oldest -> newest
    const ordered = (list || []).slice().reverse();
    const points = ordered.map((r) => ({
      label: (r.updated_at || "").slice(0, 10),
      value: parseNum(r.new_price),
    }));
    return points;
  }

  function wireTrendButtons() {
    const canvas = document.getElementById("priceTrendCanvas");
    document.querySelectorAll("[data-trend]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const productId = btn.getAttribute("data-product-id");
        const supplierId = btn.getAttribute("data-supplier-id");
        if (!productId || !supplierId) return;
        btn.disabled = true;
        try {
          const points = await loadTrend(productId, supplierId);
          drawTrend(canvas, points);
          toast("success", "Trend loaded.");
        } catch (e) {
          drawTrend(canvas, []);
          toast("error", `Could not load trend: ${e && e.message ? e.message : "error"}`);
        } finally {
          btn.disabled = false;
        }
      });
    });
  }

  function wireRatingModal() {
    const modalEl = document.getElementById("rateSupplierModal");
    if (!modalEl || typeof bootstrap === "undefined") return;
    const modal = new bootstrap.Modal(modalEl);

    const supplierNameEl = document.getElementById("rateSupplierName");
    const supplierIdEl = document.getElementById("rateSupplierId");
    const deliveryEl = document.getElementById("rateDelivery");
    const qualityEl = document.getElementById("rateQuality");
    const pricingEl = document.getElementById("ratePricing");
    const commentEl = document.getElementById("rateComment");
    const submitBtn = document.getElementById("rateSubmitBtn");

    document.querySelectorAll("[data-rate]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const supplierId = btn.getAttribute("data-supplier-id");
        const supplierName = btn.getAttribute("data-supplier-name") || "Supplier";
        if (!supplierId) return;
        supplierIdEl.value = supplierId;
        supplierNameEl.textContent = supplierName;
        deliveryEl.value = 3;
        qualityEl.value = 3;
        pricingEl.value = 3;
        commentEl.value = "";
        modal.show();
      });
    });

    if (!submitBtn) return;
    submitBtn.addEventListener("click", async () => {
      const supplierId = supplierIdEl.value;
      if (!supplierId) return;
      submitBtn.disabled = true;
      try {
        const payload = {
          supplier_id: supplierId,
          delivery_speed: parseInt(deliveryEl.value || "3", 10),
          product_quality: parseInt(qualityEl.value || "3", 10),
          pricing: parseInt(pricingEl.value || "3", 10),
          comment: commentEl.value || "",
        };

        const resp = await fetch("/api/supplier-ratings/upsert/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
            "Accept": "application/json",
          },
          body: JSON.stringify(payload),
        });
        if (!resp.ok) {
          const txt = await resp.text();
          throw new Error(txt || `HTTP ${resp.status}`);
        }
        toast("success", "Rating saved. Refreshing recommendations...");
        modal.hide();
        setTimeout(() => window.location.reload(), 600);
      } catch (e) {
        toast("error", `Could not save rating: ${e && e.message ? e.message : "error"}`);
      } finally {
        submitBtn.disabled = false;
      }
    });
  }

  function wireWhatsAppOrder() {
    document.querySelectorAll("[data-wa-order]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const supplierId = btn.getAttribute("data-supplier-id");
        const productId = btn.getAttribute("data-product-id");
        const price = btn.getAttribute("data-price") || "0";
        const moq = btn.getAttribute("data-moq") || "1";
        if (!supplierId || !productId) return;

        const qtyStr = window.prompt("Enter quantity to order:", String(moq || "1"));
        if (!qtyStr) return;
        const qty = parseInt(qtyStr, 10);
        if (!Number.isFinite(qty) || qty <= 0) {
          toast("warning", "Invalid quantity.");
          return;
        }

        btn.disabled = true;
        try {
          const form = new FormData();
          form.append("supplier_id", supplierId);
          form.append("product_id", productId);
          form.append("qty", String(qty));
          form.append("price", String(price));

          const resp = await fetch("/procurement/api/send-whatsapp-order/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken },
            body: form,
          });
          const data = await resp.json().catch(() => ({}));
          if (!resp.ok || !data.ok) {
            throw new Error(data.detail || data.response || `HTTP ${resp.status}`);
          }
          toast("success", "WhatsApp order sent.");
        } catch (e) {
          toast("error", `WhatsApp send failed: ${e && e.message ? e.message : "error"}`);
        } finally {
          btn.disabled = false;
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    wireTrendButtons();
    wireRatingModal();
    wireWhatsAppOrder();
  });
})();
