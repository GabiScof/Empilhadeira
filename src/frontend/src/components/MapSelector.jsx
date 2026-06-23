import { useState, useEffect } from "react";

export default function MapSelector({ apiBase, onMapLoaded }) {
  const [maps, setMaps] = useState([]);
  const [current, setCurrent] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${apiBase}/maps/list`)
      .then((r) => r.json())
      .then((data) => setMaps(data.maps || []))
      .catch(() => {});
    fetch(`${apiBase}/maps/current`)
      .then((r) => r.json())
      .then((data) => {
        if (data.ok && data.map) setCurrent(data.map.name);
      })
      .catch(() => {});
  }, [apiBase]);

  const loadMap = async (file) => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/maps/load/${file}`, { method: "POST" });
      const data = await res.json();
      if (data.ok) {
        setCurrent(data.map.name);
        if (onMapLoaded) onMapLoaded(data.map);
      }
    } catch {}
    setLoading(false);
  };

  return (
    <div className="rounded-lg bg-slate-800 p-4">
      <h2 className="font-semibold mb-2">Seletor de Mapa</h2>
      <div className="space-y-1.5">
        {maps.map((m) => (
          <button
            key={m.file}
            onClick={() => loadMap(m.file)}
            disabled={loading}
            className={`w-full text-left rounded px-3 py-2 text-sm transition-colors ${
              current === m.name
                ? "bg-indigo-700 text-white"
                : "bg-slate-700 hover:bg-slate-600 text-slate-200"
            }`}
            type="button"
          >
            <div className="font-medium">{m.name}</div>
            <div className="text-xs opacity-70">
              {m.arena.width_m}×{m.arena.height_m}m · {m.tags} tags
              {m.has_graph ? " · grafo" : ""}
            </div>
          </button>
        ))}
        {maps.length === 0 && (
          <p className="text-xs text-slate-500">Nenhum mapa encontrado</p>
        )}
      </div>
      {current && (
        <p className="text-xs text-slate-400 mt-2">Ativo: {current}</p>
      )}
    </div>
  );
}
