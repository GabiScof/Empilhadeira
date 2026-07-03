import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import TelemetryPanel from "../components/TelemetryPanel.jsx";

describe("TelemetryPanel", () => {
  it("shows disconnected when not connected", () => {
    render(<TelemetryPanel telemetry={null} connected={false} />);
    expect(screen.getByText("Desconectado")).toBeInTheDocument();
  });

  it("shows connected when connected", () => {
    render(<TelemetryPanel telemetry={null} connected={true} />);
    expect(screen.getByText("Conectado")).toBeInTheDocument();
  });

  it("displays telemetry values", () => {
    const telem = {
      estado: "MANUAL",
      rodas: { esq: 1.23, dir: 4.56 },
      imu: { roll: 0.5, pitch: 1.2 },
      visao: { detectado: true, id: 0, z_cm: 15.3, x_cm: 2.1, pitch_deg: 3.4 },
      bateria: {},
      ts_ms: 0,
    };
    render(<TelemetryPanel telemetry={telem} connected={true} />);
    expect(screen.getByText("MANUAL")).toBeInTheDocument();
  });
});
