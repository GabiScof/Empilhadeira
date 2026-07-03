export default function ForkSideView({ worldState }) {
  const forkHeight = worldState?.fork_height ?? 0;
  const atTop = worldState?.fork_at_top ?? false;
  const atBottom = worldState?.fork_at_bottom ?? false;
  const maxHeight = 10;
  const pct = Math.min(100, (forkHeight / maxHeight) * 100);

  return (
    <div className="rounded-lg bg-slate-800 p-4">
      <h2 className="font-semibold mb-2">Garfo (vista lateral)</h2>
      <div className="flex items-end gap-4">
        <div className="flex flex-col items-center gap-1 w-16">
          <span
            className={`text-xs px-1 rounded ${
              atTop ? "bg-red-700 text-red-200" : "bg-slate-700 text-slate-400"
            }`}
          >
            TOPO
          </span>
          <div className="relative w-8 h-32 bg-slate-700 rounded overflow-hidden">
            <div
              className="absolute bottom-0 w-full bg-amber-600 transition-all duration-150"
              style={{ height: `${pct}%` }}
            />
          </div>
          <span
            className={`text-xs px-1 rounded ${
              atBottom
                ? "bg-red-700 text-red-200"
                : "bg-slate-700 text-slate-400"
            }`}
          >
            BASE
          </span>
        </div>
        <div className="text-sm space-y-1">
          <p>
            Altura:{" "}
            <span className="font-mono">{forkHeight.toFixed(1)} cm</span>
          </p>
          <p>
            Topo:{" "}
            <span className={atTop ? "text-red-400" : "text-slate-400"}>
              {atTop ? "ACIONADO" : "livre"}
            </span>
          </p>
          <p>
            Base:{" "}
            <span className={atBottom ? "text-red-400" : "text-slate-400"}>
              {atBottom ? "ACIONADO" : "livre"}
            </span>
          </p>
        </div>
      </div>
    </div>
  );
}
