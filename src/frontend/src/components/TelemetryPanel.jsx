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

const PHASE_STYLE = {
  APPROACH: { bg: "bg-blue-900/60", border: "border-blue-500/40", text: "text-blue-300", label: "Aproximando" },
  FACE:     { bg: "bg-amber-900/60", border: "border-amber-500/40", text: "text-amber-300", label: "Corrigindo heading" },
  RETREAT:  { bg: "bg-purple-900/60", border: "border-purple-500/40", text: "text-purple-300", label: "Recuando p/ realinhar" },
};

function NavPhaseBadge({ phase }) {
  const s = PHASE_STYLE[phase] || { bg: "bg-slate-700", border: "border-slate-500/40", text: "text-slate-300", label: phase };
  return (
    <div className={`px-3 py-1.5 rounded-md ${s.bg} border ${s.border} flex items-center justify-between`}>
      <span className={`text-xs font-medium ${s.text}`}>Nav: {s.label}</span>
      <span className="text-xs text-slate-500 font-mono">{phase}</span>
    </div>
  );
}

function PidBar({ label, setpoint, error, integral, output }) {
  const maxVal = 12.25;
  const pct = Math.min(100, Math.abs(output / maxVal) * 100);
  const dir = output >= 0 ? "right" : "left";
  return (
    <div className="space-y-0.5">
      <div className="flex justify-between text-xs">
        <span className="text-slate-400">{label}</span>
        <span className="font-mono text-slate-300">{output?.toFixed(2)} rad/s</span>
      </div>
      <div className="w-full bg-slate-700 rounded-full h-1.5 relative">
        <div
          className={`absolute top-0 h-1.5 rounded-full ${output >= 0 ? "bg-emerald-500" : "bg-rose-500"}`}
          style={{
            width: `${pct / 2}%`,
            left: dir === "right" ? "50%" : undefined,
            right: dir === "left" ? "50%" : undefined,
          }}
        />
        <div className="absolute top-0 left-1/2 w-px h-1.5 bg-slate-500" />
      </div>
      <div className="flex justify-between text-[10px] text-slate-500">
        <span>err={error?.toFixed(3)}</span>
        <span>I={integral?.toFixed(2)}</span>
        <span>sp={setpoint?.toFixed(2)}</span>
      </div>
    </div>
  );
}

export default function TelemetryPanel({ telemetry, connected, worldState }) {
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

      {telemetry?.estado === "AUTOMATICO" && telemetry?.nav_phase && (
        <NavPhaseBadge phase={telemetry.nav_phase} />
      )}

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

      {telemetry?.detected_tags?.length > 0 && (
        <div>
          <p className="text-xs text-slate-400 mb-1">
            Tags à vista ({telemetry.detected_tags.length})
          </p>
          <div className="flex flex-col gap-0.5 font-mono text-xs">
            {telemetry.detected_tags.map((t) => (
              <div
                key={`${t.tag_id}-${t.position_id ?? ""}`}
                className={t.in_map ? "text-slate-200" : "text-amber-300"}
              >
                ID {t.tag_id}
                {t.position_id ? ` (${t.position_id})` : ""}
                {t.z_cm != null && ` · z ${t.z_cm.toFixed(0)}cm`}
                {t.x_cm != null &&
                  ` · x ${t.x_cm > 0 ? "+" : ""}${t.x_cm.toFixed(0)}cm`}
                {` · (${t.x_m.toFixed(2)}, ${t.y_m.toFixed(2)})m`}
                {t.in_map ? "" : " · fora do mapa"}
              </div>
            ))}
          </div>
        </div>
      )}

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

      {/* Encoders + Kalman */}
      <div className="border-t border-slate-700 pt-3 space-y-1">
        <p className="text-xs font-medium text-cyan-400 mb-1">Sensores</p>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          <Stat label="Enc esq" value={telemetry?.rodas?.esq} unit="rad/s" />
          <Stat label="Enc dir" value={telemetry?.rodas?.dir} unit="rad/s" />
          <Stat label="Kalman roll" value={telemetry?.imu?.roll} unit="°" />
          <Stat label="Kalman pitch" value={telemetry?.imu?.pitch} unit="°" />
        </div>
      </div>

      {/* EKF */}
      {telemetry?.ekf && (
        <div className="border-t border-slate-700 pt-3 space-y-1">
          <p className="text-xs font-medium text-amber-400 mb-1">EKF 2D [x, y, θ]</p>
          <Stat label="x" value={telemetry.ekf.x_m} unit="m" />
          <Stat label="y" value={telemetry.ekf.y_m} unit="m" />
          <Stat label="θ" value={telemetry.ekf.theta_deg} unit="°" />
          <Stat label="P trace" value={telemetry.ekf.covariance_trace} />
          <Stat label="Correção" value={telemetry.ekf.last_correction} />
          <Stat label="Correções" value={telemetry.ekf.correction_count} />
          {telemetry.ekf.ellipse_semi_major_m != null && (
            <Stat label="Ellipse a" value={telemetry.ekf.ellipse_semi_major_m * 1000} unit="mm" />
          )}
        </div>
      )}

      {/* PID (from sim world-state) */}
      {worldState?.pid && (
        <div className="border-t border-slate-700 pt-3 space-y-2">
          <p className="text-xs font-medium text-rose-400 mb-1">PID (firmware)</p>
          <PidBar
            label="Esquerda"
            setpoint={worldState.pid.esq.setpoint}
            error={worldState.pid.esq.error}
            integral={worldState.pid.esq.integral}
            output={worldState.pid.esq.output}
          />
          <PidBar
            label="Direita"
            setpoint={worldState.pid.dir.setpoint}
            error={worldState.pid.dir.error}
            integral={worldState.pid.dir.integral}
            output={worldState.pid.dir.output}
          />
        </div>
      )}

      {telemetry?.mission && (
        <div className="border-t border-slate-700 pt-3">
          <p className="text-xs font-medium text-indigo-400 mb-1.5">Missão</p>
          <div className="px-3 py-1.5 rounded-md bg-indigo-900/60 border border-indigo-500/40 flex items-center justify-between">
            <span className="text-xs font-mono text-indigo-300">{telemetry.mission.state}</span>
            {telemetry.mission.elapsed_s > 0 && (
              <span className="text-xs text-slate-500">{telemetry.mission.elapsed_s.toFixed(0)}s</span>
            )}
          </div>
          {telemetry.mission.pick_position_id && (
            <p className="text-xs text-slate-400 mt-1">
              {telemetry.mission.pick_position_id} → {telemetry.mission.place_position_id}
            </p>
          )}
          {telemetry.mission.fault_reason && (
            <p className="text-xs text-red-400 mt-1">{telemetry.mission.fault_reason}</p>
          )}
        </div>
      )}

      {telemetry?.navigation && (
        <div className="border-t border-slate-700 pt-3">
          <p className="text-xs font-medium text-blue-400 mb-1.5">Navegação</p>
          <div className="flex justify-between text-xs text-slate-400 mb-1">
            <span className="font-mono">{telemetry.navigation.executor_state}</span>
            <span>
              Seg {telemetry.navigation.segment_index + 1}/{telemetry.navigation.total_segments}
            </span>
          </div>
          <div className="w-full bg-slate-700 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all"
              style={{ width: `${Math.round(telemetry.navigation.progress * 100)}%` }}
            />
          </div>
          {telemetry.navigation.current_segment_type && (
            <p className="text-xs text-slate-500 mt-1 font-mono">
              {telemetry.navigation.current_segment_type}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
