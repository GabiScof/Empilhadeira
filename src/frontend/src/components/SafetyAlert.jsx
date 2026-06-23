import { useState, useEffect, useRef } from "react";

const REASON_LABELS = {
  tag_loss: "Tag perdida por tempo prolongado",
  command_watchdog: "Timeout de comando do operador",
  ws_disconnect: "Conexão WebSocket perdida",
  force_stop: "Parada forçada pelo sistema",
};

const NAV_PHASE_LABELS = {
  APPROACH: "Nav: Aproximando da tag",
  FACE: "Nav: Corrigindo heading (girando no lugar)",
  RETREAT: "Nav: Recuando para realinhar",
};

const EVENT_COLORS = {
  safety: "bg-red-900/40 text-red-300",
  nav: "bg-blue-900/40 text-blue-300",
};

export default function SafetyAlert({ telemetry }) {
  const [events, setEvents] = useState([]);
  const prevState = useRef(null);
  const prevReason = useRef(null);
  const prevPhase = useRef(null);

  useEffect(() => {
    if (!telemetry) return;

    const estado = telemetry.estado;
    const reason = telemetry.parado_reason;
    const phase = telemetry.nav_phase;

    const transitioned =
      estado === "PARADO" &&
      prevState.current !== null &&
      prevState.current !== "PARADO";

    const newReason =
      estado === "PARADO" &&
      reason &&
      reason !== prevReason.current;

    if (transitioned || newReason) {
      const label = reason
        ? REASON_LABELS[reason] || reason
        : "Transição para PARADO";

      setEvents((prev) => [
        { id: Date.now(), type: "safety", label, ts: new Date().toLocaleTimeString() },
        ...prev.slice(0, 19),
      ]);
    }

    if (
      estado === "AUTOMATICO" &&
      phase &&
      phase !== prevPhase.current
    ) {
      const label = NAV_PHASE_LABELS[phase] || `Nav: ${phase}`;
      setEvents((prev) => [
        { id: Date.now(), type: "nav", label, ts: new Date().toLocaleTimeString() },
        ...prev.slice(0, 19),
      ]);
    }

    prevState.current = estado;
    prevReason.current = reason;
    prevPhase.current = phase;
  }, [telemetry]);

  const activeReason = telemetry?.parado_reason;
  const activeLabel = activeReason
    ? REASON_LABELS[activeReason] || activeReason
    : null;

  return (
    <>
      {activeLabel && (
        <div className="mb-4 px-4 py-3 rounded-lg bg-red-900/60 border border-red-500/40 flex items-center gap-3">
          <span className="text-red-400 text-lg">!</span>
          <div>
            <p className="font-semibold text-red-200">Parada de segurança</p>
            <p className="text-sm text-red-300">{activeLabel}</p>
            <p className="text-xs text-red-400 mt-1">
              Selecione MANUAL ou AUTOMATICO para retomar.
            </p>
          </div>
        </div>
      )}

      {events.length > 0 && (
        <div className="mb-4 rounded-lg bg-slate-800/60 border border-slate-700/50 p-3">
          <p className="text-xs font-medium text-slate-400 mb-2">
            Histórico de eventos ({events.length})
          </p>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {events.map((ev) => (
              <div
                key={ev.id}
                className={`text-xs px-3 py-1.5 rounded flex justify-between ${EVENT_COLORS[ev.type] || "bg-slate-700 text-slate-300"}`}
              >
                <span>{ev.label}</span>
                <span className="text-slate-500 ml-2 shrink-0">{ev.ts}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
