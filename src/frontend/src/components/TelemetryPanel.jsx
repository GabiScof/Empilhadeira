import { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";

const MAX_HISTORY = 100;

function Stat({ label, value, unit }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-slate-400">{label}</span>
      <span className="font-mono">
        {value != null ? `${typeof value === "number" ? value.toFixed(2) : value} ${unit || ""}` : "—"}
      </span>
    </div>
  );
}

export default function TelemetryPanel({ telemetry, connected }) {
  const [wheelHistory, setWheelHistory] = useState([]);
  const [pitchHistory, setPitchHistory] = useState([]);

  useEffect(() => {
    if (!telemetry) return;

    const now = Date.now();

    setWheelHistory((prev) => {
      const next = [
        ...prev,
        {
          t: now,
          esq: telemetry.rodas?.esq ?? 0,
          dir: telemetry.rodas?.dir ?? 0,
        },
      ];
      return next.slice(-MAX_HISTORY);
    });

    setPitchHistory((prev) => {
      const next = [
        ...prev,
        {
          t: now,
          pitch: telemetry.imu?.pitch ?? 0,
        },
      ];
      return next.slice(-MAX_HISTORY);
    });
  }, [telemetry]);

  return (
    <div className="rounded-lg bg-slate-800 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Telemetria</h2>
        <span
          className={`text-xs px-2 py-0.5 rounded-full ${
            connected
              ? "bg-green-900 text-green-300"
              : "bg-red-900 text-red-300"
          }`}
        >
          {connected ? "Conectado" : "Desconectado"}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        <Stat label="Estado" value={telemetry?.estado} />
        <Stat label="ω esq" value={telemetry?.rodas?.esq} unit="rad/s" />
        <Stat label="ω dir" value={telemetry?.rodas?.dir} unit="rad/s" />
        <Stat label="Roll" value={telemetry?.imu?.roll} unit="°" />
        <Stat label="Pitch" value={telemetry?.imu?.pitch} unit="°" />
        <Stat label="Tag" value={telemetry?.visao?.detectado ? `ID ${telemetry.visao.id}` : "—"} />
        <Stat label="Z" value={telemetry?.visao?.z_cm} unit="cm" />
        <Stat label="X" value={telemetry?.visao?.x_cm} unit="cm" />
        <Stat
          label="Pitch tag"
          value={telemetry?.visao?.pitch_deg}
          unit="°"
        />
      </div>

      {wheelHistory.length > 2 && (
        <div>
          <p className="text-xs text-slate-400 mb-1">Velocidade das rodas</p>
          <ResponsiveContainer width="100%" height={100}>
            <LineChart data={wheelHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="t" hide />
              <YAxis width={35} tick={{ fontSize: 10 }} stroke="#64748b" />
              <Line
                type="monotone"
                dataKey="esq"
                stroke="#3b82f6"
                dot={false}
                strokeWidth={1.5}
              />
              <Line
                type="monotone"
                dataKey="dir"
                stroke="#f59e0b"
                dot={false}
                strokeWidth={1.5}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {pitchHistory.length > 2 && (
        <div>
          <p className="text-xs text-slate-400 mb-1">Pitch (filtrado)</p>
          <ResponsiveContainer width="100%" height={80}>
            <LineChart data={pitchHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="t" hide />
              <YAxis width={35} tick={{ fontSize: 10 }} stroke="#64748b" />
              <Line
                type="monotone"
                dataKey="pitch"
                stroke="#10b981"
                dot={false}
                strokeWidth={1.5}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
