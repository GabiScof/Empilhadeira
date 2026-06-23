// useWebSocket.js — Hook de conexao WebSocket com o Pi.
//
// Conecta a ws://<IP_DO_PI>:<porta>/ws, recebe Telemetry (contrato 2) @20 Hz
// e expoe sendCommand para emitir Command (contrato 1).
// Reconecta automaticamente com backoff exponencial (500 ms → 10 s) em qualquer queda.
//
// [ref: Secao 6 da AGENTS.md] · tipos em ../types/contracts.ts

import { useState, useEffect, useRef, useCallback } from "react";

const RECONNECT_BASE_MS = 500;
const RECONNECT_MAX_MS = 10_000;

/**
 * @param {string} url URL do WebSocket do Pi (ex.: ws://192.168.0.10:8000/ws).
 * @returns {{ telemetry: import('../types/contracts').Telemetry|null, connected: boolean, sendCommand: (cmd: import('../types/contracts').Command) => void }}
 */
export function useWebSocket(url) {
  const [telemetry, setTelemetry] = useState(null);
  const [connected, setConnected] = useState(false);

  const wsRef = useRef(null);
  const backoffRef = useRef(RECONNECT_BASE_MS);
  const timerRef = useRef(null);
  const mountedRef = useRef(true);

  // connect é estável enquanto url não muda
  const connect = useCallback(() => {
    if (!url || !mountedRef.current) return;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) {
        ws.close();
        return;
      }
      setConnected(true);
      backoffRef.current = RECONNECT_BASE_MS;
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;
      try {
        setTelemetry(JSON.parse(event.data));
      } catch {
        /* ignora frames malformados */
      }
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setConnected(false);
      wsRef.current = null;
      const delay = backoffRef.current;
      backoffRef.current = Math.min(delay * 2, RECONNECT_MAX_MS);
      timerRef.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      // onerror sempre é seguido de onclose; fechar explicitamente aciona o backoff.
      ws.close();
    };
  }, [url]);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      clearTimeout(timerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const sendCommand = useCallback((cmd) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(cmd));
    }
  }, []);

  return { telemetry, connected, sendCommand };
}
