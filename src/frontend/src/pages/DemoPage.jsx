import { useState, useEffect, useCallback } from "react";
import { useWebSocket } from "../ws/useWebSocket.js";
import Arena from "../components/Arena.jsx";
import ForkSideView from "../components/ForkSideView.jsx";
import PoseResetPanel from "../components/PoseResetPanel.jsx";
import FaultInjector from "../components/FaultInjector.jsx";
import TelemetryPanel from "../components/TelemetryPanel.jsx";
import ModeSelector from "../components/ModeSelector.jsx";
import Joystick from "../components/Joystick.jsx";
import ForkControl from "../components/ForkControl.jsx";
import SafetyAlert from "../components/SafetyAlert.jsx";
import DebugExport from "../components/DebugExport.jsx";
import MapSelector from "../components/MapSelector.jsx";
import MissionPanel from "../components/MissionPanel.jsx";

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
  const { telemetry, connected, sendCommand } = useWebSocket(WS_URL);
  const [worldState, setWorldState] = useState(null);
  const [mode, setMode] = useState("PARADO");
  const [garfo, setGarfo] = useState("parar");

  const fetchWorldState = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/sim/world-state`);
      if (res.ok) {
        setWorldState(await res.json());
      }
    } catch {}
  }, []);

  useEffect(() => {
    const interval = setInterval(fetchWorldState, 200);
    return () => clearInterval(interval);
  }, [fetchWorldState]);

  const send = useCallback(
    (overrides) => {
      sendCommand({
        modo: mode,
        joystick: { x: 0, y: 0 },
        garfo,
        ts_ms: Date.now(),
        ...overrides,
      });
    },
    [mode, garfo, sendCommand],
  );

  const handleMode = useCallback(
    (m) => {
      setMode(m);
      send({ modo: m });
    },
    [send],
  );

  const handleJoystick = useCallback(
    (pos) => {
      send({ joystick: pos });
    },
    [send],
  );

  const handleFork = useCallback(
    (cmd) => {
      setGarfo(cmd);
      send({ garfo: cmd });
    },
    [send],
  );

  const currentState = telemetry?.estado || mode;

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-4">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold">Empilhadeira — Demo + Controle</h1>
        <div className="flex items-center gap-3">
          {telemetry?.map_name && (
            <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-300">
              {telemetry.map_name}
            </span>
          )}
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
      </div>

      <SafetyAlert telemetry={telemetry} />

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Coluna 1: Controles do operador */}
        <div className="space-y-4">
          <ModeSelector
            currentMode={currentState}
            onModeChange={handleMode}
            disabled={!connected}
          />
          <Joystick
            onMove={handleJoystick}
            disabled={currentState !== "MANUAL" || !connected}
          />
          <ForkControl onForkCommand={handleFork} />
          <MissionPanel
            apiBase={API_BASE}
            telemetry={telemetry}
            worldState={worldState}
          />
        </div>

        {/* Colunas 2-4: Visualização */}
        <div className="lg:col-span-3 space-y-4">
          <Arena worldState={worldState} telemetry={telemetry} />
          <ForkSideView worldState={worldState} />
        </div>

        {/* Coluna 5: Telemetria + Ferramentas sim */}
        <div className="space-y-4">
          <TelemetryPanel telemetry={telemetry} connected={connected} worldState={worldState} />
          <MapSelector apiBase={API_BASE} onMapLoaded={fetchWorldState} />
          <PoseResetPanel apiBase={API_BASE} />
          <FaultInjector apiBase={API_BASE} />
          <DebugExport apiBase={API_BASE} telemetry={telemetry} />
        </div>
      </div>
    </div>
  );
}
