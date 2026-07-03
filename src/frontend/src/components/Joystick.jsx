import { useEffect, useRef } from "react";
import nipplejs from "nipplejs";

export default function Joystick({ onMove, disabled }) {
  const containerRef = useRef(null);
  const managerRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const manager = nipplejs.create({
      zone: containerRef.current,
      mode: "static",
      position: { left: "50%", top: "50%" },
      color: disabled ? "#475569" : "#3b82f6",
      size: 120,
    });

    managerRef.current = manager;

    manager.on("move", (_evt, data) => {
      if (disabled) return;
      const angle = data.angle?.radian ?? 0;
      const force = Math.min(data.force ?? 0, 1);
      const x = Math.cos(angle) * force;
      const y = Math.sin(angle) * force;
      onMove?.({
        x: parseFloat(x.toFixed(3)),
        y: parseFloat(y.toFixed(3)),
      });
    });

    manager.on("end", () => {
      onMove?.({ x: 0, y: 0 });
    });

    return () => {
      manager.destroy();
    };
  }, [disabled, onMove]);

  return (
    <div className="rounded-lg bg-slate-800 p-4">
      <h2 className="font-semibold mb-2">
        Joystick {disabled && <span className="text-slate-500">(inativo)</span>}
      </h2>
      <div
        ref={containerRef}
        className="relative h-40 rounded-full bg-slate-700"
        style={{ touchAction: "none" }}
      />
    </div>
  );
}
