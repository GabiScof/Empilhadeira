# Empilhadeira Robótica Autônoma

Empilhadeira em escala reduzida com navegação autônoma por AprilTag, missão
pick-and-place e telemetria em tempo real.

> **Estado atual:** lógica implementada e validada em simulação (`SIM=1`).
> Pronta para bring-up no hardware real — ver
> [`docs/hardware-deployment.md`](docs/hardware-deployment.md).

## Arquitetura — 3 camadas

```
┌──────────────────────────────────────────────────────┐
│  Frontend (celular) — React + Vite                    │
│  joystick · telemetria · missão · mapa · garfo        │
└───────────────▲──────────────────────┬────────────────┘
        (2) telemetria @20Hz    (1) comando
            WebSocket / Wi-Fi          ▼
┌───────────────┴────────────────────────────────────────┐
│  Raspberry Pi — Python (FastAPI + asyncio)              │
│  WebSocket · Vision · Serial · Control Loop (4 tasks)  │
│  EKF 2D · planejador · missão · navegação reativa     │
└───────────────▲──────────────────────┬─────────────────┘
        (4) sensores            (3) setpoint
        UART USB 115200, 20 Hz · JSON+CRC8+\n
                                       ▼
┌───────────────┴─────────────────────────────────────────┐
│  ESP32 — C++ (Arduino, PlatformIO)                       │
│  PID por roda ~100 Hz · encoders · MPU · PWM → L298n    │
└─────────────────────────────────────────────────────────┘
```

Detalhes em [`docs/architecture.md`](docs/architecture.md).

## Apps

| Pasta | Camada | README |
|-------|--------|--------|
| [`pi/`](pi/) | Raspberry Pi (Python) | [pi/README.md](pi/README.md) |
| [`firmware/`](firmware/) | ESP32 (C++) | [firmware/README.md](firmware/README.md) |
| [`frontend/`](frontend/) | Celular (React) | [frontend/README.md](frontend/README.md) |

## Como rodar

```bash
# Instalar
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # ajustar conforme ambiente

# Simulação (sem hardware)
SIM=1 ./scripts/run_pi.sh

# Hardware real
SIM=0 ./scripts/run_pi.sh

# Frontend
cd frontend && npm install && npm run dev

# Testes completos
python3 -m pytest pi/tests/ -v
bash scripts/verify.sh
```

> O pacote `app` vive em `pi/app`. O script `run_pi.sh` já roda de dentro de `pi/`.
> Alternativa manual: `SIM=1 uvicorn app.main:create_app --factory --app-dir pi`.

## Documentação

| Documento | Conteúdo |
|-----------|----------|
| [**readiness-sim-to-real.md**](docs/readiness-sim-to-real.md) | **Auditoria completa** — Pi, ESP, filtros, interfaces, bloqueantes |
| [**simulator-to-real.md**](docs/simulator-to-real.md) | **Sim → real** — o que fizemos, o que aproveitamos |
| [**hardware-deployment.md**](docs/hardware-deployment.md) | **Passo a passo no robô real** — o que fazer, o que falta |
| [verification-status.md](docs/verification-status.md) | Testes passando, bugs corrigidos, sim_sweep |
| [hardware-interfaces.md](docs/hardware-interfaces.md) | Encaixes SIM↔real (`VisionSource`, `SerialTransport`) |
| [hardware-bring-up.md](docs/hardware-bring-up.md) | Pinos, energia, fiação, calibração |
| [serial-protocol.md](docs/serial-protocol.md) | **Fonte de verdade** dos 4 contratos |
| [architecture.md](docs/architecture.md) | Decisões, parâmetros em aberto |
| [navigation.md](docs/navigation.md) | Planejador, executor, APPROACH/FACE/RETREAT |
| [mission.md](docs/mission.md) | Missão pick-and-place |
| [dock-to-tag.md](docs/dock-to-tag.md) | Aproximação por segmentos a 1 tag (opt-in `DOCK_TO_TAG=1`) |
| [maps.md](docs/maps.md) | Formato JSON dos mapas |
| [simulation.md](docs/simulation.md) | Modo SIM=1, falhas, APIs `/sim/*` |
| [camera-calibration.md](docs/camera-calibration.md) | Calibração xadrez |

## Verificação (2026-06-23)

| Check | Resultado |
|-------|-----------|
| pytest | 162/162 |
| frontend vitest | 11/11 |
| sim_sweep | 9/9 convergem |
| full_trace | 12/13 (1 LOST esperado — FOV) |

## Parâmetros em aberto

Valores provisórios em `pi/app/config.py` e `firmware/src/config.h`, marcados
`TODO(equipe)`. Lista completa em
[`docs/architecture.md#parâmetros-em-aberto`](docs/architecture.md#parâmetros-em-aberto--não-inventar-valor--ref-seção-3)
e checklist de medição em [`docs/hardware-deployment.md`](docs/hardware-deployment.md).
