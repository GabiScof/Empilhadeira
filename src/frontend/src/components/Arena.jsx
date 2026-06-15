import { useRef, useEffect } from "react";

const SCALE = 2.5;
const FOV_RANGE = 100;
const FOV_HALF_DEG = 30;

export default function Arena({ worldState }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !worldState?.world) return;

    const ctx = canvas.getContext("2d");
    const { robot, tag, arena, trail } = worldState.world;

    const w = arena.width * SCALE;
    const h = arena.height * SCALE;
    canvas.width = w;
    canvas.height = h;

    ctx.fillStyle = "#1e293b";
    ctx.fillRect(0, 0, w, h);

    ctx.strokeStyle = "#334155";
    ctx.lineWidth = 1;
    for (let x = 0; x <= arena.width; x += 20) {
      ctx.beginPath();
      ctx.moveTo(x * SCALE, 0);
      ctx.lineTo(x * SCALE, h);
      ctx.stroke();
    }
    for (let y = 0; y <= arena.height; y += 20) {
      ctx.beginPath();
      ctx.moveTo(0, y * SCALE);
      ctx.lineTo(w, y * SCALE);
      ctx.stroke();
    }

    if (trail && trail.length > 1) {
      ctx.strokeStyle = "#475569";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(trail[0][0] * SCALE, trail[0][1] * SCALE);
      for (let i = 1; i < trail.length; i++) {
        ctx.lineTo(trail[i][0] * SCALE, trail[i][1] * SCALE);
      }
      ctx.stroke();
    }

    const rx = robot.x * SCALE;
    const ry = robot.y * SCALE;

    ctx.save();
    ctx.translate(rx, ry);
    ctx.rotate(robot.theta);
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.arc(
      0,
      0,
      FOV_RANGE * SCALE,
      -FOV_HALF_DEG * (Math.PI / 180),
      FOV_HALF_DEG * (Math.PI / 180),
    );
    ctx.closePath();
    ctx.fillStyle = "rgba(59, 130, 246, 0.08)";
    ctx.fill();
    ctx.restore();

    const zref = 5;
    ctx.strokeStyle = "rgba(16, 185, 129, 0.4)";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.arc(tag.x * SCALE, tag.y * SCALE, zref * SCALE, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.save();
    ctx.translate(tag.x * SCALE, tag.y * SCALE);
    ctx.rotate(tag.theta);
    ctx.fillStyle = "#f59e0b";
    ctx.fillRect(-8, -8, 16, 16);
    ctx.fillStyle = "#1e293b";
    ctx.fillRect(-4, -4, 8, 8);
    ctx.restore();

    ctx.save();
    ctx.translate(rx, ry);
    ctx.rotate(robot.theta);
    ctx.fillStyle = "#3b82f6";
    ctx.beginPath();
    ctx.moveTo(12, 0);
    ctx.lineTo(-8, -7);
    ctx.lineTo(-8, 7);
    ctx.closePath();
    ctx.fill();
    ctx.restore();

    ctx.fillStyle = "#94a3b8";
    ctx.font = "11px monospace";
    ctx.fillText(
      `Robot: (${robot.x.toFixed(0)}, ${robot.y.toFixed(0)}) θ=${(robot.theta * 180 / Math.PI).toFixed(1)}°`,
      8,
      16,
    );
  }, [worldState]);

  return (
    <div className="rounded-lg bg-slate-800 p-3">
      <h2 className="font-semibold mb-2">Arena (vista de cima)</h2>
      <canvas
        ref={canvasRef}
        className="w-full rounded border border-slate-700"
        style={{ aspectRatio: "1/1", maxHeight: 500 }}
      />
    </div>
  );
}
