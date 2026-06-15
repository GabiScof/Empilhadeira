import { useState, useCallback } from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { useWebSocket } from "./ws/useWebSocket.js";
import ModeSelector from "./components/ModeSelector.jsx";
import Joystick from "./components/Joystick.jsx";
import ForkControl from "./components/ForkControl.jsx";
import TelemetryPanel from "./components/TelemetryPanel.jsx";
import DemoPage from "./pages/DemoPage.jsx";

const WS_URL =
  (window.location.protocol === "https:" ? "wss://" : "ws://") +
  (window.location.hostname || "localhost") +
  ":8000/ws";

function OperatorPage() {
  const { telemetry, connected, sendCommand } = useWebSocket(WS_URL);
  const [mode, setMode] = useState("PARADO");
  const [garfo, setGarfo] = useState("parar");

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
    <div className="min-h-screen bg-slate-900 text-slate-100 p-4 flex flex-col gap-4 max-w-lg mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Empilhadeira</h1>
        <Link
          to="/demo"
          className="text-xs px-3 py-1 rounded bg-slate-700 hover:bg-slate-600"
        >
          Demo
        </Link>
      </div>
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
      <TelemetryPanel telemetry={telemetry} connected={connected} />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<OperatorPage />} />
        <Route path="/demo" element={<DemoPage />} />
      </Routes>
    </BrowserRouter>
  );
}
