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

  const connect = useCallback(() => {
    if (!url || !mountedRef.current) return;

    // Já existe um socket vivo (aberto ou conectando)? Não abra outro — evita
    // sockets duplicados quando uma reconexão agendada coincide com um socket vivo.
    const existing = wsRef.current;
    if (
      existing &&
      (existing.readyState === WebSocket.OPEN ||
        existing.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    const ws = new WebSocket(url);
    wsRef.current = ws;

    // Os handlers só valem para o socket "atual" (wsRef.current === ws). Sockets
    // órfãos — criados e descartados pelo duplo-mount do StrictMode em dev, ou
    // substituídos por uma reconexão — são ignorados. Sem isso, o onclose de um
    // socket abortado agenda reconexões espúrias em cima do socket vivo, gerando
    // a tempestade de conexões (ws flapping → "Desconectado").
    ws.onopen = () => {
      if (wsRef.current !== ws) return;
      setConnected(true);
      backoffRef.current = RECONNECT_BASE_MS;
    };

    ws.onmessage = (event) => {
      if (wsRef.current !== ws) return;
      try {
        setTelemetry(JSON.parse(event.data));
      } catch {
        /* ignora frames malformados */
      }
    };

    ws.onclose = () => {
      if (wsRef.current !== ws) return; // socket órfão: ignora
      wsRef.current = null;
      setConnected(false);
      if (!mountedRef.current) return; // desmontado: não reconecta
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
      const ws = wsRef.current;
      wsRef.current = null;
      if (ws) {
        // Remove os handlers antes de fechar: o onclose deste socket não deve
        // agendar reconexão durante o unmount nem durante o cleanup do StrictMode.
        ws.onopen = ws.onmessage = ws.onclose = ws.onerror = null;
        ws.close();
      }
    };
  }, [connect]);

  const sendCommand = useCallback((cmd) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(cmd));
    }
  }, []);

  return { telemetry, connected, sendCommand };
}
