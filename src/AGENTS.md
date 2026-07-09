# Especificação técnica — Empilhadeira Robótica Autônoma

Lógica implementada e validada em simulação. Interfaces de hardware
(`VisionSource`, `SerialTransport`) prontas. Bring-up no robô real pendente —
ver `docs/hardware-deployment.md`.

---

## 1. Escopo do projeto

Empilhadeira robótica em escala reduzida que transporta pallets (~15 cm de lado;
massa a confirmar — ver Seção 3) em ambiente controlado. Dois modos:

- Manual: operador comanda o robô por joystick virtual no celular.
- Autônomo: o robô detecta uma AprilTag no pallet, estima a pose e se posiciona em
  frente ao alvo. Cobre só o posicionamento do robô, não a manipulação.

O garfo é sempre manual nos dois modos, num canal de comando independente.
Telemetria (velocidades, orientação, distância ao pallet, bateria) volta em tempo
real para o celular.

## 2. Decisões fechadas (não rediscutir, não trocar)

- Arquitetura hierárquica de 3 camadas: Frontend (celular) → Raspberry Pi (alto
  nível) → ESP32 (baixo nível, tempo real).
- Raspberry Pi em Python. Backend assíncrono com FastAPI + `asyncio`:
  3 loops no startup (Vision, Serial, Control) + WebSocket handler por conexão.
- ESP32 em C++ (framework Arduino, build com PlatformIO). PID a ~100 Hz e
  determinismo de tempo real.
- Frontend em React + Vite (roda no navegador do celular).
- Frontend ↔ Pi: WebSocket sobre Wi-Fi local (full-duplex).
- Pi ↔ ESP32: serial UART em USB, 115200 baud, 20 Hz, framing
  JSON + CRC8(hex) + `\n`.
- Monorepo com três apps (`pi/`, `firmware/`, `frontend/`) + `docs/` + `scripts/`.

---

## 3. Parâmetros em aberto — não inventar valores

Estes números ainda não estão definidos pela equipe. Para cada um: constante
nomeada em `config` (ou `platformio.ini` / `.env`), com placeholder claramente
marcado e comentário `# TODO(equipe): confirmar`. Nunca tratar placeholder como
verdade nem otimizar em cima dele.

| Parâmetro | Onde mora | Observação |
|---|---|---|
| Massa real do pallet | `pi/app/config.py` | Intro do relatório diz ~1 kg, mas o cálculo do garfo usou 0,1 kg. Inconsistência aberta. |
| Versão do motor do garfo (torque) | `config` + docs | Depende da massa real; a versão 40 rpm pode estar subdimensionada. |
| Modelo do Raspberry Pi | `docs/architecture.md` | Decide FPS de visão e orçamento de energia. |
| `L` (distância entre rodas), `r` (raio da roda) | `pi/app/config.py` | Usados na cinemática diferencial. |
| Ganhos PID (`Kp, Ki, Kd`) por roda | `firmware/src/config.h` | Sintonia inicial por Ziegler-Nichols, depois empírica. |
| Ganhos da navegação (`Kz, Kx, Kp_pitch`) | `pi/app/config.py` | Modo automático. |
| `Zref` (distância de parada) | `pi/app/config.py` | 15 cm (5 cm causava overshoot); depende do comprimento do garfo. |
| Intrínsecos da câmera (`fx, fy, cx, cy`) | `pi/calibracao/camera_intrinsics.json` | 2ª calibração xadrez OpenCV, 1280×720, fx=fy≈1023,6. |
| Tamanho físico da AprilTag | `config` | Necessário para a pose. |
| Offset extrínseco câmera→garfo | `config` + docs | Alinhar a câmera ≠ alinhar o garfo. |
| Timeout "manter último setpoint" (ESP32) | `firmware/src/config.h` | Antes de cair em estado seguro. |
| Quem é o Access Point Wi-Fi (Pi ou roteador) | `docs/architecture.md` | Afeta o RTT alvo < 170 ms. |

