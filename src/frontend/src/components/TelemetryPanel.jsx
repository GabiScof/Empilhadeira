// TelemetryPanel.jsx — Painel de telemetria @20 Hz (contrato 2).
//
// Mostra velocidades das rodas, roll/pitch (IMU), distancia/alinhamento ao pallet
// (visao) e bateria. Usa Recharts para series temporais. [ref: Secao 6 da AGENTS.md]
//
// Fase de scaffolding: apenas placeholder visual; sem dados reais.
export default function TelemetryPanel() {
  // TODO: consumir telemetry do useWebSocket e renderizar valores + graficos (Recharts).
  return (
    <div className="rounded-lg bg-slate-800 p-4">
      <h2 className="font-semibold mb-2">Telemetria</h2>
      <p className="text-slate-400 text-sm">
        TODO: rodas (rad/s), IMU (roll/pitch), visão (z/x/pitch), bateria.
      </p>
    </div>
  );
}
