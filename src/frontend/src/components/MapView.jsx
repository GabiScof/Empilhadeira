import { useMemo, useState } from "react";

const PADDING = 70;
const MAX_HEIGHT_PX = 650;
const TAG_HALF = 8;
const GRID_STEP_M = 0.10;

function cmLabel(m) {
  return `${(m * 100).toFixed(0)} cm`;
}

function coordLabel(xm, ym) {
  return `(${(xm * 100).toFixed(0)}, ${(ym * 100).toFixed(0)})`;
}

export default function MapView({ mapData }) {
  const [hoveredTag, setHoveredTag] = useState(null);

  const layout = useMemo(() => {
    if (!mapData) return null;

    const arenaW = mapData.arena.width_m;
    const arenaH = mapData.arena.height_m;

    const scale = (MAX_HEIGHT_PX - PADDING * 2) / arenaH;
    const canvasW = arenaW * scale;
    const canvasH = arenaH * scale;
    const svgW = canvasW + PADDING * 2;
    const svgH = canvasH + PADDING * 2;

    const toX = (xm) => PADDING + xm * scale;
    const toY = (ym) => PADDING + (arenaH - ym) * scale;

    return { arenaW, arenaH, scale, canvasW, canvasH, svgW, svgH, toX, toY };
  }, [mapData]);

  if (!mapData || !layout) {
    return (
      <div className="rounded-lg bg-slate-800 p-6 text-center text-slate-400">
        Selecione um mapa para visualizar
      </div>
    );
  }

  const { arenaW, arenaH, scale, canvasW, canvasH, svgW, svgH, toX, toY } = layout;
  const tags = mapData.tags || [];
  const startPose = mapData.start_pose;
  const homePose = mapData.home_pose;
  const waypoints = mapData.waypoints || [];
  const edges = mapData.edges || [];
  const standoffPx = 0.15 * scale;

  const wpMap = {};
  waypoints.forEach((wp) => { wpMap[wp.id] = wp; });

  return (
    <div className="rounded-lg bg-slate-800 p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold text-lg">
          Mapa: <span className="text-indigo-400">{mapData.name}</span>
        </h2>
        <span className="text-xs text-slate-400 bg-slate-700 rounded px-2 py-1">
          {cmLabel(arenaW)} × {cmLabel(arenaH)}
        </span>
      </div>

      <svg
        viewBox={`0 0 ${svgW} ${svgH}`}
        className="w-full max-h-[70vh] rounded border border-slate-700 bg-slate-900"
        style={{ aspectRatio: `${svgW}/${svgH}` }}
      >
        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <path d="M0,0 L8,3 L0,6 Z" fill="#94a3b8" />
          </marker>
          <marker id="arrow-rev" markerWidth="8" markerHeight="6" refX="0" refY="3" orient="auto">
            <path d="M8,0 L0,3 L8,6 Z" fill="#94a3b8" />
          </marker>
          <pattern id="grid-pattern" width={GRID_STEP_M * scale} height={GRID_STEP_M * scale}
            patternUnits="userSpaceOnUse" x={PADDING} y={PADDING}>
            <path
              d={`M ${GRID_STEP_M * scale} 0 L 0 0 0 ${GRID_STEP_M * scale}`}
              fill="none" stroke="#334155" strokeWidth="0.5"
            />
          </pattern>
        </defs>

        <rect x={PADDING} y={PADDING} width={canvasW} height={canvasH}
          fill="url(#grid-pattern)" />

        <rect x={PADDING} y={PADDING} width={canvasW} height={canvasH}
          fill="none" stroke="#64748b" strokeWidth="2" rx="2" />

        <line x1={PADDING} y1={PADDING - 30} x2={PADDING + canvasW} y2={PADDING - 30}
          stroke="#94a3b8" strokeWidth="1" markerStart="url(#arrow-rev)" markerEnd="url(#arrow)" />
        <line x1={PADDING} y1={PADDING - 36} x2={PADDING} y2={PADDING - 24}
          stroke="#94a3b8" strokeWidth="0.8" />
        <line x1={PADDING + canvasW} y1={PADDING - 36} x2={PADDING + canvasW} y2={PADDING - 24}
          stroke="#94a3b8" strokeWidth="0.8" />
        <text x={PADDING + canvasW / 2} y={PADDING - 36}
          textAnchor="middle" fill="#cbd5e1" fontSize="12" fontFamily="monospace"
          fontWeight="bold">{cmLabel(arenaW)}</text>

        <line x1={PADDING - 30} y1={PADDING} x2={PADDING - 30} y2={PADDING + canvasH}
          stroke="#94a3b8" strokeWidth="1" markerStart="url(#arrow-rev)" markerEnd="url(#arrow)" />
        <line x1={PADDING - 36} y1={PADDING} x2={PADDING - 24} y2={PADDING}
          stroke="#94a3b8" strokeWidth="0.8" />
        <line x1={PADDING - 36} y1={PADDING + canvasH} x2={PADDING - 24} y2={PADDING + canvasH}
          stroke="#94a3b8" strokeWidth="0.8" />
        <text x={PADDING - 36} y={PADDING + canvasH / 2}
          textAnchor="middle" fill="#cbd5e1" fontSize="12" fontFamily="monospace"
          fontWeight="bold" transform={`rotate(-90, ${PADDING - 36}, ${PADDING + canvasH / 2})`}>
          {cmLabel(arenaH)}
        </text>

        {Array.from({ length: Math.floor(arenaH / 0.20) + 1 }, (_, i) => i * 0.20).map((ym) => (
          <g key={`ytick-${ym}`}>
            <line x1={PADDING - 4} y1={toY(ym)} x2={PADDING} y2={toY(ym)}
              stroke="#64748b" strokeWidth="1" />
            <text x={PADDING - 8} y={toY(ym) + 3}
              textAnchor="end" fill="#64748b" fontSize="8" fontFamily="monospace">
              {(ym * 100).toFixed(0)}
            </text>
          </g>
        ))}

        {Array.from({ length: Math.floor(arenaW / 0.20) + 1 }, (_, i) => i * 0.20).map((xm) => (
          <g key={`xtick-${xm}`}>
            <line x1={toX(xm)} y1={PADDING + canvasH} x2={toX(xm)} y2={PADDING + canvasH + 4}
              stroke="#64748b" strokeWidth="1" />
            <text x={toX(xm)} y={PADDING + canvasH + 14}
              textAnchor="middle" fill="#64748b" fontSize="8" fontFamily="monospace">
              {(xm * 100).toFixed(0)}
            </text>
          </g>
        ))}

        {edges.map(([a, b], i) => {
          const wa = wpMap[a];
          const wb = wpMap[b];
          if (!wa || !wb) return null;
          return (
            <line key={`edge-${i}`}
              x1={toX(wa.x_m)} y1={toY(wa.y_m)} x2={toX(wb.x_m)} y2={toY(wb.y_m)}
              stroke="rgba(148, 163, 184, 0.25)" strokeWidth="1.5" strokeDasharray="4 3" />
          );
        })}

        {waypoints.map((wp) => (
          <g key={`wp-${wp.id}`}>
            <circle cx={toX(wp.x_m)} cy={toY(wp.y_m)} r="3.5"
              fill="rgba(148, 163, 184, 0.4)" stroke="#64748b" strokeWidth="0.5" />
            <text x={toX(wp.x_m)} y={toY(wp.y_m) - 6}
              textAnchor="middle" fill="#64748b" fontSize="7" fontFamily="monospace">
              {wp.id}
            </text>
          </g>
        ))}

        {homePose && (
          <g>
            <circle cx={toX(homePose.x_m)} cy={toY(homePose.y_m)} r="14"
              fill="rgba(34, 197, 94, 0.15)" stroke="#22c55e" strokeWidth="1" strokeDasharray="3 2" />
            <text x={toX(homePose.x_m)} y={toY(homePose.y_m) + 24}
              textAnchor="middle" fill="#22c55e" fontSize="8" fontFamily="monospace"
              fontWeight="bold">HOME</text>
          </g>
        )}

        {startPose && (
          <g>
            <circle cx={toX(startPose.x_m)} cy={toY(startPose.y_m)} r="10"
              fill="rgba(59, 130, 246, 0.2)" stroke="#3b82f6" strokeWidth="1.5" />
            <g transform={`translate(${toX(startPose.x_m)}, ${toY(startPose.y_m)}) rotate(${-startPose.theta_deg + 90})`}>
              <polygon points="0,-7 -5,5 5,5" fill="#3b82f6" opacity="0.8" />
            </g>
            <text x={toX(startPose.x_m)} y={toY(startPose.y_m) - 14}
              textAnchor="middle" fill="#3b82f6" fontSize="8" fontFamily="monospace"
              fontWeight="bold">START</text>
            <text x={toX(startPose.x_m)} y={toY(startPose.y_m) - 24}
              textAnchor="middle" fill="#60a5fa" fontSize="7" fontFamily="monospace">
              {coordLabel(startPose.x_m, startPose.y_m)} {startPose.theta_deg}°
            </text>
          </g>
        )}

        <g>
          <circle cx={toX(0)} cy={toY(0)} r="4"
            fill="none" stroke="#f87171" strokeWidth="1.5" />
          <line x1={toX(0) - 6} y1={toY(0)} x2={toX(0) + 6} y2={toY(0)}
            stroke="#f87171" strokeWidth="1" />
          <line x1={toX(0)} y1={toY(0) - 6} x2={toX(0)} y2={toY(0) + 6}
            stroke="#f87171" strokeWidth="1" />
          <text x={toX(0) + 8} y={toY(0) + 4}
            fill="#f87171" fontSize="9" fontFamily="monospace" fontWeight="bold">
            O(0,0)
          </text>
        </g>

        {tags.map((tag) => {
          const tx = toX(tag.x_m);
          const ty = toY(tag.y_m);
          const yawRad = ((tag.yaw_deg || 0) * Math.PI) / 180;
          const isHovered = hoveredTag === tag.position_id;

          const wallSide = tag.wall || "left";
          const labelX = wallSide === "right"
            ? tx + TAG_HALF + 6
            : tx - TAG_HALF - 6;
          const labelAnchor = wallSide === "right" ? "start" : "end";

          return (
            <g key={tag.position_id}
              onMouseEnter={() => setHoveredTag(tag.position_id)}
              onMouseLeave={() => setHoveredTag(null)}
              style={{ cursor: "pointer" }}>

              <line
                x1={tx} y1={ty}
                x2={tx + standoffPx * Math.cos(yawRad)}
                y2={ty - standoffPx * Math.sin(yawRad)}
                stroke={isHovered ? "#818cf8" : "#f59e0b"} strokeWidth="1"
                strokeDasharray="3 2" opacity="0.6" />

              <circle
                cx={tx + standoffPx * Math.cos(yawRad)}
                cy={ty - standoffPx * Math.sin(yawRad)}
                r="2.5" fill={isHovered ? "#818cf8" : "#f59e0b"} opacity="0.5" />

              <g transform={`translate(${tx}, ${ty}) rotate(${-(tag.yaw_deg || 0)})`}>
                <rect x={-TAG_HALF} y={-TAG_HALF} width={TAG_HALF * 2} height={TAG_HALF * 2}
                  fill={isHovered ? "#818cf8" : "#f59e0b"} rx="1"
                  stroke={isHovered ? "#a5b4fc" : "#fbbf24"} strokeWidth="1" />
                <rect x={-TAG_HALF / 2} y={-TAG_HALF / 2}
                  width={TAG_HALF} height={TAG_HALF}
                  fill="#1e293b" rx="0.5" />
                <line x1={TAG_HALF} y1={-TAG_HALF} x2={TAG_HALF} y2={TAG_HALF}
                  stroke="#e2e8f0" strokeWidth="2.5" />
              </g>

              {isHovered && (
                <g>
                  <line
                    x1={tx - TAG_HALF - 2} y1={ty - TAG_HALF - 4}
                    x2={tx + TAG_HALF + 2} y2={ty - TAG_HALF - 4}
                    stroke="#fbbf24" strokeWidth="0.5" />
                  <text x={tx} y={ty - TAG_HALF - 7}
                    textAnchor="middle" fill="#fbbf24" fontSize="7" fontFamily="monospace">
                    5 cm
                  </text>
                </g>
              )}

              <text x={labelX} y={ty - 2}
                textAnchor={labelAnchor} fill={isHovered ? "#c7d2fe" : "#94a3b8"}
                fontSize="10" fontFamily="monospace" fontWeight="bold">
                {tag.position_id}
              </text>

              <text x={labelX} y={ty + 10}
                textAnchor={labelAnchor} fill={isHovered ? "#a5b4fc" : "#64748b"}
                fontSize="8" fontFamily="monospace">
                {coordLabel(tag.x_m, tag.y_m)}
              </text>

              {isHovered && tag.wall && (
                <text x={labelX} y={ty + 20}
                  textAnchor={labelAnchor} fill="#64748b"
                  fontSize="7" fontFamily="monospace" fontStyle="italic">
                  {tag.wall} · {tag.yaw_deg}°
                </text>
              )}
            </g>
          );
        })}

        <g transform={`translate(${PADDING + 8}, ${PADDING + canvasH - 80})`}>
          <rect x="-4" y="-12" width="120" height="78" rx="4"
            fill="rgba(15, 23, 42, 0.85)" stroke="#334155" strokeWidth="0.5" />

          <rect x="2" y="0" width="8" height="8" fill="#f59e0b" rx="1" />
          <text x="16" y="8" fill="#94a3b8" fontSize="8" fontFamily="monospace">AprilTag</text>

          <circle cx="6" cy="20" r="4" fill="rgba(59, 130, 246, 0.5)"
            stroke="#3b82f6" strokeWidth="1" />
          <text x="16" y="23" fill="#94a3b8" fontSize="8" fontFamily="monospace">Start/Home</text>

          <circle cx="6" cy="35" r="3" fill="none" stroke="#f87171" strokeWidth="1" />
          <text x="16" y="38" fill="#94a3b8" fontSize="8" fontFamily="monospace">Origem O(0,0)</text>

          <line x1="2" y1="50" x2="10" y2="50"
            stroke="#f59e0b" strokeWidth="1" strokeDasharray="3 2" />
          <text x="16" y="53" fill="#94a3b8" fontSize="8" fontFamily="monospace">Standoff 15cm</text>
        </g>
      </svg>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3">
        <div className="bg-slate-700/50 rounded px-3 py-2">
          <div className="text-xs text-slate-400">Arena</div>
          <div className="text-sm font-mono font-semibold">{cmLabel(arenaW)} × {cmLabel(arenaH)}</div>
        </div>
        <div className="bg-slate-700/50 rounded px-3 py-2">
          <div className="text-xs text-slate-400">Tags</div>
          <div className="text-sm font-mono font-semibold">{tags.length} posições</div>
        </div>
        <div className="bg-slate-700/50 rounded px-3 py-2">
          <div className="text-xs text-slate-400">Tag Size</div>
          <div className="text-sm font-mono font-semibold">5 cm</div>
        </div>
        <div className="bg-slate-700/50 rounded px-3 py-2">
          <div className="text-xs text-slate-400">Waypoints</div>
          <div className="text-sm font-mono font-semibold">
            {waypoints.length > 0 ? `${waypoints.length} nós` : "Sem grafo"}
          </div>
        </div>
      </div>

      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="text-slate-400 border-b border-slate-700">
              <th className="text-left py-1.5 px-2">ID</th>
              <th className="text-left py-1.5 px-2">X (cm)</th>
              <th className="text-left py-1.5 px-2">Y (cm)</th>
              <th className="text-left py-1.5 px-2">Parede</th>
              <th className="text-left py-1.5 px-2">Yaw</th>
            </tr>
          </thead>
          <tbody>
            {tags.map((tag) => (
              <tr key={tag.position_id}
                className={`border-b border-slate-700/50 transition-colors ${
                  hoveredTag === tag.position_id ? "bg-indigo-900/30" : "hover:bg-slate-700/30"
                }`}
                onMouseEnter={() => setHoveredTag(tag.position_id)}
                onMouseLeave={() => setHoveredTag(null)}>
                <td className="py-1.5 px-2 font-bold text-amber-400">{tag.position_id}</td>
                <td className="py-1.5 px-2">{(tag.x_m * 100).toFixed(0)}</td>
                <td className="py-1.5 px-2">{(tag.y_m * 100).toFixed(0)}</td>
                <td className="py-1.5 px-2 text-slate-400">{tag.wall || "—"}</td>
                <td className="py-1.5 px-2 text-slate-400">{tag.yaw_deg}°</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
