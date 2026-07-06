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
  parado_reason: string | null;
  nav_phase: string | null;
}

// ---------------------------------------------------------------------------
// Extensões de telemetria — EKF, missão, navegação
// ---------------------------------------------------------------------------
export interface EkfState {
  x_m: number;
  y_m: number;
  theta_rad: number;
  theta_deg: number;
  covariance_trace: number;
  last_correction: string;
  correction_count: number;
  ellipse_semi_major_m: number;
  ellipse_semi_minor_m: number;
  ellipse_angle_rad: number;
}

export interface MissionInfo {
  state: string;
  pick_position_id: string | null;
  place_position_id: string | null;
  fault_reason: string | null;
  is_navigating: boolean;
  is_waiting_operator: boolean;
  elapsed_s: number;
}

export interface NavigationInfo {
  executor_state: string;
  segment_index: number;
  total_segments: number;
  progress: number;
  current_segment_type: string | null;
}

export interface DockInfo {
  enabled: boolean;
  state: string; // SEEKING | DOCKING | DONE | FAULT
  mode: string; // line_of_sight | tag_normal
  segments: number;
}

export interface DetectedTag {
  tag_id: number;
  position_id: string | null;
  x_m: number;
  y_m: number;
  quality: number;
}

export interface TelemetryExtended extends Telemetry {
  ekf: EkfState | null;
  mission: MissionInfo | null;
  navigation: NavigationInfo | null;
  dock: DockInfo | null;
  detected_tags: DetectedTag[];
  map_name: string | null;
}

export interface MapInfo {
  name: string;
  file: string;
  arena: { width_m: number; height_m: number };
  tags: number;
  has_graph: boolean;
}

export interface WorldState {
  world: {
    robot: { x_m: number; y_m: number; theta_rad: number; theta_deg: number };
    tags: Array<{ position_id: string; x_m: number; y_m: number; yaw_deg: number; april_tag_id: number }>;
    arena: { width_m: number; height_m: number };
    trail: Array<[number, number]>;
  };
  ekf?: EkfState;
  world_model?: {
    name: string;
    tags: Array<{ position_id: string; x_m: number; y_m: number; yaw_deg: number }>;
    has_graph: boolean;
    waypoints?: Array<{ id: string; x_m: number; y_m: number }>;
    edges?: Array<[string, string]>;
    start_pose: { x_m: number; y_m: number; theta_deg: number };
    home_pose: { x_m: number; y_m: number; theta_deg: number };
  };
  mission?: MissionInfo;
  executor?: { state: string; segment_index: number; total_segments: number; progress: number; current_segment?: { type: string; target_x: number; target_y: number } };
  planned_path?: Array<{ type: string; value: number; target_x: number; target_y: number; target_heading: number }>;
  executed_trail?: Array<[number, number]>;
  fork_height?: number;
  fork_at_top?: boolean;
  fork_at_bottom?: boolean;
  faults?: Record<string, any>;
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
