import { useRef, useEffect } from "react";

const CANVAS_MAX_PX = 600;
const ROBOT_SIZE_PX = 14;
const TAG_SIZE_PX = 10;
const FOV_HALF_DEG = 30;

export default function Arena({ worldState, telemetry }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !worldState?.world) return;

    const ctx = canvas.getContext("2d");
    const { robot, tags, arena, trail } = worldState.world;

    const arenaW = arena.width_m;
    const arenaH = arena.height_m;
    const scale = CANVAS_MAX_PX / Math.max(arenaW, arenaH);
    const w = Math.round(arenaW * scale);
    const h = Math.round(arenaH * scale);
    canvas.width = w;
    canvas.height = h;

    const toX = (xm) => xm * scale;
    const toY = (ym) => ym * scale;

    // Background
    ctx.fillStyle = "#1e293b";
    ctx.fillRect(0, 0, w, h);

    // Grid (every 0.1m)
    ctx.strokeStyle = "#334155";
    ctx.lineWidth = 0.5;
    const gridStep = 0.1;
    for (let x = 0; x <= arenaW; x += gridStep) {
      ctx.beginPath();
      ctx.moveTo(toX(x), 0);
      ctx.lineTo(toX(x), h);
      ctx.stroke();
    }
    for (let y = 0; y <= arenaH; y += gridStep) {
      ctx.beginPath();
      ctx.moveTo(0, toY(y));
      ctx.lineTo(w, toY(y));
      ctx.stroke();
    }

    // Arena border
    ctx.strokeStyle = "#64748b";
    ctx.lineWidth = 2;
    ctx.strokeRect(1, 1, w - 2, h - 2);

    // Home pose marker
    if (worldState.world_model?.home_pose) {
      const hp = worldState.world_model.home_pose;
      ctx.fillStyle = "rgba(34, 197, 94, 0.3)";
      ctx.beginPath();
      ctx.arc(toX(hp.x_m), toY(hp.y_m), 12, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#22c55e";
      ctx.font = "9px monospace";
      ctx.fillText("HOME", toX(hp.x_m) - 14, toY(hp.y_m) + 18);
    }

    // Waypoints and edges (if graph exists)
    if (worldState.world_model?.waypoints) {
      const wpMap = {};
      worldState.world_model.waypoints.forEach((wp) => {
        wpMap[wp.id] = wp;
      });

      if (worldState.world_model.edges) {
        ctx.strokeStyle = "rgba(148, 163, 184, 0.3)";
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        worldState.world_model.edges.forEach(([a, b]) => {
          if (wpMap[a] && wpMap[b]) {
            ctx.beginPath();
            ctx.moveTo(toX(wpMap[a].x_m), toY(wpMap[a].y_m));
            ctx.lineTo(toX(wpMap[b].x_m), toY(wpMap[b].y_m));
            ctx.stroke();
          }
        });
        ctx.setLineDash([]);
      }

      ctx.fillStyle = "rgba(148, 163, 184, 0.5)";
      Object.values(wpMap).forEach((wp) => {
        ctx.beginPath();
        ctx.arc(toX(wp.x_m), toY(wp.y_m), 3, 0, Math.PI * 2);
        ctx.fill();
      });
    }

    // Planned path
    if (worldState.planned_path && worldState.planned_path.length > 0) {
      ctx.strokeStyle = "rgba(99, 102, 241, 0.6)";
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(toX(robot.x_m), toY(robot.y_m));
      worldState.planned_path.forEach((seg) => {
        if (seg.type === "FORWARD") {
          ctx.lineTo(toX(seg.target_x), toY(seg.target_y));
        }
      });
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Executed trail
    const execTrail = worldState.executed_trail || trail;
    if (execTrail && execTrail.length > 1) {
      ctx.strokeStyle = "#475569";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(toX(execTrail[0][0]), toY(execTrail[0][1]));
      for (let i = 1; i < execTrail.length; i++) {
        ctx.lineTo(toX(execTrail[i][0]), toY(execTrail[i][1]));
      }
      ctx.stroke();
    }

    // Robot FOV
    const rx = toX(robot.x_m);
    const ry = toY(robot.y_m);
    const rTheta = robot.theta_rad;

    ctx.save();
    ctx.translate(rx, ry);
    ctx.rotate(rTheta);
    const fovRange = 0.5 * scale;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.arc(0, 0, fovRange, -FOV_HALF_DEG * Math.PI / 180, FOV_HALF_DEG * Math.PI / 180);
    ctx.closePath();
    ctx.fillStyle = "rgba(59, 130, 246, 0.08)";
    ctx.fill();
    ctx.restore();

    // EKF covariance ellipse
    const ekf = worldState.ekf || telemetry?.ekf;
    if (ekf && ekf.ellipse_semi_major_m > 0) {
      ctx.save();
      ctx.translate(toX(ekf.x_m), toY(ekf.y_m));
      ctx.rotate(ekf.ellipse_angle_rad);
      ctx.strokeStyle = "rgba(251, 191, 36, 0.6)";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.ellipse(0, 0, ekf.ellipse_semi_major_m * scale, ekf.ellipse_semi_minor_m * scale, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }

    // Tags with front-side indicator
    const mission = worldState.mission || telemetry?.mission;
    const standoffPx = 0.15 * scale;
    tags.forEach((tag) => {
      const tx = toX(tag.x_m);
      const ty = toY(tag.y_m);
      const tagYaw = (tag.yaw_deg || 0) * Math.PI / 180;

      let color = "#f59e0b";
      let isTarget = false;
      if (mission?.pick_position_id === tag.position_id) { color = "#ef4444"; isTarget = true; }
      if (mission?.place_position_id === tag.position_id) { color = "#22c55e"; isTarget = true; }

      // Front-side direction line (shows which way the tag faces)
      ctx.save();
      ctx.translate(tx, ty);
      ctx.rotate(tagYaw);
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([3, 2]);
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(standoffPx, 0);
      ctx.stroke();
      ctx.setLineDash([]);

      // Approach point (where robot stops)
      if (isTarget) {
        ctx.fillStyle = color;
        ctx.globalAlpha = 0.5;
        ctx.beginPath();
        ctx.arc(standoffPx, 0, 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1.0;
      }

      // Tag body: back side (wall) is solid, front side is marked
      ctx.fillStyle = color;
      ctx.fillRect(-TAG_SIZE_PX / 2, -TAG_SIZE_PX / 2, TAG_SIZE_PX, TAG_SIZE_PX);
      // Inner pattern (AprilTag-like)
      ctx.fillStyle = "#1e293b";
      ctx.fillRect(-TAG_SIZE_PX / 4, -TAG_SIZE_PX / 4, TAG_SIZE_PX / 2, TAG_SIZE_PX / 2);
      // Front face indicator (white line on front edge)
      ctx.strokeStyle = "#e2e8f0";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(TAG_SIZE_PX / 2, -TAG_SIZE_PX / 2);
      ctx.lineTo(TAG_SIZE_PX / 2, TAG_SIZE_PX / 2);
      ctx.stroke();
      ctx.restore();

      ctx.fillStyle = "#94a3b8";
      ctx.font = "9px monospace";
      ctx.fillText(tag.position_id, tx + TAG_SIZE_PX, ty - 2);
    });

    // Robot body
    ctx.save();
    ctx.translate(rx, ry);
    ctx.rotate(rTheta);
    ctx.fillStyle = "#3b82f6";
    ctx.beginPath();
    ctx.moveTo(ROBOT_SIZE_PX, 0);
    ctx.lineTo(-ROBOT_SIZE_PX * 0.6, -ROBOT_SIZE_PX * 0.5);
    ctx.lineTo(-ROBOT_SIZE_PX * 0.6, ROBOT_SIZE_PX * 0.5);
    ctx.closePath();
    ctx.fill();
    ctx.restore();

    // Info overlay
    ctx.fillStyle = "#94a3b8";
    ctx.font = "10px monospace";
    const info = `(${robot.x_m.toFixed(2)}, ${robot.y_m.toFixed(2)}) θ=${robot.theta_deg.toFixed(1)}°`;
    ctx.fillText(info, 6, 14);

    if (ekf) {
      ctx.fillStyle = "#fbbf24";
      ctx.fillText(`EKF: (${ekf.x_m.toFixed(2)}, ${ekf.y_m.toFixed(2)}) P=${ekf.covariance_trace.toFixed(4)}`, 6, 26);
    }

    const mapName = worldState.world_model?.name || telemetry?.map_name || "";
    if (mapName) {
      ctx.fillStyle = "#64748b";
      ctx.fillText(`Mapa: ${mapName}`, 6, h - 6);
    }
  }, [worldState, telemetry]);

  return (
    <div className="rounded-lg bg-slate-800 p-3">
      <h2 className="font-semibold mb-2">Arena (vista de cima)</h2>
      <canvas
        ref={canvasRef}
        className="block mx-auto rounded border border-slate-700"
        style={{ maxWidth: "100%", maxHeight: CANVAS_MAX_PX, height: "auto", width: "auto" }}
      />
      <div className="flex gap-3 mt-1 text-xs text-slate-500">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" /> Robô
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" /> Tag
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-red-500 inline-block" /> Pick
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-green-500 inline-block" /> Place
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded bg-yellow-500/60 inline-block" /> EKF
        </span>
      </div>
    </div>
  );
}
