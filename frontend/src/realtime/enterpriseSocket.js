export function createEnterpriseSocket({ onMessage, onStatus } = {}) {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const apiBase = (import.meta.env.VITE_FASTAPI_URL || "http://127.0.0.1:8081").replace(/^http/, protocol).replace(/\/$/, "");
  const url = `${apiBase}/ws/platform/core/events/`;
  let socket = null;
  let reconnectTimer = null;

  function connect() {
    socket = new WebSocket(url);
    onStatus?.("connecting");
    socket.onopen = () => onStatus?.("online");
    socket.onmessage = (event) => {
      try {
        onMessage?.(JSON.parse(event.data));
      } catch {
        onMessage?.({ type: "raw", payload: event.data });
      }
    };
    socket.onclose = () => {
      onStatus?.("offline");
      reconnectTimer = window.setTimeout(connect, 3000);
    };
    socket.onerror = () => onStatus?.("degraded");
  }

  connect();

  return {
    close() {
      window.clearTimeout(reconnectTimer);
      socket?.close();
    },
  };
}
