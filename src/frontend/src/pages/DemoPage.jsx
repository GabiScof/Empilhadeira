import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { useWebSocket } from "../ws/useWebSocket.js";
import Arena from "../components/Arena.jsx";
import ForkSideView from "../components/ForkSideView.jsx";
import PoseResetPanel from "../components/PoseResetPanel.jsx";
import FaultInjector from "../components/FaultInjector.jsx";
import TelemetryPanel from "../components/TelemetryPanel.jsx";

const WS_URL =
  (window.location.protocol === "https:" ? "wss://" : "ws://") +
  (window.location.hostname || "localhost") +
  ":8000/ws";

const API_BASE =
  window.location.protocol +
  "//" +
  (window.location.hostname || "localhost") +
  ":8000";

export default function DemoPage() {
  const { telemetry, connected } = useWebSocket(WS_URL);
  const [worldState, setWorldState] = useState(null);

  const fetchWorldState = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/sim/world-state`);
      if (res.ok) {
        setWorldState(await res.json());
      }
    } catch {
      // falha silenciosa
    }
  }, []);

  useEffect(() => {
    const interval = setInterval(fetchWorldState, 200);
    return () => clearInterval(interval);
  }, [fetchWorldState]);

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-4">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold">Empilhadeira — Demo</h1>
        <Link
          to="/"
          className="text-xs px-3 py-1 rounded bg-slate-700 hover:bg-slate-600"
        >
          Operador
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <Arena worldState={worldState} />
          <ForkSideView worldState={worldState} />
        </div>

        <div className="space-y-4">
          <TelemetryPanel telemetry={telemetry} connected={connected} />
          <PoseResetPanel apiBase={API_BASE} />
          <FaultInjector apiBase={API_BASE} />
        </div>
      </div>
    </div>
  );
}
