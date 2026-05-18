import { useEffect, useMemo, useState } from "react";
import type { Task, WsMessage } from "./types";

export type LiveLog = {
  id: string;
  level: string;
  message: string;
  task_id?: string;
  account_id?: number;
  service?: string;
};

function websocketBaseUrl(): string {
  const explicit = import.meta.env.VITE_WS_BASE_URL;
  if (explicit) return explicit.replace(/\/$/, "");

  const apiBase = import.meta.env.VITE_API_BASE_URL;
  if (apiBase) {
    const url = new URL(apiBase, window.location.origin);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    return url.origin;
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  if (window.location.port === "5173") return `${protocol}://${window.location.hostname}:8000`;
  return `${protocol}://${window.location.host}`;
}

export function usePrimeBbWebSocket() {
  const [connected, setConnected] = useState(false);
  const [logs, setLogs] = useState<LiveLog[]>([]);
  const [tasks, setTasks] = useState<Record<string, Task>>({});
  const [serviceProgress, setServiceProgress] = useState<Record<string, string>>({});

  useEffect(() => {
    let socket: WebSocket | null = null;
    let stopped = false;
    let connectTimer: number | undefined;
    let reconnectTimer: number | undefined;
    let pingTimer: number | undefined;

    const connect = () => {
      const activeSocket = new WebSocket(`${websocketBaseUrl()}/ws`);
      socket = activeSocket;

      activeSocket.onopen = () => {
        if (stopped || socket !== activeSocket) return;
        setConnected(true);
        activeSocket.send("ping");
        pingTimer = window.setInterval(() => activeSocket.readyState === WebSocket.OPEN && activeSocket.send("ping"), 30000);
      };

      activeSocket.onclose = () => {
        if (socket !== activeSocket) return;
        setConnected(false);
        if (pingTimer) window.clearInterval(pingTimer);
        if (!stopped) reconnectTimer = window.setTimeout(connect, 2000);
      };

      activeSocket.onerror = () => {
        if (socket === activeSocket) setConnected(false);
      };

      activeSocket.onmessage = (event) => {
        if (event.data === "pong") return;
        let message: WsMessage;
        try {
          message = JSON.parse(event.data);
        } catch {
          return;
        }
        if (message.type === "log") {
          setLogs((current) => [
            { id: `${Date.now()}-${Math.random()}`, ...message.data },
            ...current,
          ].slice(0, 100));
        }
        if (message.type === "task_progress") {
          setTasks((current) => ({ ...current, [message.data.id]: message.data }));
        }
        if (message.type === "service_progress") {
          const key = `${message.data.task_id}:${message.data.account_id}:${message.data.service}`;
          setServiceProgress((current) => ({ ...current, [key]: message.data.status }));
        }
      };
    };

    connectTimer = window.setTimeout(connect, 100);
    return () => {
      stopped = true;
      if (connectTimer) window.clearTimeout(connectTimer);
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      if (pingTimer) window.clearInterval(pingTimer);
      socket?.close();
    };
  }, []);

  return useMemo(() => ({ connected, logs, tasks, serviceProgress }), [connected, logs, tasks, serviceProgress]);
}
