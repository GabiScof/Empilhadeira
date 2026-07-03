import { useState } from "react";

export default function PoseResetPanel({ apiBase }) {
  const [x, setX] = useState(100);
  const [y, setY] = useState(150);
  const [theta, setTheta] = useState(0);
  const [status, setStatus] = useState("");

  const handleReset = async () => {
    try {
      const res = await fetch(`${apiBase}/sim/reset-pose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ x, y, theta: (theta * Math.PI) / 180 }),
      });
      if (res.ok) setStatus("Pose resetada");
      else setStatus("Erro ao resetar");
    } catch {
      setStatus("Falha de conexão");
    }
    setTimeout(() => setStatus(""), 2000);
  };

  return (
    <div className="rounded-lg bg-slate-800 p-4">
      <h2 className="font-semibold mb-2">Reset de Pose</h2>
      <div className="grid grid-cols-3 gap-2 mb-2">
        <label className="text-xs">
          X (cm)
          <input
            type="number"
            value={x}
            onChange={(e) => setX(Number(e.target.value))}
            className="w-full mt-1 px-2 py-1 rounded bg-slate-700 text-sm"
          />
        </label>
        <label className="text-xs">
          Y (cm)
          <input
            type="number"
            value={y}
            onChange={(e) => setY(Number(e.target.value))}
            className="w-full mt-1 px-2 py-1 rounded bg-slate-700 text-sm"
          />
        </label>
        <label className="text-xs">
          θ (°)
          <input
            type="number"
            value={theta}
            onChange={(e) => setTheta(Number(e.target.value))}
            className="w-full mt-1 px-2 py-1 rounded bg-slate-700 text-sm"
          />
        </label>
      </div>
      <button
        onClick={handleReset}
        className="w-full rounded bg-indigo-700 hover:bg-indigo-600 py-1.5 text-sm font-medium"
        type="button"
      >
        Resetar Pose
      </button>
      {status && (
        <p className="text-xs text-center mt-1 text-slate-400">{status}</p>
      )}
    </div>
  );
}
