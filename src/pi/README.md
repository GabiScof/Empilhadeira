# App do Raspberry Pi (alto nível)

Backend assíncrono único em **Python** (FastAPI + asyncio) que roda no Raspberry Pi.
É a camada de **alto nível**: visão, fusão de sensores, controle, máquina de estados
e ponte entre o frontend (WebSocket) e o ESP32 (UART).

> ⚠️ **Fase de scaffolding.** Toda a lógica está como stub (`NotImplementedError`).
> Nada de PID/Kalman/cinemática/navegação/CRC implementado ainda.

## Três tarefas concorrentes (asyncio)

- **WebSocket Handler** — recebe comando (contrato 1), envia telemetria @20 Hz
  (contrato 2), watchdog de comando.
- **Vision Loop** — captura, detecta AprilTag (`tag25h9`), estima pose.
- **Serial Loop** — troca setpoint (contrato 3) / sensores (contrato 4) com o ESP32,
  aplica Kalman, watchdog serial.

## Estrutura

```
app/
├── main.py            # cria as 3 tarefas asyncio
├── config.py          # TODAS as constantes/placeholders (Seção 3)
├── state.py           # estado compartilhado entre tarefas
├── models.py          # schemas Pydantic dos 4 contratos
├── tasks/             # websocket_handler, vision_loop, serial_loop
├── vision/            # detector, calibration, pose
├── control/           # state_machine, kinematics, navigation, kalman
├── comms/             # protocol (JSON+CRC8+\n), crc8
└── telemetry/         # aggregator
calibracao/
└── camera_intrinsics.json   # placeholder (fx/fy/cx/cy = null)
tests/                 # test_crc8, test_kinematics, test_protocol (casos marcados)
```

## Dependências

Python 3.11+. Principais libs (ver `pyproject.toml` na raiz):
`fastapi`, `uvicorn`, `opencv-python`, `pupil-apriltags`, `pyserial-asyncio`,
`numpy`, `filterpy`, `pydantic`.

## Como rodar (dev)

```bash
# a partir da raiz do monorepo (src/)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# verificação de import (deve passar mesmo sem lógica)
cd pi && python -c "import app.main, app.models, app.config"

# servidor (quando implementado)
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
# ou: ../scripts/run_pi.sh
```

## Qualidade

```bash
ruff check pi
black --check pi
pytest pi   # testes ainda marcados como skip
```

Configuração de porta/baudrate via `.env` (ver `.env.example` na raiz).
