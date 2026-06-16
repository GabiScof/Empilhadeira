// Joystick.jsx — Joystick virtual (nipplejs) para o modo MANUAL.
//
// Convencao de eixos (espelha contrato 1):
//   x em [-1, 1]: giro (omega) — positivo = virar direita
//   y em [-1, 1]: avanco (v)   — positivo = frente
//
// A instancia nipplejs e criada uma vez (useEffect vazio) e usa um ref para
// o callback a fim de evitar recriacoes desnecessarias. Desabilitado visualmente
// (pointer-events: none) fora do modo MANUAL, mas o Pi ignora o joystick nos
// outros modos de qualquer forma (contrato 1).
//
// [ref: Secao 1 e 6 da AGENTS.md]

import nipplejs from "nipplejs";
import { useEffect, useRef } from "react";

/**
 * @param {{
 *   onJoystickChange: (pos: {x: number, y: number}) => void,
 *   mode: import('../types/contracts').Mode
 * }} props
 */
export default function Joystick({ onJoystickChange, mode }) {
  const zoneRef = useRef(null);
  // Ref p/ callback evita recriar o manager toda vez que onJoystickChange muda referencia
  const cbRef = useRef(onJoystickChange);
  useEffect(() => {
    cbRef.current = onJoystickChange;
  }, [onJoystickChange]);

  useEffect(() => {
    if (!zoneRef.current) return;

    const manager = nipplejs.create({
      zone: zoneRef.current,
      mode: "static",
      position: { left: "50%", top: "50%" },
      color: "#60a5fa",
      size: 110,
    });

    manager.on("move", (_, data) => {
      const force = Math.min(data.force, 1.0);
      const angle = data.angle.radian;
      cbRef.current({
        x: parseFloat((force * Math.cos(angle)).toFixed(3)),
        y: parseFloat((force * Math.sin(angle)).toFixed(3)),
      });
    });

    manager.on("end", () => {
      cbRef.current({ x: 0, y: 0 });
    });

    return () => manager.destroy();
  }, []); // monta/desmonta apenas com o componente

  const active = mode === "MANUAL";

  return (
    <div className="rounded-lg bg-slate-800 p-4">
      <h2 className="font-semibold mb-2">
        Joystick
        {!active && (
          <span className="text-slate-500 text-xs ml-2">inativo fora de MANUAL</span>
        )}
      </h2>
      <div
        ref={zoneRef}
        className={`relative h-44 rounded-lg transition-opacity ${
          active ? "bg-slate-700" : "bg-slate-700 opacity-40 pointer-events-none"
        }`}
        style={{ touchAction: "none" }}
      />
    </div>
  );
}
