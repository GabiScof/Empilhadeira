// DPad.jsx — Botões de comando PURO para testes de precisão (frente exata,
// ré exata, giro no lugar), sem o ruído da mão no joystick analógico.
//
// Cada botão envia um vetor exato do contrato de joystick:
//   Frente {x:0, y:+s} · Ré {x:0, y:-s} · Gira ⟲ {x:-s, y:0} · Gira ⟳ {x:+s, y:0}
// onde s = escala de velocidade (30/60/100%). x=0 cravado garante ω=0 (reta
// perfeita); y=0 cravado garante v=0 (giro sem transladar) — é o instrumento
// dos testes 2.1/2.4 do real-robot-test-plan.
//
// IMPORTANTE (watchdog): o Pi exige comando novo a cada COMMAND_WATCHDOG_MS
// (400 ms) em MANUAL com rodas girando — o joystick satisfaz isso porque o
// nipplejs emite "move" continuamente. Aqui, enquanto o botão está
// pressionado, REENVIAMOS o mesmo vetor a cada 100 ms (heartbeat); ao soltar
// (ou sair/cancelar/desabilitar), paramos o timer e enviamos {0,0}.

import { useCallback, useEffect, useRef, useState } from "react";

const HEARTBEAT_MS = 100;

const SPEEDS = [
  { label: "30%", value: 0.3 },
  { label: "60%", value: 0.6 },
  { label: "100%", value: 1.0 },
];

const BUTTONS = [
  { key: "fwd", label: "▲ Frente", vec: (s) => ({ x: 0, y: s }) },
  { key: "rev", label: "▼ Ré", vec: (s) => ({ x: 0, y: -s }) },
  { key: "ccw", label: "⟲ Gira", vec: (s) => ({ x: -s, y: 0 }) },
  { key: "cw", label: "⟳ Gira", vec: (s) => ({ x: s, y: 0 }) },
];

export default function DPad({ onMove, disabled }) {
  const [speed, setSpeed] = useState(0.3);
  const [active, setActive] = useState(null);
  const timerRef = useRef(null);
  const onMoveRef = useRef(onMove);
  onMoveRef.current = onMove;

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setActive(null);
    onMoveRef.current?.({ x: 0, y: 0 });
  }, []);

  const start = useCallback(
    (btn) => {
      if (timerRef.current) clearInterval(timerRef.current);
      const send = () => onMoveRef.current?.(btn.vec(speedRef.current));
      send();
      timerRef.current = setInterval(send, HEARTBEAT_MS);
      setActive(btn.key);
    },
    [],
  );

  // speed em ref para o heartbeat em andamento acompanhar a troca de escala.
  const speedRef = useRef(speed);
  speedRef.current = speed;

  // Desabilitado no meio de um press (troca de modo, queda de conexão): solta.
  useEffect(() => {
    if (disabled && timerRef.current) stop();
  }, [disabled, stop]);

  // Unmount: para o timer (sem enviar — o socket pode já ter ido embora).
  useEffect(
    () => () => {
      if (timerRef.current) clearInterval(timerRef.current);
    },
    [],
  );

  const btnClass = (key) =>
    "select-none rounded-lg py-4 text-lg font-semibold transition-colors " +
    (disabled
      ? "bg-slate-700 text-slate-500"
      : active === key
        ? "bg-blue-500 text-white"
        : "bg-slate-600 hover:bg-slate-500 active:bg-blue-500");

  return (
    <div className="rounded-lg bg-slate-800 p-4">
      <div className="flex items-center justify-between mb-2">
        <h2 className="font-semibold">
          Comando exato{" "}
          {disabled && <span className="text-slate-500">(inativo)</span>}
        </h2>
        <div className="flex gap-1">
          {SPEEDS.map((s) => (
            <button
              key={s.label}
              onClick={() => setSpeed(s.value)}
              disabled={disabled}
              className={
                "text-xs px-2 py-1 rounded " +
                (speed === s.value
                  ? "bg-blue-600 text-white"
                  : "bg-slate-700 text-slate-300 hover:bg-slate-600")
              }
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>
      <div
        className="grid grid-cols-2 gap-2"
        style={{ touchAction: "none" }}
      >
        {BUTTONS.map((btn) => (
          <button
            key={btn.key}
            disabled={disabled}
            className={btnClass(btn.key)}
            onPointerDown={(e) => {
              e.preventDefault();
              if (!disabled) start(btn);
            }}
            onPointerUp={stop}
            onPointerLeave={() => active === btn.key && stop()}
            onPointerCancel={stop}
            onContextMenu={(e) => e.preventDefault()}
          >
            {btn.label}
          </button>
        ))}
      </div>
      <p className="text-xs text-slate-400 mt-2">
        Segure para mover; solte para parar. Frente/Ré = reta pura (ω=0);
        Gira = giro no lugar (v=0). Use p/ os testes de retidão (2.1) e
        odometria (2.4).
      </p>
    </div>
  );
}
