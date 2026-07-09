# Empilhadeira — Backend Pi (Python)

## Arquitetura — 3 loops + WebSocket handler

`main.py` cria 3 `asyncio.create_task` no lifespan: Vision, Serial, Control.
O WebSocket handler roda por conexão (`@app.websocket("/ws")`).
Todas compartilham `SharedState` (`app/state.py`):

| Componente | Arquivo | Taxa | Função |
|------------|---------|------|--------|
| Vision Loop | `tasks/vision_loop.py` | ~20 Hz | AprilTag → EKF correction |
| Serial Loop | `tasks/serial_loop.py` | 20 Hz | Setpoint ↔ sensores, EKF predict, GyroCalibrator, AttitudeKalman |
| Control Loop | `tasks/control_loop.py` | 20 Hz | Arbitragem (manual > missão > dock > legado) → setpoint, segurança |
| WebSocket Handler | `tasks/websocket_handler.py` | por conexão | Comandos, telemetria @20 Hz por cliente |

REST API (também em `main.py`): `/mission/*`, `/dock/*`, `/maps/*`, `/world-state`.
Pi serve `frontend/dist` como estático (modo operação sem Node).

## Estrutura

```
app/
├── main.py              # FastAPI + lifespan (troca SIM↔real)
├── config.py            # Parâmetros (provisórios marcados TODO(equipe))
├── state.py             # Estado compartilhado
├── models.py            # 4 contratos + telemetria estendida (Pydantic)
├── hardware/
│   └── interfaces.py    # VisionSource + SerialTransport (encaixes)
├── comms/
│   ├── protocol.py      # JSON + CRC8
│   └── serial_transport.py  # PySerialTransport (UART real)
├── control/             # EKF, navegação, planejador, segment_executor, dock_to_tag,
│                        #   state_machine, kinematics, kalman, gyro_calibration
├── mission/             # mission_sm (SM pick-and-place)
├── tasks/               # 3 loops asyncio + WS handler
├── vision/              # Detector, pose, calibração
├── world/               # Mapas JSON, robot model
└── sim/                 # Emulador (SIM=1 only)
```

## Como rodar

```bash
cd src && pip install -e ".[dev]"

# Simulação
SIM=1 ./scripts/run_pi.sh

# Hardware real (câmera + serial)
SIM=0 ./scripts/run_pi.sh

# Testes
python3 -m pytest pi/tests/ -v
```

## Modo SIM=1 vs SIM=0

| Componente | SIM=1 | SIM=0 |
|------------|-------|-------|
| Visão | `SimVisionSource` | `RealVisionSource` (OpenCV) |
| Serial | `FirmwareEmulator` | `PySerialTransport` (UART) |
| Control loop, EKF, missão | idêntico | idêntico |

Troca em `app/main.py` → `lifespan()`. Detalhes:
[`docs/hardware-interfaces.md`](../docs/hardware-interfaces.md).

APIs extras em SIM=1: `/sim/reset-pose`, `/sim/inject-fault`, `/sim/world-state`,
`/sim/debug-dump`. Ver [`docs/simulation.md`](../docs/simulation.md).

## Deploy no hardware

Passo a passo completo: [`docs/hardware-deployment.md`](../docs/hardware-deployment.md).

Resumo mínimo:

1. Gravar firmware ESP32 (`firmware/`)
2. Calibrar câmera → `calibracao/camera_intrinsics.json`
3. Medir L, r, PPR → `config.py` + `config.h`
4. Criar mapa JSON da arena → `maps/`
5. `.env` com `SIM=0`, `SERIAL_PORT` (nota: `MAP=` no .env não tem efeito — mapa padrão hardcoded)
6. Smoke tests (joystick → AUTOMATICO → missão)

## Parâmetros provisórios (confirmar no robô)

| Parâmetro | Valor atual | Unidade |
|-----------|-------------|---------|
| `WHEEL_BASE_L_CM` | 15.0 | cm |
| `WHEEL_RADIUS_R_CM` | 2.7 | cm |
| `ZREF_CM` | 15.0 | cm |
| `NAV_KZ` / `NAV_KX` / `NAV_KP_PITCH` | 0.5 / 0.80 / 0.1 | — |
| `NAV_MAX_APPROACH_SPEED` | 15.0 | cm/s |
| `APRILTAG_SIZE_CM` | 4.0 | cm |
| `CAMERA_TO_FORK_OFFSET_CM` | (0.0, -14.2, -10.0) | cm |
| `PALLET_MASS_KG` | 0.1 | kg |

Lista completa em `config.py` (grep `TODO(equipe)`).