---

## 4. Restrições de engenharia

Notas nos arquivos relevantes; não contradizer:

- A cinemática assume rodas sem escorregamento; odometria por encoder degrada se patinar.
- Estimar Pitch de uma única tag pequena tem ambiguidade de pose conhecida.
- A tag pode sair do FOV / sair de foco na reta final (Z pequeno) — a lógica de
  aproximação precisa lidar com perda de detecção perto do alvo.
- Em modo automático, `ω = Kx·X + Kp·Pitch` pode acoplar/brigar; prever fallback.
- O canal de comando (WebSocket) precisa de watchdog próprio: se cair no modo
  manual com o robô andando, o robô deve parar, não manter o último comando.

---

## 5. Estrutura do monorepo

```
src/
├── README.md
├── AGENTS.md
├── .gitignore
├── .env.example                   # IP do Pi, porta serial, baudrate
├── pyproject.toml                 # workspace Python (ruff, black, pytest)
│
├── docs/                            # 15 documentos — ver tabela na Seção 9
│   ├── architecture.md            # arquitetura, decisões, dock-to-tag, watchdogs
│   ├── serial-protocol.md         # 4 contratos (campos, CRC, watchdogs)
│   ├── navigation.md              # planejador, executor, ganhos, legado
│   ├── mission.md                 # missão pick-and-place, SM, API
│   ├── dock-to-tag.md             # aproximação por segmentos a 1 tag
│   ├── maps.md                    # formato JSON dos mapas
│   ├── simulation.md              # SIM=1, falhas, APIs /sim/*
│   ├── camera-calibration.md      # calibração xadrez
│   ├── hardware-bring-up.md       # pinos, energia, fiação
│   ├── hardware-deployment.md     # deploy no robô real
│   ├── hardware-interfaces.md     # VisionSource, SerialTransport
│   ├── readiness-sim-to-real.md   # auditoria sim→real
│   ├── simulator-to-real.md       # o que o sim cobre
│   ├── real-robot-test-plan.md    # plano de testes hardware
│   └── verification-status.md    # testes, bugs corrigidos
│
├── pi/                            # alto nível — Python
│   ├── README.md
│   ├── app/
│   │   ├── main.py                # FastAPI + lifespan + REST routes (mission, dock, maps)
│   │   ├── config.py              # constantes centrais (Seção 3)
│   │   ├── state.py               # estado compartilhado (SharedState)
│   │   ├── models.py              # Pydantic: 4 contratos + telemetria estendida
│   │   ├── tasks/                 # websocket_handler, vision_loop, serial_loop, control_loop
│   │   ├── vision/                # detector, calibration, pose
│   │   ├── control/               # state_machine, kinematics, navigation, ekf,
│   │   │                          #   path_planner, segment_executor, dock_to_tag,
│   │   │                          #   kalman, gyro_calibration, stanley_nav
│   │   ├── mission/               # mission_sm (SM pick-and-place)
│   │   ├── hardware/              # interfaces (VisionSource, SerialTransport protocols)
│   │   ├── sim/                   # firmware_emulator, synthetic_vision, world, fault_injector
│   │   ├── world/                 # map_schema, world_model, robot_model
│   │   ├── comms/                 # protocol, crc8, serial_transport
│   │   └── telemetry/             # aggregator
│   ├── calibracao/
│   │   └── camera_intrinsics.json
│   └── tests/
│
├── firmware/                      # baixo nível — C++ (Arduino) no ESP32
│   ├── platformio.ini             # board = esp32dev; lib_deps = ArduinoJson
│   ├── README.md
│   └── src/
│       ├── main.cpp               # loop: serial 20Hz + PID 100Hz
│       ├── config.h               # pinos, baudrate, ganhos
│       ├── pid.h / pid.cpp
│       ├── motors.h / motors.cpp  # PWM (LEDC) → L298n
│       ├── encoders.h / encoders.cpp
│       ├── protocol.h / protocol.cpp
│       └── lib/
│
├── frontend/                      # interface — React + Vite
│   ├── package.json               # react, vite, tailwindcss, nipplejs, recharts
│   ├── vite.config.js
│   ├── index.html
│   ├── README.md
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── types/contracts.ts     # tipos espelhando os contratos (Seção 6)
│       ├── ws/useWebSocket.js
│       ├── components/            # Joystick, DPad, TelemetryPanel, ForkControl,
│       │                          #   ModeSelector, Arena, DockPanel, MissionPanel,
│       │                          #   SafetyAlert, FaultInjector, MapSelector, etc.
│       └── pages/                 # OperatorPage, DemoPage, MapPage
│
└── scripts/
    ├── run_pi.sh
    └── flash_firmware.sh
```

