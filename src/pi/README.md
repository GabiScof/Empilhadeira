# Empilhadeira — Backend Pi (Python)

## Arquitetura — 4 tarefas asyncio

Todas compartilham `SharedState` (`app/state.py`):

| Tarefa | Arquivo | Taxa | Função |
|--------|---------|------|--------|
| WebSocket Handler | `tasks/websocket_handler.py` | evento | Comandos do operador, telemetria |
| Vision Loop | `tasks/vision_loop.py` | ~20 Hz | AprilTag → EKF |
| Serial Loop | `tasks/serial_loop.py` | 20 Hz | Setpoint ↔ sensores (ESP32 ou emulador) |
| Control Loop | `tasks/control_loop.py` | 20 Hz | Missão/navegação → setpoint |

O Control Loop roda independente do frontend (que envia comandos por evento,
não em stream contínuo). Um único clique em AUTOMATICO basta para navegar.

## Estrutura

```
app/
├── main.py              # FastAPI + lifespan (troca SIM↔real)
├── config.py            # Parâmetros (provisórios marcados TODO(equipe))
├── state.py             # Estado compartilhado
├── models.py            # 4 contratos Pydantic
├── hardware/
│   └── interfaces.py    # VisionSource + SerialTransport (encaixes)
├── comms/
│   ├── protocol.py      # JSON + CRC8
│   └── serial_transport.py  # PySerialTransport (UART real)
├── control/             # EKF, navegação, planejador, missão
├── tasks/               # 4 loops asyncio
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
5. `.env` com `SIM=0`, `SERIAL_PORT`, `MAP`
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
