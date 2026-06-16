// TelemetryPanel.jsx — Painel de telemetria @20 Hz (contrato 2).
//
// Renderiza estado, rodas, IMU, visao e bateria recebidos do Pi via WebSocket.
// O grafico de rodas (Recharts LineChart) e atualizado a cada frame de telemetria;
// isAnimationActive=false e obrigatorio para nao acumular lag a 20 Hz.
// [ref: Secao 6 da AGENTS.md]

import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  YAxis,
} from "recharts";

const MAX_HISTORY = 40; // ~2 s a 20 Hz

/**
 * @param {{
 *   telemetry: import('../types/contracts').Telemetry | null,
 *   connected: boolean
 * }} props
 */
export default function TelemetryPanel({ telemetry, connected }) {
  const [history, setHistory] = useState([]);

  useEffect(() => {
    if (!telemetry?.rodas) return;
    setHistory((prev) => [
      ...prev.slice(-(MAX_HISTORY - 1)),
      { i: prev.length, esq: telemetry.rodas.esq, dir: telemetry.rodas.dir },
    ]);
  }, [telemetry]);

  if (!connected || !telemetry) {
    return (
      <div className="rounded-lg bg-slate-800 p-4">
        <h2 className="font-semibold mb-2">Telemetria</h2>
        <p className="text-slate-400 text-sm">
          {connected ? "Aguardando dados…" : "○ Desconectado do Pi"}
        </p>
      </div>
    );
  }

  const { estado, rodas, imu, visao, bateria } = telemetry;
  const fmt = (v, d = 3) => (v == null ? "—" : Number(v).toFixed(d));

  return (
    <div className="rounded-lg bg-slate-800 p-4 flex flex-col gap-3">
      <h2 className="font-semibold">Telemetria</h2>

      <div className="text-sm">
        Estado:{" "}
        <strong
          className={
            estado === "PARADO"
              ? "text-red-400"
              : estado === "MANUAL"
                ? "text-green-400"
                : "text-yellow-300"
          }
        >
          {estado}
        </strong>
      </div>

      <div className="grid grid-cols-2 gap-2 text-sm">
        <div className="rounded bg-slate-700 p-2">
          <div className="text-slate-400 text-xs mb-1">Rodas (rad/s)</div>
          <div>ESQ: {fmt(rodas.esq)}</div>
          <div>DIR: {fmt(rodas.dir)}</div>
        </div>

        <div className="rounded bg-slate-700 p-2">
          <div className="text-slate-400 text-xs mb-1">IMU (°)</div>
          <div>Roll: {fmt(imu.roll, 1)}</div>
          <div>Pitch: {fmt(imu.pitch, 1)}</div>
        </div>

        <div className="rounded bg-slate-700 p-2">
          <div className="text-slate-400 text-xs mb-1">Visão</div>
          {visao.detectado ? (
            <>
              <div>Tag {visao.id}</div>
              <div>Z: {fmt(visao.z_cm, 1)} cm</div>
              <div>X: {fmt(visao.x_cm, 1)} cm</div>
              <div>P: {fmt(visao.pitch_deg, 1)}°</div>
            </>
          ) : (
            <div className="text-slate-500">Sem tag</div>
          )}
        </div>

        <div className="rounded bg-slate-700 p-2">
          <div className="text-slate-400 text-xs mb-1">Bateria</div>
          <div>Cel: {fmt(bateria.cel, 2)} V</div>
          <div>I: {fmt(bateria.i_a, 2)} A</div>
          <div>T: {fmt(bateria.temp_c, 1)} °C</div>
        </div>
      </div>

      <div>
        <div className="text-xs text-slate-400 mb-1">Velocidade das Rodas (rad/s)</div>
        <div className="h-28">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={history}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <YAxis domain={[-3.5, 3.5]} tick={{ fontSize: 9, fill: "#94a3b8" }} width={28} />
              <Tooltip
                contentStyle={{ background: "#1e293b", border: "none", fontSize: 10 }}
                formatter={(v) => Number(v).toFixed(3)}
                labelFormatter={() => ""}
              />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              <Line
                type="monotone"
                dataKey="esq"
                stroke="#60a5fa"
                dot={false}
                strokeWidth={1.5}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="dir"
                stroke="#f472b6"
                dot={false}
                strokeWidth={1.5}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
