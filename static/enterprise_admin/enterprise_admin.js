(function () {
  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  ready(function () {
    var root = document.documentElement;
    var body = document.body;
    var storedTheme = localStorage.getItem("be-admin-theme");
    if (storedTheme) {
      root.setAttribute("data-be-theme", storedTheme);
    }

    var themeToggle = document.getElementById("beAdminThemeToggle");
    if (themeToggle) {
      themeToggle.addEventListener("click", function () {
        var next = root.getAttribute("data-be-theme") === "dark" ? "light" : "dark";
        root.setAttribute("data-be-theme", next);
        localStorage.setItem("be-admin-theme", next);
      });
    }

    var search = document.getElementById("beAdminGlobalSearch");
    if (search) {
      search.addEventListener("keydown", function (event) {
        if (event.key !== "Enter") return;
        var value = search.value.trim();
        if (!value) return;
        window.location.href = "/superadmin/?q=" + encodeURIComponent(value);
      });
    }

    document.addEventListener("keydown", function (event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k" && search) {
        event.preventDefault();
        search.focus();
        search.select();
      }
    });

    var jazzySidebar = document.getElementById("jazzy-sidebar");
    var djangoSidebar = document.getElementById("nav-sidebar");
    if (jazzySidebar && djangoSidebar) {
      djangoSidebar.hidden = true;
    }
    var sidebars = Array.prototype.slice.call(document.querySelectorAll(".be-enterprise-sidebar:not([hidden])"));
    if (sidebars.length) {
      body.classList.add("be-admin-has-sidebar");
    }

    function setMobileState() {
      body.classList.toggle("be-admin-mobile", window.matchMedia("(max-width: 900px)").matches);
    }

    setMobileState();
    window.addEventListener("resize", setMobileState);

    function applySidebarState(collapsed) {
      body.classList.toggle("be-admin-sidebar-collapsed", collapsed);
      body.classList.toggle("sidebar-collapse", collapsed);
      sidebars.forEach(function (sidebar) {
        sidebar.setAttribute("aria-expanded", collapsed ? "false" : "true");
      });
      Array.prototype.slice.call(document.querySelectorAll("[data-be-sidebar-toggle]")).forEach(function (button) {
        button.title = collapsed ? "Expand sidebar" : "Collapse sidebar";
        button.setAttribute("aria-label", button.title);
      });
    }

    applySidebarState(localStorage.getItem("be-admin-sidebar-collapsed") === "true");

    document.addEventListener("click", function (event) {
      var toggle = event.target.closest && event.target.closest("[data-be-sidebar-toggle]");
      if (!toggle) return;
      event.preventDefault();
      if (body.classList.contains("be-admin-mobile")) {
        body.classList.toggle("be-admin-mobile-open");
        return;
      }
      var next = !body.classList.contains("be-admin-sidebar-collapsed");
      localStorage.setItem("be-admin-sidebar-collapsed", next ? "true" : "false");
      applySidebarState(next);
    });

    sidebars.forEach(function (sidebar) {
      var dashboardLink = sidebar.querySelector(".be-dashboard-link");
      if (dashboardLink) {
        dashboardLink.dataset.beTooltip = "Dashboard";
        dashboardLink.title = "Dashboard";
      }
      Array.prototype.slice.call(sidebar.querySelectorAll(".be-side-group-toggle")).forEach(function (button) {
        var title = button.querySelector(".be-side-title");
        var text = title ? title.textContent.trim() : "Menu group";
        button.dataset.beTooltip = text;
        button.title = text;
      });
      Array.prototype.slice.call(sidebar.querySelectorAll(".be-side-item")).forEach(function (item) {
        var label = item.querySelector(".be-side-item-label");
        var text = label ? label.textContent.trim() : "Open";
        item.dataset.beTooltip = text;
        item.title = text;
      });
    });

    Array.prototype.slice.call(document.querySelectorAll("[data-be-menu-groups]")).forEach(function (groupsRoot, rootIndex) {
      var groups = Array.prototype.slice.call(groupsRoot.querySelectorAll(".be-side-group"));
      groups.forEach(function (group, index) {
        var button = group.querySelector(".be-side-group-toggle");
        var storageKey = "be-admin-group:" + rootIndex + ":" + (group.dataset.group || index);
        var stored = localStorage.getItem(storageKey);
        var open = stored ? stored === "true" : index === 0;
        group.dataset.open = open ? "true" : "false";
        if (button) {
          button.setAttribute("aria-expanded", open ? "true" : "false");
          button.addEventListener("click", function () {
            var next = group.dataset.open !== "true";
            group.dataset.open = next ? "true" : "false";
            button.setAttribute("aria-expanded", next ? "true" : "false");
            localStorage.setItem(storageKey, next ? "true" : "false");
          });
        }
      });
    });

    Array.prototype.slice.call(document.querySelectorAll("[data-be-menu-search]")).forEach(function (menuSearch) {
      var sidebar = menuSearch.closest(".be-enterprise-sidebar") || document;
      var groupsRoot = sidebar.querySelector("[data-be-menu-groups]");
      if (!groupsRoot) return;
      menuSearch.addEventListener("input", function () {
        var term = menuSearch.value.trim().toLowerCase();
        var groups = Array.prototype.slice.call(groupsRoot.querySelectorAll(".be-side-group"));
        groups.forEach(function (group) {
          var title = group.dataset.group || "";
          var items = Array.prototype.slice.call(group.querySelectorAll(".be-side-item"));
          var visibleCount = 0;
          items.forEach(function (item) {
            var haystack = item.dataset.label || "";
            var visible = !term || haystack.indexOf(term) !== -1 || title.indexOf(term) !== -1;
            item.classList.toggle("be-side-empty", !visible);
            if (visible) visibleCount += 1;
          });
          var groupVisible = !term || visibleCount > 0 || title.indexOf(term) !== -1;
          group.classList.toggle("be-side-empty", !groupVisible);
          if (term && groupVisible) {
            group.dataset.open = "true";
            var button = group.querySelector(".be-side-group-toggle");
            if (button) button.setAttribute("aria-expanded", "true");
          }
        });
      });
    });

    document.addEventListener("click", function (event) {
      var add = event.target.closest && event.target.closest(".be-side-add");
      if (!add) return;
      event.preventDefault();
      event.stopPropagation();
      var url = add.getAttribute("data-add-url");
      if (url) window.location.href = url;
    });

    function updateDashboardRealtime(data) {
      if (!data || !data.kpis) return;
      Object.keys(data.kpis).forEach(function (key) {
        var el = document.querySelector('[data-be-live-kpi="' + key + '"]');
        if (!el) return;
        el.textContent = data.kpis[key].formatted || data.kpis[key].value || "0";
      });
      var status = document.querySelector("[data-be-realtime-status]");
      if (status) {
        status.textContent = data.status || "Live";
        status.dataset.state = data.status === "live" ? "live" : "poll";
      }
      var activity = document.querySelector("[data-be-live-activity]");
      if (activity && Array.isArray(data.activities)) {
        activity.innerHTML = data.activities.map(function (row) {
          return '<li><strong>' + escapeHtml(row.action || "Activity") + '</strong><span>' +
            escapeHtml(row.actor || "System") + '</span><small>' + escapeHtml(row.when || "") + '</small></li>';
        }).join("") || '<li><strong>No activity yet</strong><span>System</span><small>Ready</small></li>';
      }
    }

    function escapeHtml(value) {
      return String(value || "").replace(/[&<>"']/g, function (ch) {
        return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[ch];
      });
    }

    if (document.querySelector("[data-be-realtime-status]")) {
      var wsUrl = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/enterprise/dashboard/";
      var socket;
      try {
        socket = new WebSocket(wsUrl);
        socket.onmessage = function (event) {
          try { updateDashboardRealtime(JSON.parse(event.data)); } catch (err) {}
        };
      } catch (err) {}

      function pollRealtime() {
        fetch("/superadmin/api/dashboard-realtime/", { credentials: "same-origin" })
          .then(function (res) { return res.ok ? res.json() : Promise.reject(); })
          .then(updateDashboardRealtime)
          .catch(function () {});
      }
      pollRealtime();
      window.setInterval(pollRealtime, 30000);
    }
  });
})();
