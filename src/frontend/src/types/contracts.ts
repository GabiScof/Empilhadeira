/**
 * contracts.ts — Espelho TypeScript dos 4 contratos de interface.
 *
 * Fonte unica de verdade: docs/serial-protocol.md. Deve casar com
 * pi/app/models.py (Pydantic) e firmware/src/protocol.h (C++).
 *
 * Convencoes: rad/s (rodas), graus (angulos), cm (distancias), A (corrente),
 * ms (timestamp). [ref: Secao 6 da AGENTS.md]
 */

export type Mode = "MANUAL" | "AUTOMATICO" | "PARADO";
export type ForkCommand = "subir" | "descer" | "parar";

// (1) Frontend -> Pi · comando (WebSocket)
export interface Joystick {
  x: number; // [-1, 1] — giro (omega)
  y: number; // [-1, 1] — avanco (v)
}

export interface Command {
  modo: Mode;
  joystick: Joystick; // so vale em MANUAL
  garfo: ForkCommand;
  ts_ms: number; // timestamp do cliente
}

// (2) Pi -> Frontend · telemetria @20Hz (WebSocket)
export interface WheelSpeeds {
  esq: number; // rad/s (medido)
  dir: number; // rad/s (medido)
}

export interface ImuAngles {
  roll: number; // graus (Kalman)
  pitch: number; // graus (Kalman)
}

export interface VisionState {
  detectado: boolean;
  id: number | null;
  z_cm: number | null;
  x_cm: number | null;
  pitch_deg: number | null;
}

export interface Battery {
  cel: number | null;
  i_a: number | null; // A
  temp_c: number | null; // °C
}

export interface Telemetry {
  estado: Mode;
  rodas: WheelSpeeds;
  imu: ImuAngles;
  visao: VisionState;
  bateria: Battery;
  ts_ms: number;
}

// (3) Pi -> ESP32 · setpoint (UART) — espelhado aqui por completude do contrato.
export interface Setpoint {
  w_esq: number; // rad/s (alvo)
  w_dir: number; // rad/s (alvo)
  garfo: ForkCommand;
}

// (4) ESP32 -> Pi · sensores (UART) — espelhado aqui por completude do contrato.
export interface MpuRaw {
  ax: number;
  ay: number;
  az: number; // m/s² (cru)
  gx: number;
  gy: number;
  gz: number; // graus/s (cru)
  temp_c: number; // °C
}

export interface Sensors {
  enc: WheelSpeeds;
  mpu: MpuRaw;
  bms: Battery | null;
}
