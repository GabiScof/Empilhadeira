import { useState } from "react";

const FAULTS = [
  { type: "serial_drop", label: "Queda Serial" },
  { type: "tag_hidden", label: "Tag Oculta" },
  { type: "battery_saturated", label: "Bateria Saturada" },
];

export default function FaultInjector({ apiBase }) {
  const [active, setActive] = useState({});
  const [slipEsq, setSlipEsq] = useState(1.0);
  const [slipDir, setSlipDir] = useState(1.0);

  const toggleFault = async (faultType) => {
    const newActive = !active[faultType];
    try {
      await fetch(`${apiBase}/sim/inject-fault`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fault_type: faultType, active: newActive }),
      });
      setActive((prev) => ({ ...prev, [faultType]: newActive }));
    } catch {
      // falha silenciosa
    }
  };

  const applySlip = async () => {
    try {
      await fetch(`${apiBase}/sim/inject-fault`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fault_type: "wheel_slip",
          active: true,
          value: slipEsq,
          value2: slipDir,
        }),
      });
    } catch {
      // falha silenciosa
    }
  };

  const clearAll = async () => {
    try {
      await fetch(`${apiBase}/sim/inject-fault`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fault_type: "clear_all", active: false }),
      });
      setActive({});
      setSlipEsq(1.0);
      setSlipDir(1.0);
    } catch {
      // falha silenciosa
    }
  };

  return (
    <div className="rounded-lg bg-slate-800 p-4">
      <h2 className="font-semibold mb-2">Injeção de Falhas</h2>
      <div className="space-y-2">
        {FAULTS.map((f) => (
          <button
            key={f.type}
            onClick={() => toggleFault(f.type)}
            className={`w-full rounded py-1.5 text-sm font-medium transition-colors ${
              active[f.type]
                ? "bg-red-700 hover:bg-red-600"
                : "bg-slate-700 hover:bg-slate-600"
            }`}
            type="button"
          >
            {f.label} {active[f.type] ? "(ATIVO)" : ""}
          </button>
        ))}

        <div className="flex gap-2 items-end">
          <label className="text-xs flex-1">
            Slip Esq
            <input
              type="number"
              step="0.1"
              value={slipEsq}
              onChange={(e) => setSlipEsq(Number(e.target.value))}
              className="w-full mt-1 px-2 py-1 rounded bg-slate-700 text-sm"
            />
          </label>
          <label className="text-xs flex-1">
            Slip Dir
            <input
              type="number"
              step="0.1"
              value={slipDir}
              onChange={(e) => setSlipDir(Number(e.target.value))}
              className="w-full mt-1 px-2 py-1 rounded bg-slate-700 text-sm"
            />
          </label>
          <button
            onClick={applySlip}
            className="rounded bg-slate-700 hover:bg-slate-600 px-3 py-1 text-xs"
            type="button"
          >
            Aplicar
          </button>
        </div>

        <button
          onClick={clearAll}
          className="w-full rounded bg-slate-600 hover:bg-slate-500 py-1.5 text-xs"
          type="button"
        >
          Limpar Todas
        </button>
      </div>
    </div>
  );
}
