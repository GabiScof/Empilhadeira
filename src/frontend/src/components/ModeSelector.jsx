// ModeSelector.jsx — Seletor de modo (MANUAL / AUTOMATICO / PARADO).
//
// Define o campo `modo` do Command (contrato 1). Sair de PARADO exige acao
// explicita do operador. [ref: Secao 6 e 7 da AGENTS.md]
//
// Fase de scaffolding: apenas placeholder visual; sem estado real.
export default function ModeSelector() {
  // TODO: estado do modo selecionado + envio via sendCommand.
  const modos = ["MANUAL", "AUTOMATICO", "PARADO"];
  return (
    <div className="rounded-lg bg-slate-800 p-4">
      <h2 className="font-semibold mb-2">Modo</h2>
      <div className="flex gap-2">
        {modos.map((m) => (
          <button key={m} className="flex-1 rounded bg-slate-700 py-2 text-sm" type="button">
            {m}
          </button>
        ))}
      </div>
    </div>
  );
}
