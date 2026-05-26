// Joystick.jsx — Joystick virtual (nipplejs) para o modo MANUAL.
//
// Captura (x, y) em [-1, 1] e envia no Command (contrato 1). So tem efeito em
// MANUAL. [ref: Secao 1 e 6 da AGENTS.md]
//
// Fase de scaffolding: apenas placeholder visual; sem nipplejs montado.
export default function Joystick() {
  // TODO: montar nipplejs, mapear movimento -> {x, y} e propagar via sendCommand.
  return (
    <div className="rounded-lg bg-slate-800 p-4">
      <h2 className="font-semibold mb-2">Joystick (MANUAL)</h2>
      <div className="h-40 rounded-full bg-slate-700 flex items-center justify-center text-slate-400">
        TODO: joystick virtual (nipplejs)
      </div>
    </div>
  );
}
