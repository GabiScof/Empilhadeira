// endpoints.js — ÚNICA fonte dos endereços do backend (WS e REST).
//
// Regra: a API REST mora no MESMO host do WebSocket. Quando VITE_PI_WS_URL
// está definido (modo DEV: página servida pelo Mac, backend no Pi), a API é
// derivada DELE — antes, cada página montava `hostname-da-página:8000`, que
// no DEV apontava para o Mac (sem backend) e deixava mapa/dock/missão mudos
// enquanto a telemetria (WS, que já usava o env) funcionava.
// Sem o env (modo OPERAÇÃO: página servida pelo próprio Pi na :8000), cai no
// mesmo-host, que é o comportamento correto ali.

const WS_ENV = import.meta.env.VITE_PI_WS_URL;

export const WS_URL =
  WS_ENV ||
  (window.location.protocol === "https:" ? "wss://" : "ws://") +
    (window.location.hostname || "localhost") +
    ":8000/ws";

export const API_BASE = WS_ENV
  ? WS_ENV.replace(/^ws/, "http").replace(/\/ws\/?$/, "")
  : window.location.protocol +
    "//" +
    (window.location.hostname || "localhost") +
    ":8000";
