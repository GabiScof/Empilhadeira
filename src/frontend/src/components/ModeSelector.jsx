const MODES = ["MANUAL", "AUTOMATICO", "PARADO"];

const MODE_COLORS = {
  MANUAL: "bg-blue-600 hover:bg-blue-500",
  AUTOMATICO: "bg-green-600 hover:bg-green-500",
  PARADO: "bg-red-600 hover:bg-red-500",
};

export default function ModeSelector({ currentMode, onModeChange, disabled }) {
  return (
    <div className="rounded-lg bg-slate-800 p-4">
      <h2 className="font-semibold mb-2">Modo</h2>
      <div className="flex gap-2">
        {MODES.map((m) => {
          const isActive = currentMode === m;
          const base = isActive
            ? MODE_COLORS[m]
            : "bg-slate-700 hover:bg-slate-600";
          return (
            <button
              key={m}
              className={`flex-1 rounded py-2 text-sm font-medium transition-colors ${base} ${
                isActive ? "ring-2 ring-white/30" : ""
              }`}
              type="button"
              disabled={disabled}
              onClick={() => onModeChange?.(m)}
            >
              {m}
            </button>
          );
        })}
      </div>
    </div>
  );
}
