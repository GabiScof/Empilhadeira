export default function ForkControl({ onForkCommand }) {
  const handleDown = (cmd) => () => onForkCommand?.(cmd);
  const handleUp = () => onForkCommand?.("parar");

  return (
    <div className="rounded-lg bg-slate-800 p-4">
      <h2 className="font-semibold mb-2">Garfo</h2>
      <div className="flex gap-3">
        <button
          className="flex-1 rounded bg-amber-700 hover:bg-amber-600 py-3 text-sm font-medium transition-colors active:bg-amber-500"
          type="button"
          onPointerDown={handleDown("subir")}
          onPointerUp={handleUp}
          onPointerLeave={handleUp}
        >
          Subir
        </button>
        <button
          className="flex-1 rounded bg-amber-700 hover:bg-amber-600 py-3 text-sm font-medium transition-colors active:bg-amber-500"
          type="button"
          onPointerDown={handleDown("descer")}
          onPointerUp={handleUp}
          onPointerLeave={handleUp}
        >
          Descer
        </button>
      </div>
    </div>
  );
}
