// App.jsx — Shell da interface de operacao (celular).
//
// Gerencia o estado de comando (modo, posicao do joystick, garfo) e os distribui
// aos componentes filhos via props. Um heartbeat a 100 ms mantém o watchdog do Pi
// vivo enquanto conectado — sem ele, o Pi força PARADO apos COMMAND_TIMEOUT_MS.
//
// [ref: Secao 5 e 7 da AGENTS.md]

import { useState, useEffect, useRef, useCallback } from "react";

import ForkControl from "./components/ForkControl.jsx";
import Joystick from "./components/Joystick.jsx";
import ModeSelector from "./components/ModeSelector.jsx";
import TelemetryPanel from "./components/TelemetryPanel.jsx";
import { useWebSocket } from "./ws/useWebSocket.js";

// URL do WebSocket do Pi: definir VITE_PI_WS_URL no arquivo frontend/.env
// (copiar de src/.env.example e ajustar o IP do Pi na rede da PUC).
const PI_WS_URL = import.meta.env.VITE_PI_WS_URL ?? "ws://localhost:8000/ws";

// Intervalo do heartbeat em ms. Deve ser << COMMAND_TIMEOUT_MS do Pi (400 ms).
const HEARTBEAT_MS = 100;

export default function App() {
  const { telemetry, connected, sendCommand } = useWebSocket(PI_WS_URL);

  // Estado de UI (modo e garfo provocam re-render p/ highlight de botão)
  const [mode, setMode] = useState("PARADO");
  const [garfo, setGarfo] = useState("parar");

  // Ref com snapshot do comando atual: evita closures obsoletas no heartbeat
  const cmdRef = useRef({ modo: "PARADO", joystick: { x: 0, y: 0 }, garfo: "parar" });

  // Emite um Command imediatamente, mesclando patch sobre o estado atual
  const emit = useCallback(
    (patch) => {
      Object.assign(cmdRef.current, patch);
      sendCommand({ ...cmdRef.current, ts_ms: Date.now() });
    },
    [sendCommand],
  );

  // Heartbeat: reenvia o comando corrente para manter o watchdog do Pi ativo
  useEffect(() => {
    if (!connected) return;
    const id = setInterval(() => {
      sendCommand({ ...cmdRef.current, ts_ms: Date.now() });
    }, HEARTBEAT_MS);
    return () => clearInterval(id);
  }, [connected, sendCommand]);

  const handleModeChange = useCallback(
    (newMode) => {
      setMode(newMode);
      emit({ modo: newMode });
    },
    [emit],
  );

  const handleJoystickChange = useCallback(
    (pos) => {
      emit({ joystick: pos });
    },
    [emit],
  );

  const handleGarfoChange = useCallback(
    (cmd) => {
      setGarfo(cmd);
      emit({ garfo: cmd });
    },
    [emit],
  );

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-4 flex flex-col gap-4">
      <h1 className="text-xl font-bold flex items-center gap-3">
        Empilhadeira — Controle
        <span className={`text-sm font-normal ${connected ? "text-green-400" : "text-red-400"}`}>
          {connected ? "● Conectado" : "○ Desconectado"}
        </span>
      </h1>
      <ModeSelector mode={mode} onModeChange={handleModeChange} />
      <Joystick onJoystickChange={handleJoystickChange} mode={mode} />
      <ForkControl garfo={garfo} onGarfoChange={handleGarfoChange} />
      <TelemetryPanel telemetry={telemetry} connected={connected} />
    </div>
  );
}
