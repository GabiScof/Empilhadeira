# Empilhadeira Robótica Autônoma

Empilhadeira robótica em escala reduzida que transporta pallets (~15 cm de lado) em
ambiente controlado, em dois modos:

- **Manual** — operador comanda o robô por joystick virtual no celular.
- **Autônomo** — o robô detecta uma AprilTag no pallet, estima a pose e se posiciona
  em frente ao alvo (apenas **posicionamento**, não manipulação).

O **garfo é sempre manual** nos dois modos, num canal de comando independente.

> ⚠️ **Estado atual: scaffolding.** Estrutura, contratos congelados, documentação e
> stubs tipados. **Nenhuma lógica de domínio implementada** (PID, Kalman, visão,
> cinemática, navegação, CRC8, máquina de estados são `NotImplementedError`/`// TODO`).

## Arquitetura — 3 camadas

```
┌──────────────────────────────────────────────────────┐
│  Frontend (celular) — React + Vite                    │
│  joystick · telemetria · seletor de modo · garfo      │
└───────────────▲──────────────────────┬────────────────┘
        (2) telemetria @20Hz    (1) comando
            WebSocket / Wi-Fi          ▼
┌───────────────┴────────────────────────────────────────┐
│  Raspberry Pi — Python (FastAPI + asyncio)              │
│  WebSocket Handler · Vision Loop · Serial Loop          │
│  visão (AprilTag) · Kalman · cinemática · navegação     │
└───────────────▲──────────────────────┬─────────────────┘
        (4) sensores            (3) setpoint
        UART USB 115200, 20 Hz · JSON+CRC8+\n
                                       ▼
┌───────────────┴─────────────────────────────────────────┐
│  ESP32 — C++ (Arduino, PlatformIO)                       │
│  PID por roda ~100 Hz · encoders · MPU · PWM(LEDC)→L298n │
└──────────────────────────────────────────────────────────┘
```

Detalhes em [`docs/architecture.md`](docs/architecture.md). Os contratos de dados
entre as camadas são a fonte de verdade em
[`docs/serial-protocol.md`](docs/serial-protocol.md).

## Apps

| Pasta | Camada | Stack | README |
|-------|--------|-------|--------|
| [`pi/`](pi/) | Alto nível (Raspberry Pi) | Python, FastAPI, asyncio | [pi/README.md](pi/README.md) |
| [`firmware/`](firmware/) | Baixo nível (ESP32) | C++ / Arduino, PlatformIO | [firmware/README.md](firmware/README.md) |
| [`frontend/`](frontend/) | Interface (celular) | React + Vite | [frontend/README.md](frontend/README.md) |

## Como subir cada app (dev)

```bash
# Pi (backend)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
./scripts/run_pi.sh

# Firmware (ESP32)
cd firmware && pio run            # compila;  pio run -t upload  para gravar
# ou: ./scripts/flash_firmware.sh

# Frontend (celular)
cd frontend && npm install && npm run dev
```

Copie `.env.example` para `.env` e ajuste IP do Pi / porta serial.

## Documentação

- [`docs/architecture.md`](docs/architecture.md) — arquitetura, decisões fechadas, parâmetros em aberto.
- [`docs/serial-protocol.md`](docs/serial-protocol.md) — **fonte de verdade** dos 4 contratos.
- [`docs/camera-calibration.md`](docs/camera-calibration.md) — calibração da câmera.
- [`AGENTS.md`](AGENTS.md) — contexto e regras desta fase de scaffolding.

## Parâmetros em aberto

Vários valores ainda **não foram definidos pela equipe** (massa do pallet, `L`/`r`,
ganhos PID e de navegação, `Zref`, intrínsecos da câmera, tamanho da tag, etc.).
Cada um existe como constante nomeada com placeholder e comentário `TODO(equipe)`.
A lista completa está em [`docs/architecture.md`](docs/architecture.md#parâmetros-em-aberto--não-inventar-valor--ref-seção-3).
