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

          {/* Debug ao vivo: o que o robô está fazendo agora, com números */}
          <div className="mt-2 font-mono text-[11px] text-slate-300 space-y-0.5">
            {dockState === "SEEKING" && (
              <div>
                detecções {dock?.detection_streak ?? 0}/{dock?.min_detections ?? 3}
                {telemetry?.visao?.detectado
                  ? ` · vendo tag ${telemetry.visao.id}: z ${telemetry.visao.z_cm?.toFixed(0)}cm x ${telemetry.visao.x_cm > 0 ? "+" : ""}${telemetry.visao.x_cm?.toFixed(0)}cm`
                  : " · nenhuma tag na imagem"}
              </div>
            )}
            {dockState !== "SEEKING" && (
              <>
                {dock?.planned_from && (
                  <div>
                    plano feito com: z {dock.planned_from.z_cm}cm · x{" "}
                    {dock.planned_from.x_cm > 0 ? "+" : ""}
                    {dock.planned_from.x_cm}cm
                  </div>
                )}
                {dock?.goal && (
                  <div>
                    alvo: ({dock.goal[0]?.toFixed(2)}, {dock.goal[1]?.toFixed(2)})m ·{" "}
                    {((dock.goal[2] * 180) / Math.PI).toFixed(0)}°
                  </div>
                )}
                {dockState === "DOCKING" && (
                  <div>
                    passo {Math.min((dock?.seg_index ?? 0) + 1, dock?.seg_total ?? 0)}/
                    {dock?.seg_total ?? 0}
                    {dock?.seg_type
                      ? ` (${dock.seg_type === "turn" ? "GIRO" : "AVANÇO"})`
                      : ""}
                    {" · "}t {dock?.seg_elapsed_s?.toFixed(1)}s
                    {" · "}rodas {dock?.w_esq?.toFixed(1)}/{dock?.w_dir?.toFixed(1)}{" "}
                    rad/s
                  </div>
                )}
                {dockState === "FAULT" && (
                  <div className="text-red-400">
                    executor {dock?.executor_state} — timeout no passo{" "}
                    {(dock?.seg_index ?? 0) + 1} ({dock?.seg_type}): a odometria não
                    fechou o segmento
                  </div>
                )}
              </>
            )}
            {telemetry?.ekf && (
              <div className="opacity-60">
                pose: ({telemetry.ekf.x_m?.toFixed(2)}, {telemetry.ekf.y_m?.toFixed(2)}
                )m · {telemetry.ekf.theta_deg?.toFixed(0)}°
              </div>
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
