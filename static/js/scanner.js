 (function (global) {
  const state = { items: [] };

  function detectType(code) {
    if (!code) return "unknown";
    if (/^https?:\/\//.test(code) || code.length > 20) return "qr";
    if (/^\d{8,14}$/.test(code)) return "ean";
    if (code.includes("-")) return "code128";
    return "generic";
  }

  function findProductByCode(code) {
    const url = `/api/v1/products/?search=${encodeURIComponent(code)}`;
    return fetch(url, { credentials: 'same-origin' })
      .then(r => r.json())
      .then(data => {
        if (Array.isArray(data) && data.length) return data[0];
        if (data && Array.isArray(data.results) && data.results.length) return data.results[0];
        return null;
      })
      .catch(() => null);
  }

  function addItem(product, code, refs) {
    const item = {
      code: code || (product && (product.barcode || product.sku || product.id)),
      name: product ? product.name : code,
      qty: 1,
      price: product ? parseFloat(product.price || product.mrp || 0) : 0,
      product_id: product ? product.id : null,
    };
    state.items.push(item);
    render(refs);
  }

  function render(refs) {
    refs.lineItems.innerHTML = state.items.map((x, i) => `\n      <div style="display:flex;justify-content:space-between;padding:6px;border-bottom:1px dashed #eee">\n        <div style="flex:1">${i + 1}. <strong>${x.name}</strong><div style="font-size:12px;color:#666">${x.code}</div></div>\n        <div style="width:120px;text-align:right">${x.qty} × ${(x.price).toFixed(2)}</div>\n      </div>\n    `).join("");
    const total = state.items.reduce((a, x) => a + x.qty * x.price, 0);
    refs.total.textContent = `Total: ${total.toFixed(2)}`;
  }

  function queueOffline(payload) {
    const key = "pos_offline_queue";
    const queue = JSON.parse(localStorage.getItem(key) || "[]");
    queue.push(payload);
    localStorage.setItem(key, JSON.stringify(queue));
  }

  function bindShortcuts(refs) {
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        state.items = [];
        render(refs);
      }
      if (e.key === "F5") {
        queueOffline({ type: "hold_bill", items: state.items, at: Date.now() });
        if (refs.notice) refs.notice.textContent = "Bill held offline";
      }
    });
  }

  function init(cfg) {
    const refs = {
      input: document.getElementById(cfg.inputId),
      lineItems: document.getElementById(cfg.lineItemsId),
      total: document.getElementById(cfg.totalId),
      sound: document.getElementById(cfg.soundId),
      notice: document.getElementById(cfg.noticeId || "pos-notice"),
    };

    bindShortcuts(refs);

    async function handleCode(code) {
      if (!code) return;
      const product = await findProductByCode(code);
      addItem(product, code, refs);
      refs.input.value = "";
      if (refs.sound) refs.sound.play().catch(() => {});
      if (navigator.vibrate) navigator.vibrate(20);
    }

    refs.input.addEventListener("change", () => handleCode(refs.input.value.trim()));
    refs.input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleCode(refs.input.value.trim());
      }
    });

    const syncBtn = document.getElementById("sync-btn");
    if (syncBtn) {
      syncBtn.addEventListener("click", async () => {
        const key = "pos_offline_queue";
        const queue = JSON.parse(localStorage.getItem(key) || "[]");
        for (const payload of queue) {
          try {
            await fetch('/api/v1/pos/hold/', { method: 'POST', credentials: 'same-origin', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) });
          } catch (err) {
            console.warn('sync failed', err);
          }
        }
        localStorage.setItem(key, '[]');
        if (refs.notice) refs.notice.textContent = 'Synced pending bills';
      });
    }

    function getCookie(name) {
      const value = `; ${document.cookie}`;
      const parts = value.split(`; ${name}=`);
      if (parts.length === 2) return parts.pop().split(';').shift();
      return null;
    }

    async function checkout(tenderAmt) {
      const total = state.items.reduce((a, x) => a + x.qty * x.price, 0);
      const payload = {
        items: state.items.map(i => ({ product_id: i.product_id, code: i.code, name: i.name, qty: i.qty, unit_price: i.price })),
        total,
        payment: { method: 'cash', tender: tenderAmt },
      };

      try {
        const resp = await fetch('/api/v1/orders/orders/quick_place/', {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken') || '',
          },
          body: JSON.stringify(payload),
        });

        if (resp.status === 201 || resp.ok) {
          const data = await resp.json();
          if (refs.notice) refs.notice.textContent = 'Order placed: ' + (data.id || data.order_number || 'ok');
          await doPrint();
          state.items = [];
          render(refs);
          return true;
        }

        const err = await resp.text();
        console.warn('checkout failed', resp.status, err);
        if (refs.notice) refs.notice.textContent = 'Checkout failed';
        return false;
      } catch (err) {
        console.warn('checkout error', err);
        if (refs.notice) refs.notice.textContent = 'Checkout error';
        return false;
      }
    }

    const payBtn = document.getElementById('pay-btn');
    if (payBtn) {
      payBtn.addEventListener('click', async () => {
        const total = state.items.reduce((a, x) => a + x.qty * x.price, 0);
        const tender = prompt('Enter tender amount (cash) — total ' + total.toFixed(2));
        const tenderAmt = parseFloat(tender || '0');
        if (isNaN(tenderAmt)) {
          alert('Invalid amount');
          return;
        }
        if (tenderAmt < total) {
          alert('Insufficient amount');
          return;
        }

        const ok = await checkout(tenderAmt);
        if (ok) {
          alert('Payment accepted. Change: ' + (tenderAmt - total).toFixed(2));
        }
      });
    }

    const printBtn = document.getElementById('print-btn');
    async function doPrint() {
      const total = state.items.reduce((a, x) => a + x.qty * x.price, 0);
      const payload = { items: state.items, total };
      try {
        await fetch('/api/v1/printers/print/', { method: 'POST', credentials: 'same-origin', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) });
        if (refs.notice) refs.notice.textContent = 'Sent to printer';
      } catch (err) {
        console.warn('printer error', err);
        if (refs.notice) refs.notice.textContent = 'Printer error';
      }
    }

    if (printBtn) printBtn.addEventListener('click', doPrint);
  }

  global.POSScanner = { init, detectType };
})(window);
