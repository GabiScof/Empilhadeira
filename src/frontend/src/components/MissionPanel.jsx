import { useState } from "react";

const STATE_COLORS = {
  IDLE: "bg-slate-600",
  LOAD_MAP: "bg-blue-700",
  DRAW_TARGETS: "bg-blue-600",
  GO_TO_PICK: "bg-amber-700",
  AT_PICK: "bg-yellow-600 animate-pulse",
  GO_TO_PLACE: "bg-amber-700",
  AT_PLACE: "bg-yellow-600 animate-pulse",
  GO_HOME: "bg-green-700",
  DONE: "bg-green-600",
  FAULT: "bg-red-700",
};

export default function MissionPanel({ apiBase, telemetry, worldState }) {
  const [pickId, setPickId] = useState("");
  const [placeId, setPlaceId] = useState("");
  const [status, setStatus] = useState("");

  const mission = telemetry?.mission || worldState?.mission;
  const missionState = mission?.state || "IDLE";
  const availableTags = worldState?.world_model?.tags || worldState?.world?.tags || [];

  const startMission = async () => {
    try {
      const body = {};
      if (pickId) body.pick_id = pickId;
      if (placeId) body.place_id = placeId;
      const res = await fetch(`${apiBase}/mission/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      setStatus(data.ok ? "Missão iniciada" : data.error || "Erro");
    } catch {
      setStatus("Falha de conexão");
    }
    setTimeout(() => setStatus(""), 3000);
  };

  const continueMission = async () => {
    try {
      await fetch(`${apiBase}/mission/continue`, { method: "POST" });
    } catch {}
  };

  const resetMission = async () => {
    try {
      await fetch(`${apiBase}/mission/reset`, { method: "POST" });
    } catch {}
  };

  const colorClass = STATE_COLORS[missionState] || "bg-slate-600";

  return (
    <div className="rounded-lg bg-slate-800 p-4">
      <h2 className="font-semibold mb-2">Missão</h2>

      <div className={`rounded px-3 py-2 mb-3 text-center font-mono text-sm ${colorClass}`}>
        {missionState}
        {mission?.elapsed_s > 0 && (
          <span className="ml-2 text-xs opacity-70">
            ({mission.elapsed_s.toFixed(0)}s)
          </span>
        )}
      </div>

      {mission?.pick_position_id && (
        <div className="text-xs mb-1">
          Pick: <span className="font-mono text-amber-400">{mission.pick_position_id}</span>
          {" → "}
          Place: <span className="font-mono text-green-400">{mission.place_position_id}</span>
        </div>
      )}

      {mission?.fault_reason && (
        <div className="text-xs text-red-400 mb-2">Falha: {mission.fault_reason}</div>
      )}

      {(missionState === "AT_PICK" || missionState === "AT_PLACE") && (
        <button
          onClick={continueMission}
          className="w-full rounded bg-emerald-700 hover:bg-emerald-600 py-2 text-sm font-bold mb-2 animate-pulse"
          type="button"
        >
          Continuar (operador acionou a garra)
        </button>
      )}

      {missionState === "IDLE" && (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs">
              Pick
              <select
                value={pickId}
                onChange={(e) => setPickId(e.target.value)}
                className="w-full mt-1 px-2 py-1 rounded bg-slate-700 text-sm"
              >
                <option value="">Sortear</option>
                {availableTags.map((t) => (
                  <option key={t.position_id} value={t.position_id}>
                    {t.position_id}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs">
              Place
              <select
                value={placeId}
                onChange={(e) => setPlaceId(e.target.value)}
                className="w-full mt-1 px-2 py-1 rounded bg-slate-700 text-sm"
              >
                <option value="">Sortear</option>
                {availableTags.map((t) => (
                  <option key={t.position_id} value={t.position_id}>
                    {t.position_id}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <button
            onClick={startMission}
            className="w-full rounded bg-indigo-700 hover:bg-indigo-600 py-2 text-sm font-bold"
            type="button"
          >
            Iniciar Missão
          </button>
        </div>
      )}

      {missionState !== "IDLE" && (
        <button
          onClick={resetMission}
          className="w-full rounded bg-slate-700 hover:bg-slate-600 py-1.5 text-xs mt-2"
          type="button"
        >
          Resetar Missão
        </button>
      )}

      {status && (
        <p className="text-xs text-center mt-1 text-slate-400">{status}</p>
      )}
    </div>
  );
}
