// App.jsx — Shell da interface de operacao (celular).
//
// Monta os quatro componentes principais: seletor de modo, joystick virtual,
// controle do garfo e painel de telemetria. A ligacao WebSocket com o Pi vive em
// ws/useWebSocket.js. [ref: Secao 5 da AGENTS.md]
//
// Fase de scaffolding: sem logica (sem conexao real, sem estado funcional).
import ModeSelector from "./components/ModeSelector.jsx";
import Joystick from "./components/Joystick.jsx";
import ForkControl from "./components/ForkControl.jsx";
import TelemetryPanel from "./components/TelemetryPanel.jsx";

export default function App() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-4 flex flex-col gap-4">
      <h1 className="text-xl font-bold">Empilhadeira — Controle</h1>
      <ModeSelector />
      <div className="flex flex-col gap-4">
        <Joystick />
        <ForkControl />
        <TelemetryPanel />
      </div>
    </div>
  );
}
