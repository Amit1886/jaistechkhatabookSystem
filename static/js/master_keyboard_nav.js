(function () {
  if (window.__MASTER_KEYBOARD_NAV_INSTALLED__ === true) return;
  window.__MASTER_KEYBOARD_NAV_INSTALLED__ = true;

  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
      return;
    }
    fn();
  }

  function isVisible(el) {
    return !!(el && el.offsetParent !== null && !el.disabled);
  }

  function focusableInForm(form) {
    const selector = [
      'input:not([type="hidden"]):not([disabled])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      'button:not([disabled])'
    ].join(',');
    return Array.from(form.querySelectorAll(selector)).filter(isVisible);
  }

  function nextFocusable(form, current) {
    const focusables = focusableInForm(form);
    const idx = focusables.indexOf(current);
    if (idx < 0) return null;
    return focusables[idx + 1] || null;
  }

  function prevFocusable(form, current) {
    const focusables = focusableInForm(form);
    const idx = focusables.indexOf(current);
    if (idx <= 0) return null;
    return focusables[idx - 1] || null;
  }

  function handleEnterNavigation(e) {
    const el = e.target;
    if (!el) return;
    if (el.tagName === 'TEXTAREA') return;
    if (el.type === 'checkbox' || el.type === 'radio' || el.type === 'submit' || el.type === 'button') return;
    const form = el.form || el.closest('form');
    if (!form) return;

    const focusables = focusableInForm(form);
    const idx = focusables.indexOf(el);
    if (idx < 0) return;
    const last = idx === focusables.length - 1;

    if (last || el.hasAttribute('data-enter-submit')) {
      e.preventDefault();
      if (typeof form.requestSubmit === 'function') {
        form.requestSubmit();
      } else {
        form.submit();
      }
      return;
    }

    const next = nextFocusable(form, el);
    if (next) {
      e.preventDefault();
      next.focus();
      if (next.select && (next.type === 'number' || next.type === 'text')) next.select();
    }
  }

  function handleShiftEnterBack(e) {
    const el = e.target;
    if (!el || el.tagName === 'TEXTAREA') return;
    const form = el.form || el.closest('form');
    if (!form) return;
    const prev = prevFocusable(form, el);
    if (prev) {
      e.preventDefault();
      prev.focus();
      if (prev.select && (prev.type === 'number' || prev.type === 'text')) prev.select();
    }
  }

  function handleNumericArrowNavigation(e) {
    const el = e.target;
    if (!el || el.tagName !== 'INPUT') return;
    const isNumeric = el.type === 'number' || el.classList.contains('qty') || el.classList.contains('amount') || el.classList.contains('price') || el.classList.contains('discount');
    if (!isNumeric) return;

    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;

    const currentTd = el.closest('td');
    const currentTr = el.closest('tr');
    if (!currentTd || !currentTr) return;

    const colIndex = Array.from(currentTr.children).indexOf(currentTd);
    if (colIndex < 0) return;

    let targetTr = e.key === 'ArrowDown' ? currentTr.nextElementSibling : currentTr.previousElementSibling;
    while (targetTr && targetTr.tagName !== 'TR') {
      targetTr = e.key === 'ArrowDown' ? targetTr.nextElementSibling : targetTr.previousElementSibling;
    }
    if (!targetTr) return;

    const targetTd = targetTr.children[colIndex];
    if (!targetTd) return;

    const targetInput = targetTd.querySelector('input, select, textarea');
    if (!targetInput || !isVisible(targetInput)) return;

    e.preventDefault();
    targetInput.focus();
    if (targetInput.select) targetInput.select();
  }

  function normalizeDateInput(raw) {
    if (!raw) return '';
    const val = raw.trim();
    const ddmmyyyy = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/;
    const match = val.match(ddmmyyyy);
    if (!match) return val;
    const dd = match[1].padStart(2, '0');
    const mm = match[2].padStart(2, '0');
    const yyyy = match[3];
    return `${yyyy}-${mm}-${dd}`;
  }

  function enhanceDateFields(root) {
    root.querySelectorAll('input[type="date"], input[data-date-input="1"]').forEach(function (input) {
      if (!input.getAttribute('placeholder')) {
        input.setAttribute('placeholder', 'DD/MM/YYYY');
      }

      input.addEventListener('blur', function () {
        if (input.type === 'date') {
          const normalized = normalizeDateInput(input.value);
          if (/^\d{4}-\d{2}-\d{2}$/.test(normalized)) {
            input.value = normalized;
          }
          return;
        }

        const normalized = normalizeDateInput(input.value);
        if (/^\d{4}-\d{2}-\d{2}$/.test(normalized)) {
          input.value = normalized;
        }
      });
    });
  }

  function enhanceSelectKeyboard(root) {
    root.querySelectorAll('select').forEach(function (select) {
      select.addEventListener('keydown', function (e) {
        if (e.key === ' ' || e.key === 'Spacebar' || e.key === 'ArrowDown') {
          if (typeof select.showPicker === 'function') {
            try {
              select.showPicker();
              e.preventDefault();
            } catch (err) {
              // Ignore and let native behavior continue.
            }
          }
        }
      });
    });
  }

  function applyTabindex(root) {
    let index = 1;
    root.querySelectorAll('form').forEach(function (form) {
      focusableInForm(form).forEach(function (el) {
        if (!el.hasAttribute('tabindex')) {
          el.setAttribute('tabindex', String(index));
          index += 1;
        }
      });
    });
  }

  function enhanceNumericFocusSelection(root) {
    root.querySelectorAll('input[type="number"], input.amount, input.qty, input.price, input.discount').forEach(function (input) {
      input.addEventListener('focus', function () {
        if (typeof input.select === 'function') input.select();
      });
    });
  }

  ready(function () {
    // Only on add/create screens (keyboard-first data entry)
    const isAddScreen = document.body && document.body.classList && document.body.classList.contains('add-screen');
    const isOrderEntry = (window.__ADD_ORDER_PC_BUSY__ === true) || !!document.querySelector('.busy-order-pc, #orderBody, #mainOrderCard');
    if (!isAddScreen || isOrderEntry) return;

    const root = document;
    applyTabindex(root);
    enhanceDateFields(root);
    enhanceSelectKeyboard(root);
    enhanceNumericFocusSelection(root);

    document.addEventListener('keydown', function (e) {
      const target = e.target;
      if (!target) return;

      if ((e.key === 'Enter' || e.keyCode === 13) && e.shiftKey) {
        handleShiftEnterBack(e);
        return;
      }

      if ((e.key === 'Enter' || e.keyCode === 13) && !e.shiftKey) {
        handleEnterNavigation(e);
        return;
      }

      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        handleNumericArrowNavigation(e);
      }

      if ((e.key === ' ' || e.key === 'Spacebar') && target.type === 'checkbox') {
        e.preventDefault();
        target.checked = !target.checked;
        target.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
  });
})();
