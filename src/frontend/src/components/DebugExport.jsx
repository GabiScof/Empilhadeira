import { useState, useCallback } from "react";

function flattenObj(obj, prefix = "", out = {}) {
  for (const [k, v] of Object.entries(obj ?? {})) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v !== null && typeof v === "object" && !Array.isArray(v)) {
      flattenObj(v, key, out);
    } else {
      out[key] = v;
    }
  }
  return out;
}

function formatDump(dump, telemetry) {
  const ts = new Date().toISOString();
  const lines = [
    `=== EMPILHADEIRA DEBUG DUMP ===`,
    `Exported: ${ts}`,
    ``,
  ];

  const sections = [
    ["CONFIG", dump.config],
    ["WORLD", dump.world],
    ["EMULATOR (PID/Motors)", dump.emulator],
    ["STATE MACHINE", dump.state_machine],
    ["NAVIGATOR", dump.navigator],
    ["LAST COMMAND", dump.last_command],
    ["LAST VISION", dump.last_vision],
    ["LAST IMU", dump.last_imu],
    ["CURRENT SETPOINT", dump.current_setpoint],
    ["FAULTS", dump.faults],
    ["TELEMETRY (server)", dump.telemetry],
    ["TELEMETRY (frontend live)", telemetry],
  ];

  for (const [title, data] of sections) {
    lines.push(`--- ${title} ---`);
    if (data == null) {
      lines.push("  (null)");
    } else {
      const flat = flattenObj(data);
      for (const [k, v] of Object.entries(flat)) {
        const val = Array.isArray(v)
          ? `[${v.map((x) => (typeof x === "number" ? x.toFixed(4) : x)).join(", ")}]`
          : v;
        lines.push(`  ${k}: ${val}`);
      }
    }
    lines.push("");
  }

  lines.push("--- CSV (key,value) ---");
  const allFlat = flattenObj(dump);
  for (const [k, v] of Object.entries(allFlat)) {
    if (typeof v === "number" || typeof v === "boolean" || typeof v === "string") {
      lines.push(`${k},${v}`);
    }
  }

  return lines.join("\n");
}

export default function DebugExport({ apiBase, telemetry }) {
  const [status, setStatus] = useState(null);

  const handleExport = useCallback(async () => {
    setStatus("loading");
    try {
      const res = await fetch(`${apiBase}/sim/debug-dump`);
      if (!res.ok) {
        setStatus("error");
        return;
      }
      const dump = await res.json();
      const text = formatDump(dump, telemetry);

      const blob = new Blob([text], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `empilhadeira-debug-${Date.now()}.txt`;
      a.click();
      URL.revokeObjectURL(url);

      setStatus("ok");
      setTimeout(() => setStatus(null), 2000);
    } catch {
      setStatus("error");
      setTimeout(() => setStatus(null), 3000);
    }
  }, [apiBase, telemetry]);

  const handleCopy = useCallback(async () => {
    setStatus("loading");
    try {
      const res = await fetch(`${apiBase}/sim/debug-dump`);
      if (!res.ok) {
        setStatus("error");
        return;
      }
      const dump = await res.json();
      const text = formatDump(dump, telemetry);
      await navigator.clipboard.writeText(text);
      setStatus("copied");
      setTimeout(() => setStatus(null), 2000);
    } catch {
      setStatus("error");
      setTimeout(() => setStatus(null), 3000);
    }
  }, [apiBase, telemetry]);

  return (
    <div className="rounded-lg bg-slate-800 p-4 space-y-2">
      <h2 className="font-semibold">Debug Export</h2>
      <p className="text-xs text-slate-400">
        Exporta config, estado do mundo, PID, navegação e telemetria.
      </p>
      <div className="flex gap-2">
        <button
          onClick={handleExport}
          disabled={status === "loading"}
          className="flex-1 px-3 py-2 rounded bg-indigo-700 hover:bg-indigo-600 disabled:opacity-50 text-sm font-medium"
        >
          {status === "loading" ? "..." : "Baixar TXT"}
        </button>
        <button
          onClick={handleCopy}
          disabled={status === "loading"}
          className="flex-1 px-3 py-2 rounded bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-sm font-medium"
        >
          {status === "copied" ? "Copiado!" : "Copiar"}
        </button>
      </div>
      {status === "ok" && (
        <p className="text-xs text-green-400">Arquivo baixado.</p>
      )}
      {status === "error" && (
        <p className="text-xs text-red-400">Erro ao exportar.</p>
      )}
    </div>
  );
}
