# Referência Completa — Entradas, Saídas e Interfaces de Cada Módulo

> **Data:** 2026-06-23  
> **Escopo:** documentação exaustiva de cada módulo do sistema, com entradas/saídas
> precisas, justificativa de cada interface, o que o simulador cobre hoje, e o que
> precisa ser feito/definido para o hardware real.

---

## Sumário

1. [Visão geral da arquitetura](#1-visão-geral-da-arquitetura)
2. [Os 4 contratos de dados](#2-os-4-contratos-de-dados)
3. [Camada 1 — Frontend (React)](#3-camada-1--frontend-react)
4. [Camada 2 — Raspberry Pi (Python)](#4-camada-2--raspberry-pi-python)
   - 4.1 [Orquestração (`main.py`)](#41-orquestração--mainpy)
   - 4.2 [Estado compartilhado (`state.py`)](#42-estado-compartilhado--statepy)
   - 4.3 [Modelos de dados (`models.py`)](#43-modelos-de-dados--modelspy)
   - 4.4 [Configuração (`config.py`)](#44-configuração--configpy)
   - 4.5 [WebSocket Handler](#45-websocket-handler)
   - 4.6 [Vision Loop](#46-vision-loop)
   - 4.7 [Serial Loop](#47-serial-loop)
   - 4.8 [Control Loop](#48-control-loop)
   - 4.9 [Cinemática (`kinematics.py`)](#49-cinemática--kinematicspy)
   - 4.10 [Navegação reativa (`navigation.py`)](#410-navegação-reativa--navigationpy)
   - 4.11 [Máquina de estados (`state_machine.py`)](#411-máquina-de-estados--state_machinepy)
   - 4.12 [EKF 2D (`ekf.py`)](#412-ekf-2d--ekfpy)
   - 4.13 [Kalman IMU (`kalman.py`)](#413-kalman-imu--kalmanpy)
   - 4.14 [Planejador de rotas (`path_planner.py`)](#414-planejador-de-rotas--path_plannerpy)
   - 4.15 [Executor de segmentos (`segment_executor.py`)](#415-executor-de-segmentos--segment_executorpy)
   - 4.16 [Missão pick-and-place (`mission_sm.py`)](#416-missão-pick-and-place--mission_smpy)
   - 4.17 [Modelo de mundo (`world_model.py`)](#417-modelo-de-mundo--world_modelpy)
   - 4.18 [Modelo do robô (`robot_model.py`)](#418-modelo-do-robô--robot_modelpy)
   - 4.19 [Schema de mapas (`map_schema.py`)](#419-schema-de-mapas--map_schemapy)
   - 4.20 [Visão — detector, calibração, pose](#420-visão--detector-calibração-pose)
   - 4.21 [Comunicação serial — protocolo e CRC](#421-comunicação-serial--protocolo-e-crc)
   - 4.22 [Transporte serial (`serial_transport.py`)](#422-transporte-serial--serial_transportpy)
   - 4.23 [Telemetria (`aggregator.py`)](#423-telemetria--aggregatorpy)
5. [Camada 3 — ESP32 (Firmware C++)](#5-camada-3--esp32-firmware-c)
6. [Interfaces de abstração SIM↔Real](#6-interfaces-de-abstração-simreal)
7. [Simulação — o que temos hoje](#7-simulação--o-que-temos-hoje)
8. [Hardware real — o que falta fazer/definir](#8-hardware-real--o-que-falta-fazerdefinir)
9. [Fluxos de dados ponta a ponta](#9-fluxos-de-dados-ponta-a-ponta)

---

## 1. Visão geral da arquitetura

Três camadas hierárquicas, cada uma com responsabilidades bem definidas:

```
┌─────────────────────────────────────────────────────────────────────┐
│  FRONTEND — Celular (React + Vite, navegador)                       │
│  Joystick · seletor de modo · garfo · telemetria · arena · missão   │
└───────────────▲───────────────────────────┬─────────────────────────┘
                │ Contrato (2)              │ Contrato (1)
                │ Telemetria @20Hz          │ Comando (evento)
                │ WebSocket JSON            ▼ WebSocket JSON
┌───────────────┴─────────────────────────────────────────────────────┐
│  RASPBERRY PI — Alto nível (Python, FastAPI + asyncio)               │
│  4 tarefas concorrentes:                                             │
│   • WebSocket Handler   • Vision Loop                                │
│   • Serial Loop         • Control Loop                               │
│  EKF 2D · Kalman IMU · Cinemática · Navegação · Planejador · Missão  │
└───────────────▲───────────────────────────┬──────────────────────────┘
                │ Contrato (4)              │ Contrato (3)
                │ Sensores                  │ Setpoint
                │ UART 115200 JSON+CRC8+\n  ▼ UART 115200 JSON+CRC8+\n
┌───────────────┴─────────────────────────────────────────────────────┐
│  ESP32 — Baixo nível, tempo real (C++ / Arduino, PlatformIO)         │
│  PID por roda @100Hz · Encoder ISR · MPU-6050 I²C · PWM→L298n       │
│  Garfo manual + fim-de-curso local · Watchdog de setpoint            │
└──────────────────────────────────────────────────────────────────────┘
```

**Por que 3 camadas?**

| Decisão | Justificativa |
|---------|---------------|
| Frontend separado no celular | Interface acessível sem monitor/teclado; Wi-Fi basta |
| Pi para alto nível | Python permite prototipação rápida de visão (OpenCV), filtros (NumPy), e lógica assíncrona (FastAPI/asyncio) |
| ESP32 para baixo nível | PID a 100 Hz exige determinismo de tempo real que Python não garante; ISR de encoder precisa de acesso direto a GPIO |
| Separar PID (ESP) de navegação (Pi) | Malha em cascata: a externa (Pi @20Hz) produz setpoints; a interna (ESP @100Hz) rastreia velocidade. Evita duplicar PID. |

**Por que essas tecnologias?**

| Escolha | Alternativa descartada | Razão |
|---------|------------------------|-------|
| FastAPI + asyncio | Flask, Django | Precisa de WebSocket nativo + tarefas concorrentes sem threads |
| WebSocket (não HTTP polling) | REST polling | Full-duplex, latência <50ms, sem overhead de connection por mensagem |
| UART JSON+CRC8 (não binário) | Protobuf, MessagePack | Depurável com terminal serial; CRC8 é suficiente a 115200 baud |
| React + Vite | Flutter, nativo | Roda em qualquer celular com navegador; sem necessidade de instalar app |
| PlatformIO Arduino | ESP-IDF puro | Ecossistema mais acessível para a equipe; Wire/LEDC prontos |

---

## 2. Os 4 contratos de dados

Fonte de verdade: [`serial-protocol.md`](./serial-protocol.md). Espelhados em 3 linguagens.

### Contrato (1) — Frontend → Pi (WebSocket, sem CRC)

**Direção:** comando do operador  
**Transporte:** WebSocket JSON, disparado por evento (joystick move, botão pressionado)  
**Por que WebSocket?** Full-duplex sobre Wi-Fi, sem overhead de HTTP por mensagem.

```json
{
  "modo": "MANUAL",
  "joystick": { "x": 0.0, "y": 0.0 },
  "garfo": "parar",
  "ts_ms": 1719147600000
}
```

| Campo | Tipo | Faixa | Unidade | Obrigatório | Descrição |
|-------|------|-------|---------|-------------|-----------|
| `modo` | enum | `"MANUAL"` \| `"AUTOMATICO"` \| `"PARADO"` | — | sim | Modo desejado pelo operador |
| `joystick.x` | float | [-1, 1] | adimensional | sim | Giro (ω) — só vale em MANUAL |
| `joystick.y` | float | [-1, 1] | adimensional | sim | Avanço (v) — só vale em MANUAL |
| `garfo` | enum | `"subir"` \| `"descer"` \| `"parar"` | — | sim | Comando do garfo — **sempre manual**, funciona em qualquer modo |
| `ts_ms` | int | ≥ 0 | ms | sim | Timestamp do cliente (watchdog no Pi) |

**Onde é produzido:** `useWebSocket.sendCommand()` no frontend  
**Onde é consumido:** `websocket_handler.py` → `state.update_command()`  
**No SIM vs Real:** idêntico  
**No real, definir:** nada — já funciona

### Contrato (2) — Pi → Frontend (WebSocket @20Hz)

**Direção:** telemetria do robô para o operador  
**Transporte:** WebSocket JSON, empurrado pelo Pi a 20 Hz  
**Por que 20Hz?** Suficiente para feedback visual fluido; coincide com taxa de controle.

```json
{
  "estado": "MANUAL",
  "rodas": { "esq": 0.0, "dir": 0.0 },
  "imu": { "roll": 0.0, "pitch": 0.0 },
  "visao": { "detectado": false, "id": null, "z_cm": null, "x_cm": null, "pitch_deg": null },
  "bateria": { "cel": null, "i_a": null, "temp_c": null },
  "ts_ms": 0,
  "parado_reason": null,
  "nav_phase": null,
  "ekf": { "x_m": 0, "y_m": 0, "theta_rad": 0, "theta_deg": 0, "covariance_trace": 0, ... },
  "mission": { "state": "IDLE", "pick_position_id": null, ... },
  "navigation": { "executor_state": "IDLE", "segment_index": 0, ... },
  "detected_tags": [],
  "map_name": null
}
```

| Campo | Tipo | Unidade | Descrição |
|-------|------|---------|-----------|
| `estado` | Mode | — | Estado real da máquina (pode diferir do solicitado) |
| `rodas.esq/dir` | float | rad/s | Velocidade medida dos encoders |
| `imu.roll/pitch` | float | ° (graus) | Ângulos filtrados por Kalman no Pi |
| `visao.detectado` | bool | — | Tag AprilTag detectada no FOV |
| `visao.id` | int \| null | — | ID da AprilTag mais próxima |
| `visao.z_cm` | float \| null | cm | Distância frontal à tag |
| `visao.x_cm` | float \| null | cm | Deslocamento lateral à tag |
| `visao.pitch_deg` | float \| null | ° | Ângulo de pitch relativo à tag |
| `bateria.cel/i_a/temp_c` | float \| null | V/A/°C | BMS (null se indisponível) |
| `ts_ms` | int | ms | Timestamp do Pi |
| `parado_reason` | string \| null | — | `tag_loss`, `command_watchdog`, `ws_disconnect`, `force_stop` |
| `nav_phase` | string \| null | — | `APPROACH`, `FACE`, `RETREAT` (só AUTOMATICO) |
| `ekf.*` | EkfState | m, rad | Pose estimada + covariância + contagem de correções |
| `mission.*` | MissionInfo | — | Estado da missão pick-and-place |
| `navigation.*` | NavigationInfo | — | Progresso do executor de segmentos |
| `detected_tags[]` | DetectedTag[] | m | Tags detectadas com posição no mapa |
| `map_name` | string \| null | — | Nome do mapa carregado |

**Onde é produzido:** `state.snapshot_telemetry()` → `websocket_handler._telemetry_sender()`  
**Onde é consumido:** `useWebSocket` → todos os componentes do frontend  
**No SIM vs Real:** idêntico  
**No real, definir:** nada — já funciona

### Contrato (3) — Pi → ESP32 (UART com framing)

**Direção:** setpoint de velocidade de roda para o PID do ESP  
**Transporte:** UART USB 115200, JSON compacto + CRC8-MAXIM hex + `\n`, enviado a 20 Hz  
**Por que JSON e não binário?** Depurável com `pio device monitor`; overhead de ~80 bytes é aceitável a 115200.  
**Por que CRC8?** Detecção de erro suficiente para frames curtos; poly MAXIM é simples de implementar em C.

```
{"w_esq":1.5,"w_dir":1.5,"garfo":"parar"}*a3\n
```

| Campo | Tipo | Unidade | Descrição |
|-------|------|---------|-----------|
| `w_esq` | float | rad/s | Setpoint velocidade roda esquerda |
| `w_dir` | float | rad/s | Setpoint velocidade roda direita |
| `garfo` | enum | — | `"subir"` \| `"descer"` \| `"parar"` |

**Onde é produzido:** `protocol.encode_setpoint()` chamado no serial loop  
**Onde é consumido:** ESP32 `SetpointFrameDecoder::push()` → `lastSetpoint`  
**No SIM:** `FirmwareEmulator.receive_setpoint_frame(frame)` — mesmo frame binário  
**No real, definir:** nada — código pronto, precisa apenas conectar USB e validar frames

### Contrato (4) — ESP32 → Pi (UART com framing)

**Direção:** leitura de sensores embarcados  
**Transporte:** mesmo framing (JSON + CRC8 + `\n`), enviado a 20 Hz pelo ESP

```json
{"enc":{"esq":0.0,"dir":0.0},"mpu":{"ax":0,"ay":0,"az":-11,"gx":0,"gy":0,"gz":0,"temp_c":25},"bms":null}
```

> Parado, `|az| ≈ 9.8–11`. No nosso chassi o MPU está montado com o eixo z
> para BAIXO, então `az` sai **negativo** (~-11) — normal; o `GyroCalibrator`
> detecta eixo e sinal automaticamente.

| Campo | Tipo | Unidade | Descrição |
|-------|------|---------|-----------|
| `enc.esq/dir` | float | rad/s | Velocidade angular medida por encoder |
| `mpu.ax/ay/az` | float | m/s² | Aceleração crua (sem filtro) |
| `mpu.gx/gy/gz` | float | °/s | Velocidade angular crua |
| `mpu.temp_c` | float | °C | Temperatura do MPU-6050 |
| `bms` | object \| null | V/A/°C | BMS digital (null se não implementado) |

**Onde é produzido:** ESP32 `encodeSensors()` → `Serial.write()`  
**Onde é consumido:** `SensorsFrameDecoder.feed()` → `state.update_sensors()`  
**No SIM:** `FirmwareEmulator.generate_sensors_frame()` — mesmo frame binário  
**No real, definir:**
- Validar que `enc.esq/dir` reportam rad/s corretos (girar roda 1 volta = 2π rad/s × dt)
- Validar escala do MPU (±2g, ±250°/s)
- BMS: `has_bms = false` hoje — implementar leitura analógica se necessário

---

## 3. Camada 1 — Frontend (React)

### Arquitetura do frontend

```
src/frontend/src/
├── main.jsx               ← Entry point, monta <App/>
├── App.jsx                ← Router: / (OperatorPage) e /demo (DemoPage)
├── types/contracts.ts     ← Tipos TypeScript espelhando contratos (referência, não importados em runtime)
├── ws/useWebSocket.js     ← Hook de conexão WebSocket
├── pages/DemoPage.jsx     ← Painel completo de simulação
└── components/
    ├── Joystick.jsx       ← nipplejs: joystick virtual
    ├── ModeSelector.jsx   ← Botões MANUAL/AUTOMATICO/PARADO
    ├── ForkControl.jsx    ← Botões subir/descer/parar garfo
    ├── TelemetryPanel.jsx ← Painel de telemetria com gráficos
    ├── Arena.jsx          ← Canvas 2D da arena (sim)
    ├── SafetyAlert.jsx    ← Alertas de segurança
    ├── FaultInjector.jsx  ← Injeção de falhas (sim)
    ├── DebugExport.jsx    ← Exportação de debug dump
    ├── MapSelector.jsx    ← Seletor de mapas
    └── MissionPanel.jsx   ← Controle de missão
```

### `useWebSocket.js` — Camada de comunicação

| Aspecto | Detalhe |
|---------|---------|
| **Entrada** | URL `ws://host:8000/ws` |
| **Saída (envia)** | JSON do Contrato (1) via `sendCommand(cmd)` |
| **Saída (recebe)** | JSON do Contrato (2) → `setTelemetry(data)` |
| **Reconexão** | Exponential backoff 500ms → 10000ms |
| **Estado exposto** | `{ telemetry, connected, sendCommand }` |
| **Por que hook customizado?** | Encapsula reconexão, parsing, e estado reativo para todos os componentes |
| **No SIM vs Real** | Idêntico — o WebSocket não sabe se atrás tem emulador ou hardware |
| **No real, definir** | O IP do Pi (variável de ambiente `VITE_PI_WS_URL`) e garantir Wi-Fi estável |

### Componentes — Entradas e Saídas

| Componente | Props (ENTRADA) | Dados que LÊ | Ação que ENVIA | Para onde |
|------------|-----------------|--------------|----------------|-----------|
| **`Joystick`** | `onMove`, `disabled` | — | `onMove({x, y})` em [-1,1] | → App → WebSocket (Contrato 1) |
| **`ModeSelector`** | `currentMode`, `onModeChange`, `disabled` | — | `onModeChange("MANUAL"\|"AUTOMATICO"\|"PARADO")` | → App → WebSocket |
| **`ForkControl`** | `onForkCommand` | — | `"subir"` / `"descer"` (pointerdown), `"parar"` (pointerup) | → App → WebSocket |
| **`TelemetryPanel`** | `telemetry`, `connected`, `worldState?` | rodas, imu, visão, EKF, missão, PID (sim) | — (somente leitura) | — |
| **`Arena`** | `worldState`, `telemetry` | robô, tags, trilha, FOV, covariância EKF, path planejado | — (somente leitura, canvas) | — |
| **`SafetyAlert`** | `telemetry` | `estado`, `parado_reason`, `nav_phase` | — (exibe alertas) | — |
| **`FaultInjector`** | `apiBase` | — | `POST /sim/inject-fault` com fault_type e valores | REST → Pi |
| **`DebugExport`** | `apiBase`, `telemetry` | — | `GET /sim/debug-dump` → arquivo .txt | REST → Pi |
| **`MapSelector`** | `apiBase`, `onMapLoaded` | — | `GET /maps/list`, `POST /maps/load/{name}` | REST → Pi |
| **`MissionPanel`** | `apiBase`, `telemetry`, `worldState` | mission state, tags disponíveis | `POST /mission/start\|continue\|reset` | REST → Pi |

**Por que cada componente existe como módulo separado?**

| Componente | Justificativa |
|------------|---------------|
| Joystick | Encapsula nipplejs (lib externa) e normaliza coordenadas para [-1,1] |
| ModeSelector | Isola a lógica de troca de modo com desabilitação quando desconectado |
| ForkControl | O garfo tem ciclo de vida próprio (pointerdown/up) independente do joystick |
| TelemetryPanel | Componente mais complexo — histórico de gráficos com Recharts, modos de exibição |
| Arena | Canvas 2D com rendering manual (não React DOM) — melhor performance a 20Hz |
| SafetyAlert | Acumula histórico de eventos de segurança, independente do ciclo de vida |
| FaultInjector | Só existe no modo SIM; REST não WebSocket (faults são ação pontual) |

### Página de operador (`/`) vs Demo (`/demo`)

| Aspecto | Operador (`App.jsx`) | Demo (`DemoPage.jsx`) |
|---------|---------------------|-----------------------|
| Joystick + Modo + Garfo | ✅ | ✅ |
| TelemetryPanel | ✅ | ✅ |
| SafetyAlert | ✅ | ✅ |
| Arena (canvas 2D) | ❌ | ✅ |
| FaultInjector | ❌ | ✅ |
| MapSelector | ❌ | ✅ |
| MissionPanel | ❌ | ✅ |
| DebugExport | ❌ | ✅ |
| REST polling `/sim/world-state` | ❌ | ✅ cada 200ms |
| **Uso** | Celular do operador (real) | Desktop de desenvolvimento (sim) |

**No SIM vs Real:** A página `/` funciona idêntica; `/demo` usa REST APIs que só existem com `SIM=1`.  
**No real, definir:** A página `/` é suficiente. Se quiser o Arena no real, precisaria de um endpoint equivalente a `/sim/world-state` que exponha a pose EKF — hoje não existe (a info já vem na telemetria WebSocket, mas o Arena espera o formato REST).

---

## 4. Camada 2 — Raspberry Pi (Python)

### 4.1 Orquestração — `main.py`

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/main.py` |
| **Papel** | Ponto de entrada; cria FastAPI, registra rotas, spawna as 4 tarefas no lifespan |
| **Entrada** | Variáveis de ambiente (`.env`) via `config.py` |
| **Saída** | App FastAPI rodando com WebSocket em `WS_HOST:WS_PORT` |

**Decisão de roteamento SIM↔Real (dentro de `lifespan`):**

```python
if config.SIM:
    # Cria SimWorld, FirmwareEmulator, SyntheticVision, FaultInjector
    vision_source = SimVisionSource(state)
    tasks = [serial_loop_sim(state), vision_loop(state, vision_source), control_loop(state)]
else:
    # Tenta abrir câmera real e UART
    vision_source = RealVisionSource()         # OpenCV + pupil-apriltags
    tasks = [serial_loop_real(state), vision_loop(state, vision_source), control_loop(state)]
```

**Rotas HTTP registradas:**

| Rota | Método | Só SIM? | Entrada | Saída |
|------|--------|---------|---------|-------|
| `/ws` | WebSocket | Não | Contrato (1) | Contrato (2) |
| `/maps/list` | GET | Não | — | `["arena_media.json", ...]` |
| `/maps/load/{name}` | POST | Não | nome do mapa | `{ map: {...} }` |
| `/maps/current` | GET | Não | — | `{ name: "..." }` |
| `/mission/start` | POST | Não | `{ pick_id?, place_id? }` | `{ ok: true }` |
| `/mission/continue` | POST | Não | — | `{ ok: true }` |
| `/mission/reset` | POST | Não | — | `{ ok: true }` |
| `/mission/state` | GET | Não | — | MissionSM.to_dict() |
| `/sim/reset-pose` | POST | **Sim** | `{ x, y, theta }` | `{ ok: true }` |
| `/sim/inject-fault` | POST | **Sim** | `{ fault_type, active, value?, value2? }` | `{ ok: true }` |
| `/sim/world-state` | GET | **Sim** | — | estado completo do sim |
| `/sim/debug-dump` | GET | **Sim** | — | dump de depuração |

**No SIM:** todas as rotas disponíveis, incluindo `/sim/*`.  
**No real:** rotas `/sim/*` desabilitadas; missão e mapas funcionam normalmente.  
**No real, definir:** `SIM=0` no `.env`, `SERIAL_PORT`, `CAMERA_INDEX`.

### 4.2 Estado compartilhado — `state.py`

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/state.py` |
| **Papel** | Container único de todo o estado do robô; acessado pelas 4 tarefas via `asyncio.Lock` |
| **Por que um objeto centralizado?** | As 4 tarefas concorrentes precisam trocar dados sem condição de corrida; um lock asyncio resolve sem threads |

**Membros do `SharedState` e quem escreve/lê:**

| Membro | Tipo | Quem ESCREVE | Quem LÊ | Descrição |
|--------|------|-------------|---------|-----------|
| `last_command` | `Command \| None` | WebSocket Handler | Control Loop | Último comando do operador |
| `last_sensors` | `Sensors \| None` | Serial Loop | Control Loop, Telemetria | Últimos dados do ESP32 |
| `last_vision` | `VisionState` | Vision Loop | Control Loop, Telemetria | Visão da tag mais próxima |
| `last_imu` | `ImuAngles` | Serial Loop (Kalman) | Telemetria | Roll/pitch filtrados |
| `current_setpoint` | `Setpoint` | Control Loop | Serial Loop | Setpoint para os motores |
| `ekf` | `PoseEKF` | Serial Loop (predict), Vision Loop (correct) | Control Loop, Telemetria | Pose estimada [x,y,θ] |
| `kalman` | `AttitudeKalman` | Serial Loop | — (saída via `last_imu`) | Filtro de atitude |
| `state_machine` | `StateMachine` | Control Loop | Telemetria | Estado MANUAL/AUTO/PARADO |
| `navigator` | `NavigationController` | Control Loop | — | Navegação reativa legada |
| `mission` | `MissionSM` | Control Loop, REST API | Control Loop, Telemetria | FSM de missão |
| `segment_executor` | `SegmentExecutor` | Control Loop | Telemetria | Executor de rota |
| `planned_path` | `list[Segment]` | Control Loop | Telemetria, Arena | Rota planejada |
| `executed_trail` | `list[(float,float)]` | Serial Loop | Arena | Histórico de poses |
| `detected_tags_cache` | `list[DetectedTag]` | Vision Loop | Telemetria | Tags detectadas para UI |
| `world_model` | `WorldModel \| None` | main.py, REST | Tudo | Mapa carregado |
| `robot_model` | `RobotModel` | init | Cinemática, EKF | Parâmetros mecânicos |

**Métodos de acesso (todos async com lock):**

| Método | Entrada | Saída | Quem chama |
|--------|---------|-------|------------|
| `update_command(cmd)` | `Command` | — | WebSocket Handler |
| `clear_command()` | — | — | WebSocket Handler (disconnect) |
| `update_sensors(sensors)` | `Sensors` | — | Serial Loop |
| `update_vision(vision)` | `VisionState` | — | Vision Loop |
| `update_imu(imu)` | `ImuAngles` | — | Serial Loop |
| `update_setpoint(setpoint)` | `Setpoint` | — | Control Loop |
| `snapshot_telemetry()` | — | `Telemetry` | WebSocket Handler |
| `load_world(world_model)` | `WorldModel` | — | main.py, REST `/maps/load` |

**No SIM vs Real:** o SharedState é idêntico. Sim adiciona refs `sim_emulator`, `sim_world`, `sim_vision` para hot-swap.

### 4.3 Modelos de dados — `models.py`

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/models.py` |
| **Papel** | Definição Pydantic de todos os tipos de dados trocados entre módulos |
| **Por que Pydantic?** | Validação automática, serialização JSON, type hints nativos, compatível com FastAPI |

**Enums:**

| Enum | Valores | Usado em |
|------|---------|----------|
| `Mode` | `MANUAL`, `AUTOMATICO`, `PARADO` | Contrato 1 e 2, StateMachine |
| `ForkCommand` | `SUBIR`, `DESCER`, `PARAR` | Contrato 1 e 3 |

**Modelos por contrato:**

| Modelo | Contrato | Campos-chave |
|--------|----------|--------------|
| `Joystick` | (1) | `x: float`, `y: float` |
| `Command` | (1) | `modo: Mode`, `joystick: Joystick`, `garfo: ForkCommand`, `ts_ms: int` |
| `Setpoint` | (3) | `w_esq: float`, `w_dir: float`, `garfo: ForkCommand` |
| `Encoders` | (4) | `esq: float`, `dir: float` (rad/s) |
| `MpuRaw` | (4) | `ax,ay,az` (m/s²), `gx,gy,gz` (°/s), `temp_c` |
| `Sensors` | (4) | `enc: Encoders`, `mpu: MpuRaw`, `bms: Battery \| None` |
| `WheelSpeeds` | (2) | `esq: float`, `dir: float` (rad/s) |
| `ImuAngles` | (2) | `roll: float`, `pitch: float` (°) |
| `VisionState` | (2) | `detectado: bool`, `id`, `z_cm`, `x_cm`, `pitch_deg` |
| `Battery` | (2)(4) | `cel`, `i_a`, `temp_c` |
| `EkfState` | (2) ext | `x_m`, `y_m`, `theta_rad/deg`, `covariance_trace`, elipse |
| `MissionInfo` | (2) ext | `state`, `pick/place_position_id`, `is_navigating`, `elapsed_s` |
| `NavigationInfo` | (2) ext | `executor_state`, `segment_index`, `total_segments`, `progress` |
| `DetectedTag` | (2) ext | `tag_id`, `position_id`, `x_m`, `y_m`, `quality` |
| `Telemetry` | (2) | Composição de todos os acima |

### 4.4 Configuração — `config.py`

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/config.py` |
| **Papel** | TODAS as constantes nomeadas do sistema — zero números mágicos nos outros módulos |
| **Por que centralizado?** | Trocar parâmetros SIM↔real num único lugar; facilita calibração |

**Grupos de parâmetros e status SIM→Real:**

| Grupo | Constantes | Status | Ação no real |
|-------|-----------|--------|--------------|
| **Modo** | `SIM` (env `SIM=1`) | ✅ | Setar `SIM=0` |
| **Rede** | `WS_HOST`, `WS_PORT`, `TELEMETRY_HZ=20`, `CONTROL_HZ=20` | ✅ | Manter |
| **Serial** | `SERIAL_PORT=/dev/ttyUSB0`, `SERIAL_BAUDRATE=115200`, `SERIAL_HZ=20` | ✅ | Confirmar porta após `ls /dev/tty*` |
| **Cinemática** | `WHEEL_BASE_L_CM=15`, `WHEEL_RADIUS_R_CM=2.7` (medição da equipe 2026-07-06) | ⚠️ Confirmar | Confirmar r por rolagem; medir L |
| **Velocidade** | `MAX_LINEAR_SPEED=19 cm/s` (medido 24 na bancada 2026-07-06, gravado a 80%), `MAX_ANGULAR_SPEED=2.5 rad/s` (derivado; provisório) | ⚠️ | Cronometrar o giro p/ fechar o angular |
| **Navegação legada** | `NAV_KZ`, `NAV_KX`, `NAV_KP_PITCH`, `ZREF_CM=15` | ⚠️ | Re-tunar com dados reais |
| **Visão** | `APRILTAG_FAMILY=tag25h9`, `APRILTAG_SIZE_CM=4`, intrínsecos, `CAMERA_TO_FORK_OFFSET_CM=(0,-14.2,-25.5)`, `CAMERA_TILT_DEG=28.4` | ⚠️ | **Recalibrar câmera** (cx/cy anômalos) e validar offset/tilt medidos (bancada 2026-07-06/07) |
| **EKF** | `EKF_Q_XY`, `EKF_Q_THETA`, `EKF_R_XY`, `EKF_R_THETA`, gate=3 | ⚠️ | Re-tunar com dados reais |
| **Emulador** | `EMU_*` (PID, motor, ruído, arena) | — | Não usado no real |
| **Missão** | `MISSION_SEED`, `TAG_APPROACH_STANDOFF_M=0.15` | ⚠️ | Ajustar standoff conforme comprimento do garfo |
| **Mapas** | `DEFAULT_MAP`, `MAPS_DIR` | ⚠️ | Criar mapa da arena real |

### 4.5 WebSocket Handler

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/tasks/websocket_handler.py` |
| **Papel** | Recebe comandos do frontend, envia telemetria de volta |

```
ENTRADA:  WebSocket JSON → parse → Command (Contrato 1)
SAÍDA:    Telemetry (Contrato 2) → JSON → WebSocket @20Hz
```

| Função | Entrada | Saída | Descrição |
|--------|---------|-------|-----------|
| `websocket_endpoint(ws, state)` | WebSocket frames | — | Aceita conexão, loop de recepção |
| `_telemetry_sender(ws, state)` | `state.snapshot_telemetry()` | JSON @20Hz | Loop de envio periódico |

**Comportamento de segurança:**
- Se o frontend desconecta → `state.state_machine.force_stop("ws_disconnect")` + `state.clear_command()`
- Se recebe modo `PARADO` após latch → `state.state_machine.acknowledge()`

**No SIM vs Real:** idêntico.  
**No real, definir:** estabilidade do Wi-Fi (AP Pi ou roteador); meta RTT < 170ms.

### 4.6 Vision Loop

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/tasks/vision_loop.py` |
| **Papel** | Adquire imagens, detecta AprilTags, alimenta EKF com correções |

```
ENTRADA:  VisionSource.get_vision() → VisionState (tag mais próxima)
          VisionSource.get_all_detections() → list[TagObservation] (multi-tag)
SAÍDA:    state.update_vision(vision)
          ekf.correct_apriltag(x, y, theta) para cada tag resolvida contra o mapa
          state.detected_tags_cache atualizado
```

**Fluxo detalhado (cada tick @20Hz):**

```
1. source.get_vision() → VisionState (legado, tag mais próxima)
2. source.get_all_detections() → [TagObservation(tag_id, z_m, x_m, yaw_rad, quality)]
3. Para cada detecção:
   a. Resolve tag_id → position_id no WorldModel
   b. Calcula pose do robô no mundo a partir da pose relativa + pose da tag no mapa
   c. ekf.correct_apriltag(observed_x, observed_y, observed_theta, quality)
      → aceita se Mahalanobis ≤ 3σ, rejeita se outlier
   d. Preenche detected_tags_cache com posição no mapa + quality
4. state.update_vision(vision)
```

**Interface `VisionSource` (protocol):**

```python
class VisionSource(Protocol):
    def get_vision(self) -> VisionState: ...
    def get_all_detections(self) -> list[TagObservation]: ...
```

| Implementação | Classe | Fonte dos dados | Onde fica |
|---------------|--------|-----------------|-----------|
| **SIM** | `SimVisionSource` | `SyntheticVision.compute_legacy()` e `.compute_all()` usando pose do SimWorld | `tasks/vision_loop.py` |
| **REAL** | `RealVisionSource` | OpenCV `VideoCapture` → `AprilTagDetector.detect()` → `pose.estimate_*()` | `tasks/vision_loop.py` |

**Por que essa interface?** Desacopla a fonte de imagem da lógica de EKF. A mesma `vision_loop` roda com visão sintética ou câmera real sem mudar uma linha.

**No SIM:** `SyntheticVision` calcula geometria exata + ruído configurável (blur, drop, range).  
**No real, definir:**
1. **Recalibrar câmera** → `camera_intrinsics.json` (a calibração atual está suspeita: cx/cy anômalos). O `vision_loop` força a resolução de captura para o `image_size` do JSON de calibração — capturar em resolução diferente invalida fx/fy/cx/cy
2. **Conferir `APRILTAG_SIZE_CM`** (atual 4 cm) com paquímetro
3. **Validar `CAMERA_TO_FORK_OFFSET_CM`** — medido na bancada 2026-07-07: (0, -14.2, -25.5); z negativo (lente atrás da ponta do garfo)
4. **Validar convenção `yaw_rad`** em `pose.py` — o pitch do PnP vira yaw no plano; precisa validar com câmera real

### 4.7 Serial Loop

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/tasks/serial_loop.py` |
| **Papel** | Envia setpoints para ESP32, recebe sensores, alimenta Kalman e EKF |

```
ENTRADA:  state.current_setpoint (escrito pelo Control Loop)
SAÍDA:    state.update_sensors(sensors)
          state.update_imu(kalman.update(mpu, dt))  → roll/pitch filtrados
          ekf.predict(w_esq, w_dir, gyro_z, dt)     → pose predita
          state.executed_trail.append((ekf.x, ekf.y))
```

**Duas implementações:**

| Função | Modo | Transporte | Descrição |
|--------|------|-----------|-----------|
| `serial_loop_sim(state)` | SIM | `FirmwareEmulator` in-process | Encode setpoint → emulador.step() → decode sensors |
| `serial_loop_real(state, transport?)` | REAL | `PySerialTransport` (UART USB) | Encode setpoint → USB → decode sensors |

**Fluxo detalhado (cada tick @20Hz):**

```
1. Lê state.current_setpoint sob lock
2. Codifica com protocol.encode_setpoint() → frame bytes
3. SIM: emulator.receive_setpoint_frame(frame) + emulator.step(dt)
        + emulator.generate_sensors_frame() → frame bytes
   REAL: transport.send_setpoint(setpoint)
        + transport.read_sensors(timeout) → list[Sensors]
4. Decodifica sensors
5. state.kalman.update(sensors.mpu, dt) → ImuAngles → state.update_imu()
6. ekf.predict(enc.esq, enc.dir, mpu.gz (em rad/s), dt, wheel_radius_m, wheelbase_m)
7. state.update_sensors(sensors)
8. state.executed_trail.append((ekf.x, ekf.y))
```

**Interface `SerialTransport` (protocol):**

```python
class SerialTransport(Protocol):
    async def open(self): ...
    async def send_setpoint(self, setpoint: Setpoint): ...
    async def read_sensors(self, timeout_s: float) -> list[Sensors]: ...
    async def close(self): ...
```

**Por que essa interface?** Desacopla transporte físico da lógica de loop. Em testes, injeta-se um fake transport.

**No SIM:** usa `FirmwareEmulator` que emula PID, motor, encoder, MPU dentro do Python.  
**No real, definir:**
1. Porta serial: `SERIAL_PORT=/dev/ttyUSB0` (ou `/dev/ttyACM0` dependendo do chip USB-UART)
2. Permissão: adicionar usuário ao grupo `dialout`
3. Validar que frames fluem a 20Hz em ambas as direções

### 4.8 Control Loop

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/tasks/control_loop.py` |
| **Papel** | Decisão central: transforma comando do operador ou objetivo de missão em setpoint de velocidade de roda |

```
ENTRADA:  state.last_command (do WebSocket Handler)
          state.last_vision (do Vision Loop)
          state.ekf.x, .y, .theta (do Serial Loop)
          state.mission.state (FSM de missão)
SAÍDA:    state.update_setpoint(Setpoint) → vai para Serial Loop → ESP32
```

**Fluxo por modo (cada tick @20Hz):**

```
1. Lê command, vision sob lock
2. Determina modo de controle:
   ┌─ MANUAL:
   │   joystick_to_twist(x, y) → (v, ω)
   │   twist_to_wheel_speeds(v, ω) → (w_esq, w_dir)
   │
   ├─ AUTOMATICO + missão ativa:
   │   mission.get_current_target() → (goal_x, goal_y, goal_heading)
   │   Se rota não planejada: plan_route(ekf_pose, goal, world_model) → segments
   │   segment_executor.step(ekf.x, ekf.y, ekf.theta, dt) → (w_esq, w_dir)
   │   Se executor ROUTE_DONE: mission.notify_route_done()
   │
   └─ AUTOMATICO sem missão (legado):
       navigator.compute(z_cm, x_cm, pitch_deg) → (v, ω)
       twist_to_wheel_speeds(v, ω) → (w_esq, w_dir)

3. state_machine.step(modo, vision, garfo, ts_ms, w_esq, w_dir)
   → pode zerar motores se segurança disparar
   → retorna (modo_efetivo, w_esq_final, w_dir_final, garfo_final)

4. Check watchdog no MANUAL: se >400ms sem comando → force_stop("command_watchdog")

5. state.update_setpoint(Setpoint(w_esq_final, w_dir_final, garfo_final))
```

**No SIM vs Real:** IDÊNTICO. Este módulo não sabe e não precisa saber se há emulador ou hardware.  
**No real, definir:** re-tunar os ganhos `NAV_K_DIST`, `NAV_K_HEADING` e ganhos do navigator legado com o robô no chão.

### 4.9 Cinemática — `kinematics.py`

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/control/kinematics.py` |
| **Papel** | Conversão entre joystick ↔ velocidades ↔ velocidades de roda |

| Função | Entrada | Saída | Fórmula |
|--------|---------|-------|---------|
| `joystick_to_twist(x, y)` | x∈[-1,1], y∈[-1,1] | `(v, ω)` cm/s, rad/s | `v = y × MAX_V`, `ω = -x × MAX_ω`, com saturação (sinal corrigido 2026-07-06: ω positivo = anti-horário/esquerda, então joystick à DIREITA gera ω negativo — antes virava para o lado errado) |
| `twist_to_wheel_speeds(v, ω)` | v cm/s, ω rad/s | `(w_esq, w_dir)` rad/s | `w = (v ± ω·L/2) / r` |
| `wheel_speeds_to_twist(w_esq, w_dir)` | w_esq, w_dir rad/s | `(v, ω)` cm/s, rad/s | Inversa |

**Depende de:** `WHEEL_BASE_L_CM` (L), `WHEEL_RADIUS_R_CM` (r), `MAX_LINEAR_SPEED`, `MAX_ANGULAR_SPEED`  
**No real, definir:** medir L e r com precisão; se errados, o robô curva mais/menos que o esperado.

### 4.10 Navegação reativa — `navigation.py`

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/control/navigation.py` |
| **Papel** | Controlador de aproximação a uma AprilTag visível (modo AUTOMATICO legado) |
| **Por que "legado"?** | Funciona sem mapa, corrigindo em tempo real pela visão; substituído por missão+planejador para navegação por mapa |

```
ENTRADA:  z_cm, x_cm, pitch_deg (da VisionState)
SAÍDA:    (v, ω) cm/s, rad/s → depois convertidos em wheel speeds pela cinemática
```

**Classe `NavigationController` — 3 fases:**

| Fase | Condição | Comportamento |
|------|----------|---------------|
| `APPROACH` | z > Zref | `v = Kz·(z - Zref)` com desaceleração e saturação; `ω = Kx·X + Kp·pitch` |
| `FACE` | z ≈ Zref, pitch alto | Para, gira no lugar para alinhar pitch → 0 |
| `RETREAT` | z < Zref (muito perto) | Recua devagar até z ≈ Zref, depois volta a APPROACH |

**Características implementadas:**
- Proteção contra oscilação omega (detecção de trocas de sinal)
- Guard de FOV: reduz velocidade perto da borda do campo de visão
- Fallback com retreat quando detecta "preso" (z baixo + omega oscilando)
- Perfil de desaceleração suave antes de Zref

**Parâmetros (em `config.py`):**

| Parâmetro | Valor sim | Descrição |
|-----------|-----------|-----------|
| `NAV_KZ` | ~0.5 | Ganho proporcional em z |
| `NAV_KX` | ~0.02 | Ganho proporcional lateral |
| `NAV_KP_PITCH` | ~0.01 | Ganho de pitch |
| `ZREF_CM` | 15 | Distância de parada |
| `TAG_LOST_FRAMES` | 5 | Frames sem tag → PARADO |

**No real, definir:** re-tunar todos os ganhos; `ZREF_CM` depende do comprimento físico do garfo.

### 4.11 Máquina de estados — `state_machine.py`

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/control/state_machine.py` |
| **Papel** | Garante segurança e controla transições de modo |

```
ENTRADA:  modo solicitado, vision (detectado?), garfo, timestamp, wheel speeds
SAÍDA:    (modo efetivo, w_esq, w_dir, garfo) — pode zerar motores
```

**Diagrama de estados:**

```
    ┌──────────┐     ┌──────────────┐     ┌─────────┐
    │  MANUAL  │◄───►│  AUTOMATICO  │────►│ PARADO  │
    │          │     │              │     │ (latch) │
    └────┬─────┘     └──────┬───────┘     └────┬────┘
         │                  │                   │
         └──────────────────┴───────────────────┘
                    force_stop()
                  (qualquer → PARADO)
```

**Transições de segurança:**

| Gatilho | De | Para | Latch? |
|---------|----|----|--------|
| Comando do operador | MANUAL | AUTOMATICO | Não |
| Perda de tag >5 frames (legado) | AUTOMATICO | PARADO | Sim |
| Watchdog comando >400ms | MANUAL | PARADO | Sim |
| WebSocket desconecta | Qualquer | PARADO | Sim |
| `force_stop(reason)` | Qualquer | PARADO | Sim |

**Latch:** se `safety_latched=True`, sair de PARADO exige `acknowledge()` explícito (operador clica em modo).

**No SIM vs Real:** idêntico. A máquina de estados não sabe a fonte dos dados.  
**No real, definir:** validar que `COMMAND_WATCHDOG_MS=400` é adequado para o RTT do Wi-Fi.

### 4.12 EKF 2D — `ekf.py`

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/control/ekf.py` |
| **Papel** | Filtro de Kalman estendido para localização 2D: estima [x, y, θ] no plano |
| **Por que EKF e não GPS?** | Arena indoor sem GPS; AprilTags são os "satélites" do robô |

```
ENTRADA (predict):  w_esq, w_dir (rad/s), gyro_z (rad/s), dt (s)
                    wheel_radius_m, wheelbase_m
ENTRADA (correct):  observed_x (m), observed_y (m), observed_theta (rad), quality
SAÍDA:              state = [x, y, θ] em metros/radianos
                    covariance 3×3
```

**Predição (chamada no Serial Loop @20Hz):**

```
v = (w_esq + w_dir) / 2 × wheel_radius
ω = (w_dir - w_esq) / wheelbase × wheel_radius
ω_fused = alpha × gyro_z + (1-alpha) × ω_odom     ← fusão giroscópio+odometria

x += v × cos(θ) × dt
y += v × sin(θ) × dt
θ += ω_fused × dt

P = F × P × Fᵀ + Q     ← propagação de covariância
```

**Correção (chamada no Vision Loop @20Hz, por tag detectada):**

```
innovation = [obs_x - x, obs_y - y, normalize(obs_θ - θ)]
S = H × P × Hᵀ + R
mahalanobis = √(innovationᵀ × S⁻¹ × innovation)

Se mahalanobis ≤ GATE (3):
    K = P × Hᵀ × S⁻¹
    state += K × innovation
    P = (I - K × H) × P
    → aceita correção
Senão:
    → rejeita outlier (blur, detecção errada)
```

**Parâmetros (em `config.py`):**

| Parâmetro | Valor sim | Significado |
|-----------|-----------|-------------|
| `EKF_Q_XY` | 0.001 | Ruído de processo em x/y (m²) — quão "incerto" é um passo de odometria |
| `EKF_Q_THETA` | 0.002 | Ruído de processo em θ (rad²) |
| `EKF_R_XY` | 0.01 | Ruído de medição tag em x/y (m²) — quão "ruidosa" é a detecção |
| `EKF_R_THETA` | 0.05 | Ruído de medição tag em θ (rad²) |
| `EKF_MAHALANOBIS_GATE` | 3.0 | Limiar de rejeição de outliers |

**No SIM:** ruídos calibrados para o modelo de ruído sintético (0.2cm posição, 0.05° ângulo).  
**No real, definir:**
1. **Re-calibrar Q e R** com dados reais (gravar log de odometria vs ground truth)
2. **Validar alpha_gyro** (peso do giroscópio vs odometria) — o gyro do MPU-6050 pode ter drift diferente
3. **Gate de Mahalanobis:** 3σ funciona bem se as distribuições forem razoáveis; validar com detecções reais

### 4.13 Kalman IMU — `kalman.py`

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/control/kalman.py` |
| **Papel** | Fusão acelerômetro+giroscópio → roll/pitch estáveis para telemetria |
| **Por que Kalman separado?** | Roll/pitch são para telemetria e segurança (detectar tombamento), não para navegação 2D (que usa EKF com θ=yaw) |

```
ENTRADA:  MpuRaw (ax, ay, az em m/s²; gx, gy em °/s), dt (s)
SAÍDA:    ImuAngles (roll, pitch em graus)
```

**Implementação:** filterpy `KalmanFilter` com estado 4D [roll, pitch, roll_rate, pitch_rate].
- **Medição:** roll/pitch derivados de acelerômetro (atan2)
- **Predição:** integração da taxa angular (giroscópio como entrada)

**No SIM:** MPU sintético do emulador com ruído gaussiano.  
**No real, definir:** ajustar Q/R do Kalman se o MPU-6050 real tiver bias diferente do esperado.

### 4.14 Planejador de rotas — `path_planner.py`

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/control/path_planner.py` |
| **Papel** | Dada a pose atual e um objetivo (x,y,θ), gera uma lista de segmentos (FORWARD / TURN) |

```
ENTRADA:  start_x, start_y, start_heading (m, rad) — do EKF
          goal_x, goal_y, goal_heading (m, rad) — do mapa (tag approach pose)
          world_model (opcional) — para grafo de waypoints
SAÍDA:    list[Segment] — sequência de FORWARD(distância) e TURN(ângulo)
```

**Dois modos de planejamento:**

| Modo | Quando usado | Algoritmo |
|------|-------------|-----------|
| **Grafo (A\*)** | Mapa tem `waypoints` + `edges` | A* no grafo de waypoints → sequência de WPs → waypoints_to_segments |
| **Manhattan** | Mapa sem grafo | Giro alinhado ao eixo → retas → giro final |

**Tipo `Segment`:**

```python
@dataclass
class Segment:
    type: SegmentType       # FORWARD ou TURN
    value: float            # distância (m) ou ângulo (rad)
    target_x: float         # pose alvo deste segmento
    target_y: float
    target_heading: float
```

**No SIM vs Real:** idêntico.  
**No real, definir:** criar o mapa JSON da arena real com waypoints e edges posicionados nas coordenadas reais.

### 4.15 Executor de segmentos — `segment_executor.py`

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/control/segment_executor.py` |
| **Papel** | Executa a rota planejada segmento por segmento, produzindo velocidades de roda |

```
ENTRADA:  x, y, theta (m, rad) — do EKF
          dt (s)
          segments carregados via load_route()
SAÍDA:    (w_left, w_right) rad/s — setpoint para o Serial Loop
```

**Máquina de estados do executor:**

```
IDLE → load_route() → RUNNING → (cada step):
  ├─ FORWARD: P-control em distância e heading ao alvo
  │   erro_dist = distância ao target; erro_heading = ângulo ao target
  │   v = K_DIST × erro_dist (saturado)
  │   ω = K_HEADING × erro_heading (saturado)
  │   Se erro_dist < POS_TOL_M → SEGMENT_DONE → próximo segmento
  │
  ├─ TURN: heading control puro
  │   erro_heading = target_heading - θ
  │   ω = K_HEADING × erro_heading
  │   Se |erro_heading| < HEADING_TOL_RAD → SEGMENT_DONE
  │
  └─ Timeout: >MAX_SEGMENT_TIME_S → TIMEOUT (→ MissionSM FAULT)

Último segmento SEGMENT_DONE → ROUTE_DONE
```

**Parâmetros (em `config.py`):**

| Parâmetro | Valor sim | Significado |
|-----------|-----------|-------------|
| `NAV_K_DIST` | 1.5 | Ganho de distância (m/s por m de erro) |
| `NAV_K_HEADING` | 2.5 | Ganho de heading (rad/s por rad de erro) |
| `POS_TOL_M` | ~0.02 | Tolerância de posição |
| `HEADING_TOL_RAD` | ~0.05 | Tolerância de heading |
| `MAX_SEGMENT_TIME_S` | 30 | Timeout por segmento |

**No real, definir:** re-tunar `K_DIST`, `K_HEADING`; o robô real pode precisar de ganhos menores para evitar overshoot com inércia.

### 4.16 Missão pick-and-place — `mission_sm.py`

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/mission/mission_sm.py` |
| **Papel** | Máquina de estados de missão completa: pick → place → home |
| **Por que separada da StateMachine?** | Hierarquia: StateMachine gerencia MANUAL/AUTO/PARADO; MissionSM gerencia a sequência de navegação dentro de AUTOMATICO |

```
ENTRADA:  start_mission(world, pick_id?, place_id?) — via REST API
          operator_continue() — via REST API (operador terminou o garfo)
          notify_route_done() — do Control Loop (executor chegou ao alvo)
SAÍDA:    get_current_target() → (x, y, heading) — alvo atual para o planejador
          state, is_navigating, is_waiting_operator — para telemetria
```

**Diagrama de estados:**

```
IDLE ─── start_mission() ──→ DRAW_TARGETS ──→ GO_TO_PICK
                                                   │
                                          executor done
                                                   ▼
                                              AT_PICK ──── operator_continue() ──→ GO_TO_PLACE
                                                                                       │
                                                                              executor done
                                                                                       ▼
                                                                                  AT_PLACE ── continue() ──→ GO_HOME
                                                                                                                │
                                                                                                       executor done
                                                                                                                ▼
                                                                                                             DONE
                                              ┌──────────┐
                                              │  FAULT   │ ← timeout, erro, ou force_stop
                                              └──────────┘
```

**Por que o operador clica "continuar" manualmente?** O garfo é sempre manual — o robô se posiciona, o operador aciona subir/descer, e depois clica continuar para ir ao próximo destino.

**No SIM vs Real:** idêntico (a missão não sabe como os motores são controlados).  
**No real, definir:**
1. Criar mapa com pelo menos 2 tags (pick e place) + `home_pose`
2. Decidir `MISSION_RESUME_TRIGGER`: botão na UI (atual) ou eventual sensor

### 4.17 Modelo de mundo — `world_model.py`

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/world/world_model.py` |
| **Papel** | Fachada de acesso ao mapa carregado; resolve tags, calcula poses de aproximação |

```
ENTRADA:  ArenaMap (carregado de JSON via load_map())
SAÍDA:    Consultas: tags, waypoints, poses, grafos
```

| Método | Entrada | Saída | Descrição |
|--------|---------|-------|-----------|
| `from_file(path)` | caminho JSON | `WorldModel` | Factory |
| `tag_pose_m_rad(position_id)` | `str` | `(x,y,yaw)` m,rad | Pose de uma tag no mapa |
| `tag_approach_pose_m_rad(id, standoff)` | `str, float` | `(x,y,heading)` | Ponto de parada em frente à tag |
| `resolve_tag_id(april_id, position_id)` | ints | — | Liga ID detectado ao position_id do mapa |
| `get_position_for_tag_id(id)` | int | `str \| None` | Reverse lookup |
| `waypoint_xy(id)` | `str` | `(x,y)` | Coordenada de waypoint |
| `nearest_waypoint(x,y)` | floats | `str` | Waypoint mais próximo |

**No SIM:** 4 mapas de simulação (`corredor_pequeno`, `corredor_6tags`, `arena_media`, `arena_grande_com_grafo`).  
**No real, definir:** criar mapa JSON com coordenadas medidas da arena real (tags, waypoints, dimensões).

### 4.18 Modelo do robô — `robot_model.py`

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/world/robot_model.py` |
| **Papel** | Parâmetros geométricos do robô + cinemática direta diferencial |

```
ENTRADA:  wheel_radius_m, wheelbase_m, encoder_ppr (de config.py)
SAÍDA:    Cinemática direta/inversa em SI
```

| Método | Entrada | Saída | Descrição |
|--------|---------|-------|-----------|
| `forward_kinematics(w_left, w_right)` | rad/s | `(v, ω)` m/s, rad/s | Velocidade linear e angular |
| `inverse_kinematics(v, ω)` | m/s, rad/s | `(w_left, w_right)` rad/s | Velocidade por roda |
| `diff_drive_step(x,y,θ, w_left, w_right, dt)` | pose + speeds + dt | `(x,y,θ)` nova | Integração de pose |
| `rad_per_pulse()` | — | float | Resolução angular por pulso de encoder |

**No SIM:** `WHEELBASE_M=0.15`, `WHEEL_RADIUS_M=0.027`.  
**No real, definir:**
1. **Medir `WHEEL_BASE_L_CM`** — distância entre centros das rodas, com paquímetro
2. **Medir `WHEEL_RADIUS_R_CM`** — raio da roda (não o diâmetro!)
3. **Validar `ENCODER_PPR`** — rodar 1 volta completa e contar pulsos (validado 2026-07-06: ~1440 com a decodificação x4)

### 4.19 Schema de mapas — `map_schema.py`

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/world/map_schema.py` |
| **Papel** | Validação Pydantic de mapas JSON |

**Estrutura do JSON de mapa:**

```json
{
  "name": "arena_media",
  "arena": { "width_m": 1.0, "height_m": 0.6, "origin": "bottom_left" },
  "start_pose": { "x_m": 0.15, "y_m": 0.30, "theta_deg": 0 },
  "home_pose": { "x_m": 0.15, "y_m": 0.30, "theta_deg": 0 },
  "tags": [
    { "position_id": "P1", "x_m": 0.90, "y_m": 0.30, "wall": "east", "yaw_deg": 180 }
  ],
  "waypoints": [
    { "id": "W1", "x_m": 0.50, "y_m": 0.30 }
  ],
  "edges": [["start", "W1"], ["W1", "P1"]],
  "tag_size_m": 0.04,
  "tag_family": "tag25h9"
}
```

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `name` | string | sim | Nome do mapa |
| `arena.width_m/height_m` | float >0 | sim | Dimensões da arena em metros |
| `start_pose` | PoseSpec | sim | Onde o robô começa |
| `home_pose` | PoseSpec | sim | Para onde volta após missão |
| `tags[]` | TagSpec[] | sim (≥1) | Posição e orientação de cada AprilTag |
| `waypoints[]` | WaypointSpec[] | não | Nós do grafo para A* |
| `edges[]` | string[][] | não | Arestas do grafo |
| `tag_size_m` | float | não (default 0.04) | Tamanho físico da tag |

**No real, definir:** criar pelo menos 1 mapa medido da arena real.

### 4.20 Visão — detector, calibração, pose

#### `detector.py` — Detecção de AprilTags

```
ENTRADA:  imagem grayscale (numpy array H×W)
SAÍDA:    lista de detecções com pose PnP (posição, rotação)
```

| Aspecto | Detalhe |
|---------|---------|
| Lib | pupil-apriltags |
| Família | tag25h9 |
| Intrínseccos | fx, fy, cx, cy (da calibração) |
| Tag size | necessário para escala da pose PnP |

**Por que pupil-apriltags?** Implementação C nativa do algoritmo AprilTag 3, com bindings Python; mais rápido que o dt-apriltags.

**No real, definir:** calibrar a câmera → `camera_intrinsics.json`

#### `calibration.py` — Carregamento de intrínsecos

```
ENTRADA:  caminho para camera_intrinsics.json
SAÍDA:    CameraIntrinsics(fx, fy, cx, cy, dist_coeffs, image_size, reprojection_error)
```

**Estado atual:** JSON calibrado (OpenCV, 640×480, erro 0,144 px), mas ⚠️ **recalibração
em andamento** — cx=399/cy=273 são anômalos para 640×480 (cx ≈ 800/2 sugere fotos em
resolução errada). `vision_loop`/`teste_cam` forçam a captura para o `image_size` do JSON.  
**No real, definir:** recalibrar com padrão xadrez (OpenCV `calibrateCamera()` ou 3DF Zephyr):
1. Imprimir tabuleiro 9×6
2. Capturar 20+ fotos em ângulos variados
3. Rodar calibração → salvar JSON

#### `pose.py` — Estimação de pose

```
ENTRADA:  lista de detecções crus do detector (com pose_R, pose_t)
SAÍDA 1:  VisionState (tag mais próxima: z_cm, x_cm, pitch_deg)
SAÍDA 2:  list[TagObservation] (todas as tags: z_m, x_m, yaw_rad, quality)
```

| Função | Entrada | Saída | Uso |
|--------|---------|-------|-----|
| `estimate_vision_state(detections)` | detecções | `VisionState` | Navegação legada |
| `estimate_tag_observations(detections)` | detecções | `list[TagObservation]` | Correção EKF multi-tag |
| `rotation_matrix_to_euler_angles(R)` | 3×3 matrix | `(roll, pitch, yaw)°` | Auxiliar |

**Detalhes importantes:**
- **Tilt da câmera:** `pose.py` rotaciona a pose por `CAMERA_TILT_DEG` (28,4°,
  medido na bancada 2026-07-07) **antes** de extrair z/x/pitch — o `z` do
  contrato é a distância **HORIZONTAL**, não a hipotenusa do eixo óptico.
- **Offset câmera→garfo:** aplica `CAMERA_TO_FORK_OFFSET_CM` (SOMA) em x/z.
  Medido na bancada 2026-07-07: `(0, -14.2, -25.5)` — a lente fica ~25,5 cm
  ATRÁS da ponta do garfo, por isso o z do offset é NEGATIVO. Depois do
  offset, `z_cm` = distância da PONTA DO GARFO até a tag (é a referência do
  `ZREF_CM`/standoff).

**Sinal do x (corrigido 2026-07-06):** o frame óptico OpenCV/AprilTag tem x
positivo = tag à DIREITA, o oposto da convenção do projeto/simulador
(`x_cm`/`x_m` positivo = tag à ESQUERDA). `pose.py` **nega o x na fronteira**
em TODOS os caminhos reais — tanto no `VisionState` (`x_cm`) quanto no
`TagObservation`/EKF (`x_m`); o x refere-se ao CENTRO da tag. Sem a negação a
navegação autônoma viraria para longe da tag. Validar no robô: tag deslocada
à esquerda da câmera → `x_cm` positivo.

**No real, definir:**
1. **`CAMERA_TO_FORK_OFFSET_CM`** — validar o valor medido (tag a 15 cm da ponta do garfo → `z_cm` ≈ 15)
2. **Convenção yaw** — a implementação usa pitch como proxy para yaw no plano (funciona para tag na parede). Validar com câmera real.

### 4.21 Comunicação serial — protocolo e CRC

#### `protocol.py` — Framing JSON+CRC

```
ENTRADA (encode): Setpoint → bytes (Contrato 3 com CRC)
ENTRADA (decode): bytes → Sensors (Contrato 4 verificado)
```

| Função | Entrada | Saída | Descrição |
|--------|---------|-------|-----------|
| `encode_setpoint(setpoint)` | `Setpoint` | `bytes` | `json*crc\n` |
| `decode_sensors(frame)` | `bytes` | `Sensors \| None` | Valida CRC, parse JSON |
| `SensorsFrameDecoder.feed(data)` | `bytes` (stream) | `list[Sensors]` | Incremental: acumula até `\n` |

**Por que framing por `\n`?** Simples, auto-sincronizável, compatível com terminais seriais.  
**Por que CRC8-MAXIM?** Polinômio simples, 1 byte, suficiente para frames de ~80 bytes; MAXIM (Dallas 1-Wire) é amplamente testado.

#### `crc8.py`

```
ENTRADA:  bytes (payload)
SAÍDA:    int 0-255 (CRC) ou string hex 2 chars
```

**Cross-tested:** `test_crc8_cross_check_firmware_algorithm` garante que CRC Python = CRC C++.

### 4.22 Transporte serial — `serial_transport.py`

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/comms/serial_transport.py` |
| **Papel** | Implementação real de `SerialTransport` via pyserial-asyncio |

```
ENTRADA:  Setpoint (via send_setpoint)
SAÍDA:    list[Sensors] (via read_sensors)
```

| Método | Entrada | Saída | Descrição |
|--------|---------|-------|-----------|
| `open()` | — | — | Abre conexão serial_asyncio |
| `send_setpoint(sp)` | `Setpoint` | — | `encode_setpoint(sp)` → write + drain |
| `read_sensors(timeout)` | float | `list[Sensors]` | Lê até 1024 bytes → `SensorsFrameDecoder` |
| `close()` | — | — | Fecha writer |

**No SIM:** NÃO é usado. O emulador opera in-process.  
**No real, definir:**
1. `SERIAL_PORT` correto (normalmente `/dev/ttyUSB0` ou `/dev/ttyACM0`)
2. Permissão: `sudo usermod -a -G dialout $USER`
3. Cabo USB conectado e ESP32 ligado

### 4.23 Telemetria — `aggregator.py`

| Aspecto | Detalhe |
|---------|---------|
| **Arquivo** | `pi/app/telemetry/aggregator.py` |
| **Papel** | Constrói o objeto `Telemetry` a partir dos componentes individuais |

```
ENTRADA:  estado, rodas, imu, visão, bateria, ts_ms, + campos estendidos
SAÍDA:    Telemetry (Contrato 2 completo)
```

**Na prática:** `SharedState.snapshot_telemetry()` faz este trabalho inline; o `aggregator` é uma função auxiliar standalone.

---

## 5. Camada 3 — ESP32 (Firmware C++)

### Visão geral

```
firmware/src/
├── main.cpp         ← setup() + loop() dual-rate
├── config.h         ← Pinos GPIO, ganhos PID, timeouts, LEDC
├── pid.h/cpp        ← Controlador PID por roda
├── motors.h/cpp     ← PWM → L298n, garfo + fim-de-curso
├── encoders.h/cpp   ← ISR quadratura, cálculo ω
└── protocol.h/cpp   ← SetpointFrameDecoder, encodeSensors
```

### Mapa de pinos (`config.h`)

| Função | GPIO | Tipo | Observação |
|--------|------|------|------------|
| Motor esq IN1 | 27 | OUTPUT | L298n #1 canal B (conferido na bancada 2026-07-06: canais A/B trocados na fiação, remapeado por software) |
| Motor esq IN2 | 26 | OUTPUT | L298n #1 canal B |
| Motor esq PWM | 25 | LEDC | Canal 0, 20kHz, 8 bits |
| Motor dir IN1 | 12 | OUTPUT | L298n #1 canal A (strapping — LOW no boot) |
| Motor dir IN2 | 14 | OUTPUT | L298n #1 canal A |
| Motor dir PWM | 13 | LEDC | Canal 1 |
| Garfo IN1 | 18 | OUTPUT | L298n #2 |
| Garfo IN2 | 19 | OUTPUT | L298n #2 |
| Garfo PWM | 5 | LEDC | Canal 2 |
| Fim-curso topo | -1 | — | Desabilitado (chave não montada) |
| Fim-curso base | -1 | — | Desabilitado (chave não montada; GPIO 15 agora é o encoder esq B) |
| Encoder esq A | 23 | INPUT_PULLUP | ISR CHANGE (decodificação x4) — refiado 2026-07-06 |
| Encoder esq B | 15 | INPUT_PULLUP | ISR CHANGE (x4) |
| Encoder dir A | 32 | INPUT_PULLUP | ISR CHANGE (x4) |
| Encoder dir B | 33 | INPUT_PULLUP | ISR CHANGE (x4) |
| I²C SDA | 21 | Wire | MPU-6050 |
| I²C SCL | 22 | Wire | MPU-6050 |

### Loop principal — `main.cpp`

```
setup():
  Serial.begin(115200)
  motorsBegin()           → configura GPIO + LEDC
  encodersBegin()         → ISR nos pinos A dos encoders
  Wire.begin(21, 22)      → I²C para MPU-6050
  MPU wake-up (write 0 to reg 0x6B)

loop() @~máxima velocidade:
  ┌─ UART RX (contínuo):
  │   Para cada byte recebido:
  │     decoder.push(byte, setpoint) → se frame completo: atualiza lastSetpoint
  │
  ├─ WATCHDOG:
  │   Se now - lastSetpointMs > 200ms → motorsStop() + PID reset
  │
  ├─ PID @100Hz (a cada 10ms):
  │   measuredEsq = encoderReadEsq(dt)    → rad/s
  │   measuredDir = encoderReadDir(dt)     → rad/s
  │   pidEsq.setSetpoint(lastSetpoint.w_esq)
  │   pidDir.setSetpoint(lastSetpoint.w_dir)
  │   uEsq = pidEsq.update(measuredEsq, dt)
  │   uDir = pidDir.update(measuredDir, dt)
  │   motorSetWheelEsq(uEsq)
  │   motorSetWheelDir(uDir)
  │   motorSetFork(lastSetpoint.garfo)     → respeita fim-de-curso
  │
  └─ SERIAL TX @20Hz (a cada 50ms):
      readMpu(sensors)      → burst I²C do MPU-6050
      sensors.enc_esq = measuredEsq
      sensors.enc_dir = measuredDir
      sensors.has_bms = false
      n = encodeSensors(sensors, txBuffer, 512)
      Serial.write(txBuffer, n)
```

### PID — `pid.h/cpp`

```
ENTRADA:  setpoint (rad/s), measured (rad/s), dt_s
SAÍDA:    u (unidade arbitrária → mapeada para duty PWM 0-255)
```

| Parâmetro | Valor em `config.h` | Descrição |
|-----------|---------------------|-----------|
| `PID_KP` | 20 | Ganho proporcional |
| `PID_KI` | 5 | Ganho integral |
| `PID_KD` | 1 | Ganho derivativo |
| `PID_INTEGRAL_LIMIT` | 500 | Anti-windup ±500 |

**Fórmula:** `u = Kp × e + Ki × ∫e × dt + Kd × de/dt`

**No real, definir:** sintonizar Kp/Ki/Kd por Ziegler-Nichols:
1. Setar Ki=Kd=0
2. Subir Kp até oscilação sustentada → anotar Ku (ganho crítico) e Tu (período)
3. Kp = 0.6×Ku, Ki = 2×Kp/Tu, Kd = Kp×Tu/8

### Motors — `motors.h/cpp`

```
ENTRADA:  u (float, saída do PID) para rodas; ForkCommand para garfo
SAÍDA:    sinais GPIO (direção) + duty PWM (velocidade)
```

| Função | Entrada | Saída | Lógica |
|--------|---------|-------|--------|
| `motorSetWheelEsq(u)` | float | GPIO + PWM | u>0: IN1=H,IN2=L; u<0: IN1=L,IN2=H; duty=min(\|u\|, 255) |
| `motorSetWheelDir(u)` | float | GPIO + PWM | Idem |
| `motorSetFork(cmd)` | ForkCommand | GPIO + PWM | SUBIR: se não no topo; DESCER: se não na base; duty fixo 220 |
| `motorsStop()` | — | — | Todas as saídas LOW, duty 0 |

**Por que L298n?** Driver H-bridge simples e barato; suporta até 2A por canal; controle bidirecional com 2 pinos de direção + 1 PWM.

**No real, definir:**
1. Verificar que motores giram na direção esperada — **validado 2026-07-06**
   (`MOTOR_ESQ_INV=false`, `MOTOR_DIR_INV=true`; testar sempre UM lado por vez —
   o teste conjunto mascara canais A/B trocados)
2. `FORK_DUTY=220` — subiu de 180 na bancada 2026-07-06/07 para levantar com carga; revalidar com o pallet real

### Encoders — `encoders.h/cpp`

```
ENTRADA:  contagens da ISR (CHANGE nas fases A e B, tabela de transição x4)
SAÍDA:    ω (rad/s) = (contagens / PPR) × 2π / dt
```

| Aspecto | Detalhe |
|---------|---------|
| PPR | 1440 contagens/revolução (NXT: 360 ciclos de quadratura × 4) |
| ISR | CHANGE nas DUAS fases; tabela de transição (decodificação completa x4) — ruído/bounce gera transições que se cancelam |
| Cálculo | ω = (contagem atômica / 1440) × 2π / dt |
| Reset | Contador zerado após leitura |

**No real, definir:**
1. **Validar PPR:** girar roda 1 volta completa → ~1440 contagens (validado 2026-07-06)
2. **Level shifter:** se encoder é 5V e ESP32 é 3.3V, usar level shifter bidirecional

### Protocol — `protocol.h/cpp`

**Mesmo framing do Pi:** `<json>*<crc8_hex>\n`

```
ENTRADA (decode): bytes do UART → Setpoint
SAÍDA (encode):   Sensors → bytes para UART
```

| Função | Entrada | Saída |
|--------|---------|-------|
| `SetpointFrameDecoder::push(byte, sp)` | byte | `true` se frame completo e válido |
| `decodeSetpoint(frame, len, sp)` | bytes | `true` se CRC + JSON + campos válidos |
| `encodeSensors(sensors, buf, size)` | Sensors | nº de bytes escritos |
| `crc8(data, len)` | bytes | uint8_t |

---

## 6. Interfaces de abstração SIM↔Real

Definidas em `pi/app/hardware/interfaces.py`. São os dois pontos de troca:

### Interface `VisionSource`

```python
@runtime_checkable
class VisionSource(Protocol):
    def get_vision(self) -> VisionState: ...
    def get_all_detections(self) -> list[TagObservation]: ...
```

| Implementação | Classe | Fonte dos dados | Arquivo |
|---------------|--------|-----------------|---------|
| **SIM** | `SimVisionSource` | Geometria do `SimWorld` + ruído + FOV | `tasks/vision_loop.py` |
| **REAL** | `RealVisionSource` | `cv2.VideoCapture` → `AprilTagDetector` → `pose.estimate_*` | `tasks/vision_loop.py` |

**`TagObservation` (dados intermediários):**

```python
@dataclass
class TagObservation:
    tag_id: int             # ID da AprilTag detectada
    position_id: str        # ID da posição no mapa (resolvido depois)
    z_m: float              # distância frontal em metros
    x_m: float              # deslocamento lateral em metros
    yaw_rad: float          # orientação relativa em radianos
    quality: float = 1.0    # qualidade da detecção (0-1)
```

### Interface `SerialTransport`

```python
@runtime_checkable
class SerialTransport(Protocol):
    async def open(self): ...
    async def send_setpoint(self, setpoint: Setpoint): ...
    async def read_sensors(self, timeout_s: float) -> list[Sensors]: ...
    async def close(self): ...
```

| Implementação | Classe | Transporte | Arquivo |
|---------------|--------|-----------|---------|
| **SIM** | (emulador inline, não via interface) | In-process Python | `tasks/serial_loop.py` |
| **REAL** | `PySerialTransport` | UART USB via pyserial-asyncio | `comms/serial_transport.py` |

**Por que usar Protocol (e não ABC)?** Structural subtyping: qualquer objeto que tenha os métodos certos satisfaz a interface, sem herança explícita. Facilita testes com fakes.

---

## 7. Simulação — o que temos hoje

### Componentes do simulador

| Componente | Arquivo | O que faz |
|------------|---------|-----------|
| **SimWorld** | `sim/world.py` | Física: diff-drive com slip, clamp na arena, ruído de encoder/gyro |
| **FirmwareEmulator** | `sim/firmware_emulator.py` | PID por roda @100Hz, modelo de motor 1ª ordem, garfo com limites |
| **SyntheticVision** | `sim/synthetic_vision.py` | Calcula detecções a partir da geometria: FOV, range, ruído, multi-tag |
| **FaultInjector** | `sim/fault_injector.py` | Injeção de falhas: serial drop, tag hidden, slip, blur, encoder noise, gyro drift |

### O que o simulador PROVA (confiança alta de que funciona no real)

1. **Arquitetura de 4 loops funciona sem deadlock** — as 4 tarefas asyncio rodam em paralelo sem condição de corrida
2. **Fluxo de dados ponta a ponta:** joystick → cinemática → setpoint → PID → encoder → EKF → telemetria
3. **Máquina de estados é segura:** perda de tag → PARADO latched; watchdog funciona; latch exige acknowledge
4. **Navegação reativa converge:** 9/9 cenários no `sim_sweep` — robô chega a ~15cm da tag com offset lateral ≤2.4cm
5. **Missão completa funciona:** 4 mapas validados, ciclo IDLE→pick→place→home→DONE
6. **EKF funciona:** predição por odometria + correção por tag, gating de Mahalanobis rejeita outliers
7. **Protocolo serial é compatível:** CRC8 cross-tested entre Python e C++
8. **Watchdog serial funciona:** emulador para motores se não recebe setpoint em 200ms
9. **Planejador A* e Manhattan geram rotas válidas** para todos os mapas de teste

### O que o simulador NÃO PROVA (só o hardware pode validar)

| Aspecto | Por que o SIM não basta | O que fazer no real |
|---------|------------------------|---------------------|
| **Câmera real detecta tags** | Iluminação, foco, resolução reais diferem | Testar com tags impressas na distância real |
| **PnP tem precisão real** | SIM usa geometria exata + ruído gaussiano simples | Comparar pose PnP vs medição física |
| **PID real converge** | Modelo de motor 1ª ordem é idealizado | Ziegler-Nichols no chão |
| **Encoders são precisos** | SIM gera ω perfeito + ruído gaussiano | Validar PPR, level shifter, contagem |
| **Garfo segura pallet** | SIM não tem física de carga real | Testar com massa real |
| **EKF com ruído real** | Ruído de patinagem, detecções ruins, reflexos | Gravar log e re-tunar Q/R |
| **Wi-Fi RTT** | SIM roda local | Medir latência com celular real |
| **UART funciona** | SIM é in-process | Conectar USB, validar frames |
| **MPU-6050 funciona** | SIM gera valores sintéticos | Validar escala ±2g, ±250°/s |

### Testes existentes (162 pytest + 11 vitest)

| Categoria | Quantidade | O que testam |
|-----------|-----------|--------------|
| Máquina de estados | 14 | Transições, latch, watchdog |
| Cinemática | 8 | Joystick → twist → rodas |
| Navegação | 25 | APPROACH, FACE, RETREAT, fallback |
| EKF | 10 | Predict, correct, gating, reset |
| Protocolo/CRC | ~10 | Encode/decode, CRC cross-check |
| Path planner | ~8 | A*, Manhattan, segmentos |
| Segment executor | ~10 | FORWARD, TURN, timeout, progress |
| Missão | 10+4 | FSM + integração com mapas |
| Integração sim | ~15 | Sim sweep, full trace |
| Hardware interfaces | ~5 | Fake transport, mock vision |
| Frontend | 11 | WebSocket, componentes |

---

## 8. Hardware real — o que falta fazer/definir

### 8.1 Bloqueante (impede operação autônoma)

| Item | Estado | Ação | Responsável |
|------|--------|------|-------------|
| **Calibração da câmera** | ⚠️ recalibração em andamento — calibrado 640×480 (0,144 px), mas cx/cy anômalos (cx=399 ≈ 800/2) | Recalibrar com padrão xadrez (capturar em 640×480, foco travado) e re-validar z/x | Equipe |
| **Mapa da arena real** | Só mapas de simulação | Medir arena, posição das tags, criar JSON | Equipe |
| **Teste UART Pi↔ESP32** | Nunca executado | Conectar USB, `pio device monitor`, validar frames | Equipe |
| **Teste câmera real** | Nunca executado | Tag visível, detecção OK, z_cm/x_cm plausíveis | Equipe |
| **Compilar firmware** | Não compilado nesta máquina | `cd src/firmware && pio run -t upload` | Equipe |

### 8.2 Necessário mas não bloqueante (funciona com valores provisórios)

| Item | Valor atual (provisório) | Ação | Impacto se não fizer |
|------|--------------------------|------|---------------------|
| `WHEEL_BASE_L_CM` | 15 cm | Medir com paquímetro | Cinemática errada → robô curva demais/pouco |
| `WHEEL_RADIUS_R_CM` | 2.7 cm (medição da equipe 2026-07-06) | Confirmar por rolagem | Velocidade calculada errada |
| `ENCODER_PPR` | 1440 (validado 2026-07-06) | 1 volta ≈ 1440 contagens (x4) | Odometria com escala errada |
| `PID Kp/Ki/Kd` | 20/5/1 | Ziegler-Nichols | Motor oscila ou responde devagar |
| `APRILTAG_SIZE_CM` | 4 cm | Conferir com paquímetro | Escala da pose PnP errada |
| `CAMERA_TO_FORK_OFFSET_CM` | (0, -14.2, -25.5) — medido na bancada 2026-07-07 | Validar (tag a 15 cm da ponta do garfo → z≈15) | Erro sistemático de posicionamento |
| `ZREF_CM` (distância de parada) | 15 cm | Medir comprimento do garfo | Para longe/perto demais |
| `EKF_Q_*`, `EKF_R_*` | Tunados em sim | Gravar log + re-tunar | Filtro diverge ou converge devagar |
| `NAV_K_DIST`, `NAV_K_HEADING` | Tunados em sim | Testar no chão | Robô oscila ou converge devagar |
| `COMMAND_WATCHDOG_MS` | 400 ms | Medir RTT Wi-Fi | Pode parar indevidamente se Wi-Fi lento |
| `TAG_APPROACH_STANDOFF_M` | 0.15 m | Ajustar ao garfo | Robô para longe/perto demais |

### 8.3 Opcional

| Item | Estado | Notas |
|------|--------|-------|
| BMS digital | Firmware retorna `null` | Implementar leitura analógica se quiser monitorar bateria |
| Wi-Fi AP (Pi vs roteador) | Não decidido | Se Pi for AP: hostapd; se roteador externo: basta conectar |
| Teste E2E WebSocket automatizado | Não existe | Para CI/CD futuro |
| Lint ruff | 58 avisos de estilo | Não afeta funcionamento |

### 8.4 Ordem de execução sugerida para o bring-up

```
Fase A — Sem robô:
  1. [x] Código pronto
  2. [ ] pio run → compilar firmware
  3. [ ] pio run -t upload → gravar ESP32

Fase B — Serial only:
  4. [ ] Conectar USB, pio device monitor → ver frames @20Hz
  5. [ ] SIM=0, rodar Pi → "Serial loop (REAL) iniciado"
  6. [ ] Joystick manual no celular → motores giram
  7. [ ] Desconectar USB → motores param <200ms

Fase C — Visão:
  8. [ ] Calibrar câmera → salvar camera_intrinsics.json
  9. [ ] Tag tag25h9 visível → visao.detectado=true na telemetria
  10. [ ] Medir APRILTAG_SIZE_CM, CAMERA_TO_FORK_OFFSET_CM

Fase D — Mecânica + mapa:
  11. [ ] Medir L, r, PPR → atualizar config.py + config.h
  12. [ ] Criar mapa JSON da arena real
  13. [ ] POST /maps/load/arena_real

Fase E — Autonomia:
  14. [ ] AUTOMATICO (1 clique) → robô converge na tag
  15. [ ] Sintonizar PID (Ziegler-Nichols)
  16. [ ] Re-tunar EKF Q/R
  17. [ ] Missão pick-place completa na arena real
```

---

## 9. Fluxos de dados ponta a ponta

### 9.1 Fluxo manual — operador controla o joystick

```
Celular                        Raspberry Pi                          ESP32
─────────                      ─────────────                         ─────
Joystick.onMove({x,y})
  │
  ├─ sendCommand({              WebSocket Handler
  │    modo: "MANUAL",            │
  │    joystick: {x,y},           ├─ parse JSON
  │    garfo: "parar",            ├─ state.update_command(cmd)
  │    ts_ms: now                 │
  │  })                           │
  │                             Control Loop @20Hz
  │                               │
  │                               ├─ joystick_to_twist(x, y) → (v, ω) cm/s, rad/s
  │                               ├─ twist_to_wheel_speeds(v, ω) → (w_esq, w_dir) rad/s
  │                               ├─ state_machine.step(MANUAL, ...)
  │                               │   └─ watchdog: se >400ms sem cmd → PARADO
  │                               └─ state.update_setpoint(Setpoint)
  │                                                                   │
  │                             Serial Loop @20Hz                     │
  │                               ├─ encode_setpoint() → frame       │
  │                               ├─ send via UART ──────────────────►│
  │                               │                                   ├─ decoder.push() → lastSetpoint
  │                               │                                   ├─ PID @100Hz:
  │                               │                                   │   encoder → PID → PWM → motor
  │                               │                                   │   garfo → motorSetFork()
  │                               │                                   └─ Serial TX @20Hz:
  │                               │◄──────────────────────────────────│   MPU + enc → frame
  │                               ├─ decode sensors                   │
  │                               ├─ kalman.update(mpu) → ImuAngles   │
  │                               ├─ ekf.predict(enc, gyro_z, dt)     │
  │                               └─ state.update_sensors()           │
  │                                                                   │
  │                             Vision Loop @20Hz                     │
  │                               ├─ get_vision() → VisionState
  │                               ├─ get_all_detections() → tags
  │                               ├─ para cada tag: ekf.correct_apriltag()
  │                               └─ state.update_vision()
  │
  │◄────────────────────────── _telemetry_sender @20Hz
  │                               └─ state.snapshot_telemetry() → Telemetry JSON
  │
  ├─ setTelemetry(data)
  ├─ TelemetryPanel atualiza
  └─ SafetyAlert verifica
```

### 9.2 Fluxo de missão — navegação autônoma

```
Celular                        Raspberry Pi                          ESP32
─────────                      ─────────────                         ─────
POST /mission/start
  { pick_id: "P1",
    place_id: "P2" }
       │
       ├─ MissionSM.start_mission(world, "P1", "P2")
       │    └─ state → GO_TO_PICK
       │
       │                        Control Loop @20Hz
       │                          │
       │                          ├─ mission.is_navigating = true
       │                          ├─ mission.get_current_target()
       │                          │   → (x_pick, y_pick, heading_pick)
       │                          ├─ plan_route(ekf_pose, target, world)
       │                          │   → [TURN, FORWARD, TURN, FORWARD, ...]
       │                          ├─ segment_executor.load_route(segments)
       │                          ├─ segment_executor.step(ekf.x, ekf.y, ekf.theta, dt)
       │                          │   → (w_left, w_right) rad/s
       │                          └─ state.update_setpoint(Setpoint)
       │                                                              │
       │                        (robô navega, EKF corrige por tags)   │
       │                                                              │
       │                          executor.state → ROUTE_DONE
       │                          mission.notify_route_done()
       │                          state → AT_PICK
       │
       │◄── telemetria: mission.state = "AT_PICK",
       │                mission.is_waiting_operator = true
       │
       │  (operador aciona garfo subir/descer via WebSocket)
       │  (quando terminou:)
       │
POST /mission/continue
       │
       ├─ mission.operator_continue()
       │    └─ state → GO_TO_PLACE
       │
       │  (repete navegação até place)
       │  (executor ROUTE_DONE → AT_PLACE)
       │
POST /mission/continue
       │
       ├─ mission.operator_continue()
       │    └─ state → GO_HOME
       │
       │  (navega até home_pose)
       │  (executor ROUTE_DONE → DONE)
       │
       │◄── telemetria: mission.state = "DONE"
```

### 9.3 Fluxo de segurança — perda de conexão

```
Cenário 1: WebSocket desconecta no MANUAL (celular perde Wi-Fi)
─────────────────────────────────────────────────────────────────
websocket_handler: onclose()
  → state.state_machine.force_stop("ws_disconnect")   → PARADO latched
  → state.clear_command()                              → last_command = None
Control Loop: modo=PARADO → w_esq=0, w_dir=0
Serial Loop: envia Setpoint(0, 0, parar) → ESP32 para motores

Cenário 2: Cabo USB desconecta (Pi perde ESP32)
─────────────────────────────────────────────────
ESP32: sem setpoint por >200ms → motorsStop() + PID reset
Pi: Serial Loop falha ao ler → loga erro, sensores param de atualizar
    (missão pode entrar em FAULT por timeout de segmento)

Cenário 3: Tag perdida por >5 frames no AUTOMATICO legado
──────────────────────────────────────────────────────────
Vision Loop: visao.detectado = false por 5+ ticks
StateMachine.step(): conta frames sem tag → force_stop("tag_loss")
  → PARADO latched
  → motores zerados
Operador: precisa clicar em modo → acknowledge() → sair de PARADO
```

---

## Apêndice A — Tabela resumo de módulos

| Módulo | Arquivo | Entrada principal | Saída principal | Idêntico SIM/Real? |
|--------|---------|-------------------|-----------------|-------------------|
| main.py | `pi/app/main.py` | Config, `.env` | App FastAPI | Não (troca fonte de visão/serial) |
| state.py | `pi/app/state.py` | Escritas das 4 tarefas | Leituras das 4 tarefas | Sim |
| models.py | `pi/app/models.py` | — (definições) | Tipos de dados | Sim |
| config.py | `pi/app/config.py` | `.env`, variáveis de ambiente | Constantes nomeadas | Sim (valores podem diferir) |
| websocket_handler | `tasks/websocket_handler.py` | WebSocket frames (Contrato 1) | Telemetria JSON (Contrato 2) | Sim |
| vision_loop | `tasks/vision_loop.py` | VisionSource | EKF corrections, VisionState | Sim (fonte muda) |
| serial_loop | `tasks/serial_loop.py` | Setpoint | Sensors, EKF predict, IMU | Não (sim vs real transport) |
| control_loop | `tasks/control_loop.py` | Command, Vision, EKF | Setpoint | Sim |
| kinematics | `control/kinematics.py` | Joystick ou twist | Wheel speeds | Sim |
| navigation | `control/navigation.py` | VisionState (z,x,pitch) | (v, ω) | Sim |
| state_machine | `control/state_machine.py` | Modo, visão, timestamps | Modo efetivo + wheels | Sim |
| ekf | `control/ekf.py` | Encoders+gyro (predict); Tags (correct) | [x, y, θ] | Sim |
| kalman | `control/kalman.py` | MpuRaw | ImuAngles (roll, pitch) | Sim |
| path_planner | `control/path_planner.py` | Pose atual + goal + world | list[Segment] | Sim |
| segment_executor | `control/segment_executor.py` | EKF pose + dt | (w_left, w_right) | Sim |
| mission_sm | `mission/mission_sm.py` | REST API + executor events | Target pose + state | Sim |
| world_model | `world/world_model.py` | JSON map | Tag/waypoint queries | Sim |
| robot_model | `world/robot_model.py` | Config (L, r) | Cinemática SI | Sim |
| map_schema | `world/map_schema.py` | JSON | ArenaMap validado | Sim |
| detector | `vision/detector.py` | Imagem grayscale | Detecções AprilTag | Sim (usada só no real) |
| calibration | `vision/calibration.py` | JSON intrínsecos | CameraIntrinsics | Sim (usada só no real) |
| pose | `vision/pose.py` | Detecções | VisionState + TagObservation | Sim (usada só no real) |
| protocol | `comms/protocol.py` | Setpoint/bytes | Bytes/Sensors | Sim |
| crc8 | `comms/crc8.py` | bytes | CRC int/hex | Sim |
| serial_transport | `comms/serial_transport.py` | Setpoint | Sensors via UART | Só real |
| SimWorld | `sim/world.py` | w_esq, w_dir, dt | Pose do robô + sensores ruidosos | Só sim |
| FirmwareEmulator | `sim/firmware_emulator.py` | Frame setpoint | Frame sensors | Só sim |
| SyntheticVision | `sim/synthetic_vision.py` | Pose robô + tags | VisionState + TagDetection | Só sim |
| FaultInjector | `sim/fault_injector.py` | Tipo de falha | Altera sim components | Só sim |
| ESP32 main.cpp | `firmware/src/main.cpp` | Setpoint UART | Sensors UART | Só real |
| ESP32 pid | `firmware/src/pid.cpp` | Setpoint + measured | PWM duty | Só real |
| ESP32 motors | `firmware/src/motors.cpp` | PID output + ForkCmd | GPIO + LEDC | Só real |
| ESP32 encoders | `firmware/src/encoders.cpp` | ISR pulses | ω rad/s | Só real |
| ESP32 protocol | `firmware/src/protocol.cpp` | UART bytes | Setpoint / Sensors frames | Só real |
| Frontend App | `frontend/src/App.jsx` | User events | WebSocket commands | Sim |
| Frontend DemoPage | `frontend/src/pages/DemoPage.jsx` | WS + REST | Arena + faults + mission | Sim |
| useWebSocket | `frontend/src/ws/useWebSocket.js` | URL | {telemetry, connected, send} | Sim |