---

## 6. Contratos de interface (congelados)

Os quatro contratos estão em `docs/serial-protocol.md` e espelhados em
`pi/app/models.py`, `firmware/src/protocol.*` e `frontend/src/types/contracts.ts`.

Convenções fixas:
- Velocidade angular de roda em rad/s (não rpm) em todos os contratos.
- Ângulos em graus. Distâncias em cm. Corrente em A.
- Framing serial: `<json compacto>*<CRC8 em 2 dígitos hex>\n`.

```jsonc
// (1) Frontend → Pi · comando (WebSocket)
{
  "modo": "MANUAL",                   // "MANUAL" | "AUTOMATICO" | "PARADO"
  "joystick": { "x": 0.0, "y": 0.0 }, // float [-1,1]; só vale em MANUAL
  "garfo": "parar",                   // "subir" | "descer" | "parar"
  "ts_ms": 0                          // int, timestamp do cliente
}

// (2) Pi → Frontend · telemetria @20Hz (WebSocket)
// Campos base (sempre presentes):
{
  "estado": "MANUAL",
  "rodas": { "esq": 0.0, "dir": 0.0 },
  "imu": { "roll": 0.0, "pitch": 0.0 },
  "visao": { "detectado": false, "id": null, "z_cm": null, "x_cm": null, "pitch_deg": null },
  "bateria": { "cel": null, "i_a": null, "temp_c": null },
  "ts_ms": 0,
  // Campos estendidos (populados pelo Pi, não pela UART):
  "parado_reason": null,             // string | null (tag_loss, ws_disconnect, etc.)
  "nav_phase": null,                 // string | null (COARSE_ALIGN, APPROACH, etc.)
  "ekf": null,                       // {x, y, theta, cov, ellipse} | null
  "mission": null,                   // {state, pick_id, place_id, ...} | null
  "navigation": null,                // {executor_state, segment_index, ...} | null
  "dock": null,                      // {state, mode, ...} | null
  "detected_tags": [],               // lista de tags detectadas (multi-tag)
  "map_name": null                   // string | null
}

// (3) Pi → ESP32 · setpoint (UART) — depois vira "<json>*CRC\n"
{
  "w_esq": 0.0, "w_dir": 0.0,         // rad/s (alvo)
  "garfo": "parar"                    // "subir" | "descer" | "parar"
}

// (4) ESP32 → Pi · sensores (UART)
{
  "enc": { "esq": 0.0, "dir": 0.0 },             // rad/s (medido)
  "mpu": { "ax": 0.0, "ay": 0.0, "az": 0.0,      // m/s² (cru)
           "gx": 0.0, "gy": 0.0, "gz": 0.0,      // graus/s (cru)
           "temp_c": 0.0 },
  "bms": null                         // mesmo formato de "bateria", ou null
}
```

---

## 7. Especificações de lógica

- Máquina de estados (`control/state_machine.py`): estados MANUAL / AUTOMATICO /
  PARADO. Operador alterna MANUAL↔AUTOMATICO. Condição de segurança → PARADO (rodas
  zeradas). No AUTOMATICO, perder a tag por >5 frames (~250 ms a 20 Hz) → PARADO. Sair
  de PARADO exige ação explícita do operador.
