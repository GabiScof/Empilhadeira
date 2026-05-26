// ForkControl.jsx — Controle do garfo (canal independente, sempre manual).
//
// Botoes "subir"/"descer" enquanto pressionados; ao soltar, "parar". Vale nos dois
// modos. Envia o campo `garfo` do Command (contrato 1). [ref: Secao 1 e 7]
//
// Fase de scaffolding: apenas placeholder visual; sem handlers reais.
export default function ForkControl() {
  // TODO: onPointerDown -> "subir"/"descer"; onPointerUp/Leave -> "parar".
  return (
    <div className="rounded-lg bg-slate-800 p-4">
      <h2 className="font-semibold mb-2">Garfo</h2>
      <div className="flex gap-3">
        <button className="flex-1 rounded bg-slate-700 py-3" type="button">
          Subir
        </button>
        <button className="flex-1 rounded bg-slate-700 py-3" type="button">
          Descer
        </button>
      </div>
    </div>
  );
}
