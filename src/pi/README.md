# Empilhadeira — Backend Pi (Python)

Backend assíncrono (FastAPI + asyncio) que roda no Raspberry Pi. Recebe comandos do
frontend via WebSocket, detecta AprilTag via câmera, controla o ESP32 via UART serial,
e envia telemetria de volta ao frontend a 20 Hz.

## Arquitetura

Três tarefas asyncio concorrentes compartilham `SharedState`:

- **WebSocket Handler** — recebe comandos (contrato 1), aplica máquina de estados,
  gera setpoints via cinemática/navegação, envia telemetria (contrato 2).
- **Vision Loop** — captura frames, detecta AprilTag (tag25h9), estima pose.
- **Serial Loop** — troca setpoints (contrato 3) e sensores (contrato 4) com o ESP32.

## Estrutura

```
app/
├── main.py              # FastAPI factory + startup das 3 tarefas
├── config.py            # Todos os parâmetros (provisórios marcados)
├── state.py             # Estado compartilhado (locks asyncio)
├── models.py            # Schemas Pydantic dos 4 contratos
├── comms/               # CRC-8/MAXIM + protocolo serial
├── control/             # Cinemática, navegação, estado, Kalman
├── tasks/               # WebSocket, visão, serial
├── telemetry/           # Agregador de telemetria
├── vision/              # Detector AprilTag, estimativa de pose
└── sim/                 # Camada de simulação (SIM=1)
    ├── firmware_emulator.py  # Réplica do firmware ESP32
    ├── world.py              # Mundo físico simulado
    ├── synthetic_vision.py   # Visão sem câmera
    └── fault_injector.py     # Injeção de falhas
```

## Como rodar

```bash
# Instalar dependências
cd src && pip install -e ".[dev]"

# Modo simulação (sem hardware)
SIM=1 uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --app-dir pi

# Modo real (com hardware)
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --app-dir pi

# Testes
pytest pi/tests/ -v

# Lint + formato
ruff check pi/
black --check pi/
```

## Modo Simulação (SIM=1)

Com `SIM=1`, o backend substitui:
- UART serial → emulador do firmware ESP32 (PID, motor, encoder, MPU, garfo)
- Câmera → visão sintética baseada na geometria robô-tag

O resto do código (controle, navegação, estado, telemetria) é **idêntico** ao modo real.

APIs de simulação (só disponíveis com SIM=1):
- `POST /sim/reset-pose` — define pose do robô `{x, y, theta}`
- `POST /sim/inject-fault` — injeta falhas `{fault_type, active}`
- `GET /sim/world-state` — estado completo do mundo simulado

## Parâmetros Provisórios

Todos marcados com `# PROVISÓRIO — TODO(equipe): confirmar` em `config.py`:

| Parâmetro | Valor provisório | Unidade | Observação |
|-----------|-----------------|---------|------------|
| `WHEEL_BASE_L_CM` | 15.0 | cm | Distância entre rodas |
| `WHEEL_RADIUS_R_CM` | 2.8 | cm | Raio da roda Lego NXT |
| `MAX_LINEAR_SPEED` | 30.0 | cm/s | Velocidade máxima |
| `MAX_ANGULAR_SPEED` | 3.0 | rad/s | Velocidade angular máxima |
| `NAV_KZ` | 0.5 | — | Ganho de aproximação |
| `NAV_KX` | 2.0 | — | Ganho lateral |
| `NAV_KP_PITCH` | 0.5 | — | Ganho de pitch |
| `ZREF_CM` | 5.0 | cm | Distância de parada |
| `APRILTAG_SIZE_CM` | 5.0 | cm | Tamanho físico da tag |
| `PALLET_MASS_KG` | 0.1 | kg | Inconsistência 1kg vs 0.1kg |
| `CAMERA_TO_FORK_OFFSET_CM` | (0,0,0) | cm | Offset câmera→garfo |
| `COMMAND_WATCHDOG_MS` | 500 | ms | Timeout de comando |
