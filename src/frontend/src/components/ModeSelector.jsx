// ModeSelector.jsx — Seletor de modo (MANUAL / AUTOMATICO / PARADO).
//
// Emite Command (contrato 1) via onModeChange ao trocar de modo.
// O botao do modo ativo fica destacado (bg-blue-600).
// [ref: Secao 6 e 7 da AGENTS.md]

/** @param {{ mode: import('../types/contracts').Mode, onModeChange: (m: string) => void }} props */
export default function ModeSelector({ mode, onModeChange }) {
  const modos = ["MANUAL", "AUTOMATICO", "PARADO"];

  return (
    <div className="rounded-lg bg-slate-800 p-4">
      <h2 className="font-semibold mb-2">Modo</h2>
      <div className="flex gap-2">
        {modos.map((m) => (
          <button
            key={m}
            type="button"
            className={`flex-1 rounded py-2 text-sm font-medium transition-colors ${
              mode === m ? "bg-blue-600 text-white" : "bg-slate-700 text-slate-300 hover:bg-slate-600"
            }`}
            onClick={() => onModeChange(m)}
          >
            {m}
          </button>
        ))}
      </div>
    </div>
  );
}
