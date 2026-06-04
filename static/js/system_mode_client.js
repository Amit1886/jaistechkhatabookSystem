(function () {
  function getWsUrl(path) {
    var protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return protocol + "//" + window.location.host + path;
  }

  function applyModeData(payload) {
    if (!payload) return;
    if (payload.current_mode) {
      document.body.dataset.systemMode = payload.current_mode;
      document.body.classList.remove(
        "system-mode-pos",
        "system-mode-mobile",
        "system-mode-tablet",
        "system-mode-desktop",
        "system-mode-admin_super",
        "system-mode-auto"
      );
      document.body.classList.add("system-mode-" + String(payload.current_mode).toLowerCase());
    }
    if (typeof payload.is_locked !== "undefined") {
      document.body.dataset.systemModeLocked = payload.is_locked ? "1" : "0";
    }
  }

  function forceReloadOnModeChange(event) {
    var bodyMode = document.body.dataset.systemMode || "";
    var nextMode = (((event || {}).payload || {}).current_mode || "").toUpperCase();
    if (!nextMode) return;
    applyModeData(event.payload);
    if (bodyMode.toUpperCase() !== nextMode) {
      window.location.reload();
    }
  }

  function connectModeSocket() {
    try {
      var socket = new WebSocket(getWsUrl("/ws/system-mode/"));

      socket.onmessage = function (raw) {
        var data = {};
        try {
          data = JSON.parse(raw.data || "{}");
        } catch (e) {
          return;
        }

        if (data.event_type === "system.mode.changed") {
          forceReloadOnModeChange(data);
        }
      };

      socket.onclose = function () {
        setTimeout(connectModeSocket, 3000);
      };
    } catch (e) {
      // Silent fallback; page still works without live mode stream.
    }
  }

  function init() {
    if (!document.body) return;

    // Desktop EXE mode does not run ASGI/channels; `/ws/system-mode/` will 404 and cause retry loops.
    // Avoid hammering the server (and SQLite sessions) in desktop mode.
    try {
      var mode = String(document.body.dataset.systemMode || "").toUpperCase();
      if (mode.indexOf("DESKTOP") !== -1) return;
    } catch (e) {}
    connectModeSocket();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
