/**
 * Página de visualização de mapas da arena.
 *
 * Permite selecionar qualquer mapa disponível e visualizar a planta
 * com dimensões, posições de tags, waypoints e anotações.
 * Funciona independente do modo de simulação (não precisa de SIM=1).
 */

import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import MapView from "../components/MapView.jsx";

const API_BASE =
  window.location.protocol +
  "//" +
  (window.location.hostname || "localhost") +
  ":8000";

export default function MapPage() {
  const [maps, setMaps] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [mapData, setMapData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/maps/list`)
      .then((r) => r.json())
      .then((data) => {
        const list = data.maps || [];
        setMaps(list);
        if (list.length > 0 && !selectedFile) {
          loadMap(list[0].file);
        }
      })
      .catch(() => setError("Sem conexão com o backend"));
  }, []);

  const loadMap = async (file) => {
    setLoading(true);
    setError(null);
    setSelectedFile(file);
    try {
      const res = await fetch(`${API_BASE}/maps/${file}`);
      const data = await res.json();
      if (data.ok) {
        setMapData(data.map);
      } else {
        setError(data.error || "Erro ao carregar mapa");
      }
    } catch {
      setError("Falha na comunicação com o backend");
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-4">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold">Visualizar Mapa</h1>
        <div className="flex items-center gap-2">
          <Link
            to="/"
            className="text-xs px-3 py-1 rounded bg-slate-700 hover:bg-slate-600 transition-colors"
          >
            Operador
          </Link>
          <Link
            to="/demo"
            className="text-xs px-3 py-1 rounded bg-slate-700 hover:bg-slate-600 transition-colors"
          >
            Demo
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Sidebar: map list */}
        <div className="space-y-2">
          <div className="rounded-lg bg-slate-800 p-4">
            <h2 className="font-semibold mb-3 text-sm">Mapas Disponíveis</h2>
            <div className="space-y-1.5">
              {maps.map((m) => (
                <button
                  key={m.file}
                  onClick={() => loadMap(m.file)}
                  disabled={loading}
                  className={`w-full text-left rounded px-3 py-2.5 text-sm transition-colors ${
                    selectedFile === m.file
                      ? "bg-indigo-700 text-white ring-1 ring-indigo-500"
                      : "bg-slate-700 hover:bg-slate-600 text-slate-200"
                  }`}
                  type="button"
                >
                  <div className="font-medium">{m.name}</div>
                  <div className="text-xs opacity-70 mt-0.5">
                    {(m.arena.width_m * 100).toFixed(0)}×{(m.arena.height_m * 100).toFixed(0)} cm
                    {" · "}{m.tags} tags
                    {m.has_graph ? " · grafo" : ""}
                  </div>
                </button>
              ))}
              {maps.length === 0 && !error && (
                <p className="text-xs text-slate-500">Carregando...</p>
              )}
            </div>
          </div>

          {/* Quick info */}
          {mapData && (
            <div className="rounded-lg bg-slate-800 p-4">
              <h2 className="font-semibold mb-2 text-sm">Coordenadas</h2>
              <div className="text-xs text-slate-400 space-y-1 font-mono">
                <p>Origem: inferior esquerdo</p>
                <p>+X: direita (largura)</p>
                <p>+Y: cima (comprimento)</p>
                <p>Unidades: metros (m)</p>
                <p>Yaw: anti-horário de +X</p>
              </div>
            </div>
          )}
        </div>

        {/* Main content: map viewer */}
        <div className="lg:col-span-3">
          {error && (
            <div className="rounded-lg bg-red-900/30 border border-red-800 p-4 mb-4 text-sm text-red-300">
              {error}
            </div>
          )}
          {loading && (
            <div className="rounded-lg bg-slate-800 p-8 text-center text-slate-400">
              Carregando mapa...
            </div>
          )}
          {!loading && <MapView mapData={mapData} />}
        </div>
      </div>
    </div>
  );
}
