// ForkControl.jsx — Controle do garfo (canal independente, sempre manual).
//
// onPointerDown -> "subir" / "descer"; onPointerUp/Leave -> "parar".
// O botao do comando ativo fica destacado (bg-yellow-500).
// Vale nos dois modos de operacao; o Pi nao filtra pelo modo. [ref: Secao 1 e 7]

/**
 * @param {{
 *   garfo: import('../types/contracts').ForkCommand,
 *   onGarfoChange: (cmd: import('../types/contracts').ForkCommand) => void
 * }} props
 */
export default function ForkControl({ garfo, onGarfoChange }) {
  const cmds = [
    { cmd: "subir", label: "↑ Subir" },
    { cmd: "descer", label: "↓ Descer" },
  ];

  return (
    <div className="rounded-lg bg-slate-800 p-4">
      <h2 className="font-semibold mb-2">Garfo</h2>
      <div className="flex gap-3">
        {cmds.map(({ cmd, label }) => (
          <button
            key={cmd}
            type="button"
            className={`flex-1 rounded py-4 text-sm font-medium select-none transition-colors ${
              garfo === cmd
                ? "bg-yellow-500 text-black"
                : "bg-slate-700 text-slate-300 hover:bg-slate-600"
            }`}
            onPointerDown={() => onGarfoChange(cmd)}
            onPointerUp={() => onGarfoChange("parar")}
            onPointerLeave={() => onGarfoChange("parar")}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
