import { useEffect, useRef, useState } from "react";

export function useLiveStream(streamName) {
  const [messages, setMessages] = useState([]);
  const wsRef = useRef(null);

  useEffect(() => {
    let isMounted = true;
    const loc = window.location;
    const proto = loc.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${loc.host}/ws/realtime/${streamName}/`;

    function connect() {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ hello: streamName, at: new Date().toISOString() }));
      };

      ws.onmessage = (evt) => {
        if (!isMounted) return;
        try {
          const data = JSON.parse(evt.data);
          setMessages((prev) => [data, ...prev].slice(0, 50));
        } catch {
          /* ignore parse errors */
        }
      };

      ws.onclose = () => {
        if (!isMounted) return;
        setTimeout(connect, 2000);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();
    return () => {
      isMounted = false;
      if (wsRef.current) wsRef.current.close();
    };
  }, [streamName]);

  return messages;
}
