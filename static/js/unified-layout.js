(function () {
  function onReady(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  onReady(function () {
    document.body.classList.add('uc-ready');
    const path = (window.location.pathname || '').toLowerCase();
    const modeClassExists = ['mode-pc', 'mode-pos', 'mode-tablet', 'mode-mobile', 'mode-embedded']
      .some(function (c) { return document.body.classList.contains(c); });
    if (!modeClassExists) {
      document.body.classList.add('mode-pc');
    }

    const addLikePath = [
      '/add-',
      '/add/',
      '/create/',
      '/new/',
      '/edit/',
      '/expense/create',
      '/sales-voucher/create',
      '/voucher/create',
    ].some(function (token) { return path.indexOf(token) !== -1; });
    const headingText = ((document.querySelector('h1,h2,h3,h4,h5') || {}).textContent || '').toLowerCase();
    const addLikeHeading = headingText.indexOf('add') !== -1 || headingText.indexOf('create') !== -1;
    const hasPrimaryForm = !!document.querySelector('form');
    const addLikeDom = !!document.querySelector(
      '.busy-unified-add, .unified-screen, .order-card, .transaction-card, #mainOrderCard, #mainPartyCard, #mainPaymentCard, #mainExpenseCard'
    );
    if ((addLikePath || addLikeHeading) && hasPrimaryForm) {
      document.body.classList.add('add-screen');
    }
    if (!document.body.classList.contains('add-screen') && addLikeDom) {
      document.body.classList.add('add-screen');
    }
    if (document.body.classList.contains('add-screen')) {
      // Re-attach mode stylesheet at runtime so it wins over late-loaded legacy CSS.
      var existing = document.getElementById('pc-add-mode-runtime');
      if (existing) existing.remove();
      var link = document.createElement('link');
      link.id = 'pc-add-mode-runtime';
      link.rel = 'stylesheet';
      link.href = '/static/css/pc_add_mode.css?v=20260222a';
      document.head.appendChild(link);
    }

    // Generic locked-feature behavior fallback.
    document.addEventListener('click', function (e) {
      const el = e.target.closest('.locked-feature[data-upgrade-url]');
      if (!el) return;
      e.preventDefault();
      window.location.href = el.dataset.upgradeUrl;
    });

    function hasBootstrapDropdown() {
      return !!(window.bootstrap && window.bootstrap.Dropdown);
    }

    function closeAllDropdowns(exceptDropdown) {
      document.querySelectorAll('.dropdown-menu.show').forEach(function (menu) {
        const dd = menu.closest('.dropdown');
        if (exceptDropdown && dd === exceptDropdown) return;
        menu.classList.remove('show');
        if (dd) dd.classList.remove('show');
      });
    }

    // Fallback dropdown behavior for environments where Bootstrap JS isn't available
    // (e.g. CDN blocked/offline). Works with both `data-bs-toggle="dropdown"` and
    // legacy `data-toggle="dropdown"` toggles.
    document.addEventListener('click', function (e) {
      const toggle = e.target.closest('[data-bs-toggle="dropdown"],[data-toggle="dropdown"],.dropdown-toggle');
      if (!toggle) {
        if (!e.target.closest('.dropdown-menu')) closeAllDropdowns(null);
        return;
      }

      const dropdown = toggle.closest('.dropdown');
      const menu = dropdown ? dropdown.querySelector('.dropdown-menu') : null;
      if (!dropdown || !menu) return;

      if (hasBootstrapDropdown()) return;

      e.preventDefault();
      e.stopPropagation();

      const willOpen = !menu.classList.contains('show');
      closeAllDropdowns(dropdown);
      if (willOpen) {
        dropdown.classList.add('show');
        menu.classList.add('show');
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeAllDropdowns(null);
    });
  });
})();
