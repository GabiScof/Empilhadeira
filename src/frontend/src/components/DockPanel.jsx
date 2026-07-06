import { useState } from "react";

// Painel do "dock-to-tag": liga/desliga a aproximação por segmentos a UMA tag.
// Fluxo do operador: ligar aqui → selecionar AUTOMATICO → mostrar uma tag.
// O robô planeja passinhos (avança / gira 90°) e para em frente à tag.

const STATE_LABEL = {
  SEEKING: "Procurando tag…",
  DOCKING: "Aproximando",
  DONE: "Estacionado",
  FAULT: "Falha",
};

const STATE_COLOR = {
  SEEKING: "bg-blue-700",
  DOCKING: "bg-amber-600 animate-pulse",
  DONE: "bg-green-600",
  FAULT: "bg-red-700",
};

export default function DockPanel({ apiBase, telemetry }) {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  const dock = telemetry?.dock;
  const enabled = !!dock?.enabled;
  const dockState = dock?.state || "SEEKING";
  const estado = telemetry?.estado;

  const call = async (path) => {
    setBusy(true);
    try {
      const res = await fetch(`${apiBase}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      const data = await res.json();
      setStatus(data.ok ? "" : data.error || "Erro");
    } catch {
      setStatus("Falha de conexão");
    }
    setBusy(false);
    setTimeout(() => setStatus(""), 3000);
  };

  return (
    <div className="rounded-lg bg-slate-800 p-4">
      <h2 className="font-semibold mb-2">Aproximar de uma tag</h2>

      <button
        type="button"
        disabled={busy}
        onClick={() => call(enabled ? "/dock/disable" : "/dock/enable")}
        className={`w-full rounded py-2 text-sm font-bold transition-colors ${
          enabled
            ? "bg-emerald-600 hover:bg-emerald-500 ring-2 ring-white/30"
            : "bg-slate-700 hover:bg-slate-600"
        }`}
      >
        {enabled ? "✓ Ligado — desligar" : "Ligar aproximação por tag"}
      </button>

      {enabled && (
        <>
          <div
            className={`rounded px-3 py-1.5 mt-2 text-center font-mono text-xs ${
              STATE_COLOR[dockState] || "bg-slate-600"
            }`}
          >
            {STATE_LABEL[dockState] || dockState}
            {dock?.segments > 0 && (
              <span className="ml-2 opacity-70">{dock.segments} passos</span>
            )}
          </div>

          {estado !== "AUTOMATICO" && (
            <p className="text-xs text-amber-400 mt-2">
              Agora selecione <b>AUTOMATICO</b> e mostre uma tag ao robô.
            </p>
          )}

          {dock?.mode === "tag_normal" && (
            <p className="text-[11px] text-slate-400 mt-1">
              Modo "quadrar com a face" — valide a convenção de yaw antes de confiar.
            </p>
          )}
        </>
      )}

      {status && <p className="text-xs text-center mt-1 text-red-400">{status}</p>}
    </div>
  );
}