- Cinemática diferencial (`control/kinematics.py`): `ω_esq = (v − ω·L/2)/r`,
  `ω_dir = (v + ω·L/2)/r`. Manual: joystick `(x,y)` → `(v, ω)` com saturação. A saída
  `(ω_esq, ω_dir)` é a mesma interface nos 2 modos.
- Navegação automática (`control/navigation.py`): objetivo `X≈0`, `Pitch≈0`,
  `Z≈Zref`. Abordagem A (primária): `v = Kz·(Z−Zref)`, `ω = Kx·X + Kp·Pitch`.
  Abordagem B (fallback): sequencial alinhar→aproximar→ajuste fino.
- PID por roda (`firmware/pid.*`): `u = Kp·e + Ki·∫e + Kd·de/dt`, malha a ~100 Hz,
  setpoint do Pi a 20 Hz. Se o setpoint não chegar, mantém o último válido por um
  intervalo curto (Seção 3) e depois entra em estado seguro.
- Garfo (`firmware/motors.*`): PWM de duty fixo enquanto o botão estiver
  pressionado; ao soltar, duty 0 (a redução do motor segura a carga).
- AttitudeKalman (`control/kalman.py`): fundir acelerômetro + giroscópio do MPU → roll/pitch
  para telemetria da UI. Heading (θ) é do EKF 2D, não deste filtro.
- GyroCalibrator (`control/gyro_calibration.py`): bias automático + auto-orientação de eixo Z
  no boot (robô parado ~3 s). O yaw calibrado alimenta o EKF.
- Protocolo (`comms/protocol.py`, `firmware/protocol.*`): serializa JSON, anexa
  CRC8 hex e `\n`; na recepção ressincroniza no `\n` e descarta CRC inválido.
- Estado seguro / watchdogs: firmware 200 ms, comando 400 ms, serial-loss 5 frames,
  tag-loss 6 frames, WS disconnect imediato. Latch com acknowledge. Missão e dock
  bypassam tag-loss e auto-acknowledge. Ver `architecture.md` §Estado seguro.

---

## 8. Tech stack

- Pi: Python 3.11+, FastAPI, Uvicorn, asyncio, opencv-python, pupil-apriltags,
  pyserial-asyncio, NumPy, filterpy, Pydantic. Família de tag: `tag25h9`.
- ESP32: C++ / Arduino, PlatformIO (`board = esp32dev`), ArduinoJson, periférico
  LEDC para PWM, `Wire` para I²C, encoder por interrupção.
- Frontend: React + Vite, Tailwind CSS, nipplejs, Recharts, WebSocket nativo.

Não adicionar dependências fora desta lista sem marcar `TODO(equipe)` e justificar.

---

## 9. Documentação

- `README.md` na raiz: escopo, arquitetura em 3 camadas (com diagrama), como subir
  cada app, links para `docs/`.
- `README.md` por app (`pi/`, `firmware/`, `frontend/`): dependências, como rodar,
  o que cada pasta faz.
- `docs/serial-protocol.md`: os 4 contratos da Seção 6, com tabela campo a campo
  (nome, tipo, unidade, faixa, obrigatório?).
- `docs/architecture.md`: arquitetura, decisões fechadas (Seção 2) e parâmetros em
  aberto (Seção 3).
- Docstring de módulo em PT-BR no topo de cada arquivo: o que ele faz.
- Funções expostas com docstring de assinatura (args, retorno, unidades).

---

## 10. Convenções

- Idioma: código (nomes de arquivos, módulos, funções, variáveis, tipos) em
  inglês; comentários, docstrings e documentação em PT-BR.
- Python: formatado com `black`, lint com `ruff`, type hints em tudo.
- C++: `clang-format`; JS/TS: `eslint` + `prettier`.
- Git: uma branch por frente de trabalho; commits no formato
  `tipo(escopo): descrição` (ex.: `feat(pi): scaffold vision loop`).
- Nenhum número mágico: tudo que for parâmetro vai para `config`.
