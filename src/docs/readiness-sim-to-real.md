# Prontidão SIM → Real — Auditoria Completa

> **Data da auditoria:** 2026-06-23  
> **Pergunta:** o Pi, o ESP32, a lógica, os filtros e as interfaces de comunicação
> estão prontos para ligar o robô físico com `SIM=0`?  
> **Resposta curta:** o **software está implementado e validado em simulação**; o
> **deploy físico ainda exige calibração e testes no chão** antes de confiar em
> navegação autônoma.

Documentos complementares:
- [`simulator-to-real.md`](./simulator-to-real.md) — o que o sim validou vs o que muda
- [`hardware-deployment.md`](./hardware-deployment.md) — passo a passo no robô
- [`hardware-interfaces.md`](./hardware-interfaces.md) — encaixes `VisionSource` / `SerialTransport`
- [`serial-protocol.md`](./serial-protocol.md) — fonte de verdade dos 4 contratos
- [`verification-status.md`](./verification-status.md) — 162 testes, bugs corrigidos

---

## Veredicto executivo

```
┌─────────────────────────────────────────────────────────────────────────┐
│  CAMADA                    │ CÓDIGO      │ TESTADO SIM │ TESTADO REAL │
├────────────────────────────┼─────────────┼─────────────┼──────────────┤
│  Lógica Pi (controle)      │ ✅ Pronto   │ ✅ 162 testes│ ❌ Pendente  │
│  Filtros (Kalman + EKF)    │ ✅ Pronto   │ ✅ Unitário │ ❌ Pendente  │
│  Visão real (OpenCV+tags)  │ ✅ Pronto   │ ⚠️ Mock     │ ❌ Pendente  │
│  Serial real (UART)        │ ✅ Pronto   │ ⚠️ Fake inj.│ ❌ Pendente  │
│  Firmware ESP32            │ ✅ Pronto   │ ✅ Emulador │ ❌ Pendente  │
│  Frontend ↔ Pi (WebSocket) │ ✅ Pronto   │ ✅ 11 testes│ ⚠️ Wi-Fi     │
│  Contratos (4 JSON)        │ ✅ Alinhados│ ✅ CRC8     │ —            │
│  Calibração câmera         │ ❌ null     │ —           │ ❌ Bloqueante│
│  Mapa arena real           │ ❌ Sim only │ ✅ 4 mapas  │ ❌ Bloqueante│
│  Parâmetros mecânicos      │ ⚠️ Provisório│ ✅ Sim tune│ ❌ Medir     │
└─────────────────────────────────────────────────────────────────────────┘
```

| Status | Significado |
|--------|-------------|
| **Pronto para transição de código** | Pode setar `SIM=0` — o backend sobe e tenta câmera + serial |
| **Pronto para operação autônoma** | Só após calibração, mapa real, smoke tests e sintonia PID |
| **Pronto para competição/demo** | Missão completa validada na arena física |

**Conclusão honesta:** não falta implementar lógica nem interfaces. Falta **executar
o bring-up físico** (calibrar, medir, sintonizar, validar). O simulador provou que o
**design** funciona; o hardware provará que os **números** estão certos.

---

## 1. Arquitetura da transição — onde tudo liga

Único ponto de troca: `lifespan()` em `pi/app/main.py`.

```python
if config.SIM:
    vision_source = SimVisionSource(_state)
    tasks += [serial_loop_sim(_state), vision_loop(_state, vision_source)]
else:
    vision_source = RealVisionSource()      # OpenCV + pupil-apriltags
    tasks += [serial_loop_real(_state), vision_loop(_state, vision_source)]
tasks += [control_loop(_state)]             # IDÊNTICO nos dois modos
```

| Tarefa asyncio | Arquivo | SIM=1 | SIM=0 | Mesmo código? |
|----------------|---------|-------|-------|---------------|
| WebSocket Handler | `tasks/websocket_handler.py` | ✅ | ✅ | **Sim** |
| Control Loop @20 Hz | `tasks/control_loop.py` | ✅ | ✅ | **Sim** |
| Vision Loop | `tasks/vision_loop.py` | SimVisionSource | RealVisionSource | Loop sim; fonte não |
| Serial Loop | `tasks/serial_loop.py` | serial_loop_sim | serial_loop_real | Loop sim; transporte não |

Se câmera ou serial falharem no boot real, a app **não cai** — loga erro e continua
(útil para bring-up parcial: testar serial antes da câmera, etc.).

---

## 2. Raspberry Pi — auditoria módulo a módulo

### 2.1 Entrada e orquestração

| Módulo | Arquivo | Status | Notas |
|--------|---------|--------|-------|
| FastAPI factory | `main.py` | ✅ | Rotas `/ws`, `/maps/*`, `/mission/*`; `/sim/*` só SIM=1 |
| Config central | `config.py` | ⚠️ | Todos parâmetros existem; muitos `TODO(equipe)` provisórios |
| Estado compartilhado | `state.py` | ✅ | Lock asyncio, EKF, missão, setpoint, telemetria |
| Modelos Pydantic | `models.py` | ✅ | 4 contratos + telemetria estendida (EKF, missão, nav) |

### 2.2 Loops de tarefa (runtime)

| Módulo | Arquivo | Status | Testes |
|--------|---------|--------|--------|
| WebSocket | `tasks/websocket_handler.py` | ✅ | Manual ao vivo; sem E2E auto |
| Control Loop | `tasks/control_loop.py` | ✅ | `test_control_loop.py` (4) |
| Vision Loop | `tasks/vision_loop.py` | ✅ | `test_vision_sim.py`; real via mock |
| Serial Loop SIM | `tasks/serial_loop.py` | ✅ | `test_integration_sim.py` |
| Serial Loop REAL | `tasks/serial_loop.py` | ✅ | `test_hardware_interfaces.py` (fake transport) |

**Control Loop — o que faz (idêntico SIM/real):**
- MANUAL: joystick → cinemática → setpoint
- AUTOMATICO + missão: mission SM → path planner → segment executor → setpoint
- AUTOMATICO legado (sem missão): NavigationController → setpoint
- Passa pela máquina de estados + watchdog antes de publicar `current_setpoint`

### 2.3 Controle e navegação

| Módulo | Arquivo | Status | Testes |
|--------|---------|--------|--------|
| Máquina de estados | `control/state_machine.py` | ✅ | 14 testes; latch segurança |
| Cinemática | `control/kinematics.py` | ✅ | 8 testes |
| Navegação reativa | `control/navigation.py` | ✅ | 25 testes; APPROACH/FACE/RETREAT |
| Planejador | `control/path_planner.py` | ✅ | A*, Manhattan |
| Executor segmentos | `control/segment_executor.py` | ✅ | FORWARD, TURN, free angle |
| Missão SM | `mission/mission_sm.py` | ✅ | 10 + 4 integração mapas |

### 2.4 Filtros e estimação

#### Kalman IMU (`control/kalman.py`) — roll/pitch para telemetria

| Aspecto | Detalhe |
|---------|---------|
| **Entrada** | `MpuRaw` do ESP32 (accel m/s², gyro °/s) — **mesmo no sim e real** |
| **Saída** | `ImuAngles` roll/pitch filtrados → telemetria WebSocket |
| **Implementação** | filterpy KalmanFilter, estado [roll, pitch, roll_rate, pitch_rate] |
| **Onde roda** | `serial_loop_*` → `state.kalman.update()` a cada pacote de sensores |
| **Status código** | ✅ Implementado |
| **Calibração** | Q/R fixos em código — ⚠️ pode precisar ajuste no hardware |
| **Uso na navegação** | Roll/pitch vão na telemetria; EKF usa gyro Z para heading |

#### EKF 2D (`control/ekf.py`) — localização no plano

| Aspecto | Detalhe |
|---------|---------|
| **Estado** | [x, y, θ] em metros/radianos + covariância 2×2 |
| **Predição** | Odometria: ω_esq, ω_dir + gyro Z → `ekf.predict()` no serial loop |
| **Correção** | AprilTag: `ekf.correct_apriltag()` no vision loop (multi-tag) |
| **Gating** | Mahalanobis ≤ 3σ — rejeita outliers (blur, detecção ruim) |
| **Parâmetros** | `EKF_Q_*`, `EKF_R_*`, `alpha_gyro=0.7` — ⚠️ `TODO(equipe)` calibrar |
| **Status código** | ✅ Implementado |
| **Testes** | `test_ekf.py` (10), integração missão |

**Fluxo EKF no real (idêntico ao sim):**

```
ESP32 encoders + MPU ──serial──► serial_loop_real ──► ekf.predict()
Câmera AprilTag ──vision──► vision_loop ──► ekf.correct_apriltag()
Control Loop lê ekf.x, ekf.y, ekf.theta para missão/navegação
```

### 2.5 Visão (modo real)

| Módulo | Arquivo | Status | Bloqueante? |
|--------|---------|--------|-------------|
| Detector | `vision/detector.py` | ✅ | pupil-apriltags tag25h9 |
| Calibração | `vision/calibration.py` | ✅ código | ❌ JSON com `null` |
| Pose | `vision/pose.py` | ⚠️ | offset câmera→garfo; yaw TODO |
| RealVisionSource | `tasks/vision_loop.py` | ✅ | Exige calibração se `REQUIRE_CAMERA_CALIBRATION=1` |

**RealVisionSource — comportamento no boot:**
1. Tenta `AprilTagDetector.from_calibration()` → lê `pi/calibracao/camera_intrinsics.json`
2. Se `null` e `REQUIRE_CAMERA_CALIBRATION=1` (padrão) → **RuntimeError claro**
3. Se `REQUIRE_CAMERA_CALIBRATION=0` → usa placeholders (pose imprecisa)
4. Abre `cv2.VideoCapture(CAMERA_INDEX)` — default `/dev/video0`

**Dependências Pi para modo real** (`pyproject.toml`):
- `opencv-python`, `pupil-apriltags`, `pyserial-asyncio`, `numpy`, `filterpy`, `websockets`

### 2.6 Comunicação serial (modo real)

| Módulo | Arquivo | Status | Notas |
|--------|---------|--------|-------|
| Protocolo | `comms/protocol.py` | ✅ | encode/decode + SensorsFrameDecoder |
| CRC8 | `comms/crc8.py` | ✅ | Cross-check com algoritmo firmware |
| Transporte | `comms/serial_transport.py` | ✅ | PySerialTransport — UART USB |
| Interface | `hardware/interfaces.py` | ✅ | Protocol tipado |

**PySerialTransport:**
- Porta: `SERIAL_PORT` (default `/dev/ttyUSB0`)
- Baud: `SERIAL_BAUDRATE` (115200)
- Envia: `encode_setpoint()` @20 Hz
- Recebe: `SensorsFrameDecoder.feed()` — ressincroniza em `\n`, descarta CRC inválido

**Nunca testado:** UART real Pi↔ESP32 no chão. Código pronto; integração física pendente.

### 2.7 Mundo e mapas

| Módulo | Arquivo | Status |
|--------|---------|--------|
| Schema JSON | `world/map_schema.py` | ✅ Validado |
| WorldModel | `world/world_model.py` | ✅ |
| RobotModel | `world/robot_model.py` | ⚠️ L, r provisórios |
| Mapas atuais | `pi/maps/*.json` | ⚠️ Coordenadas da simulação |

Rotas `/maps/list`, `/maps/load/{name}`, `/maps/current` funcionam em **SIM=0**.

---

## 3. ESP32 (firmware) — auditoria completa

### 3.1 Status do código

| Arquivo | Responsabilidade | Status | Espelho no emulador |
|---------|------------------|--------|---------------------|
| `main.cpp` | Loop dual-rate PID 100Hz + serial 20Hz | ✅ | `firmware_emulator.py` |
| `config.h` | Pinos, ganhos, timeouts | ✅ | `config.py` EMU_* |
| `pid.cpp` | PID por roda + anti-windup | ✅ | `PidController` |
| `motors.cpp` | PWM LEDC → L298n, garfo, fim-de-curso | ✅ | MotorModel + fork |
| `encoders.cpp` | ISR quadratura, ω rad/s | ✅ | encoder sintético |
| `protocol.cpp` | JSON+CRC8 encode/decode | ✅ | mesmo framing |
| `protocol.h` | Structs Setpoint, Sensors | ✅ | models.py |

**Não implementado (não bloqueante para operação básica):**
- BMS digital — `has_bms = false`, campo `bms: null` no JSON
- Unidade de `bms.cel` — `TODO(equipe)` (provavelmente V)

### 3.2 Loop principal (`main.cpp`)

```
loop() @ ~loop rate
├── 1. UART RX → SetpointFrameDecoder → lastSetpoint
├── 2. Watchdog: >200ms sem setpoint → motorsStop() + PID reset
├── 3. PID @100Hz: encoder → PID → PWM rodas + garfo
└── 4. Serial @20Hz: MPU-6050 I2C → encodeSensors → UART TX
```

| Feature | Valor | Alinhado com Pi? |
|---------|-------|------------------|
| Baudrate | 115200 | ✅ |
| Taxa serial | 20 Hz | ✅ `SERIAL_HZ` |
| Taxa PID | 100 Hz | ✅ emulador |
| Watchdog | 200 ms | ✅ `SETPOINT_TIMEOUT_MS` |
| MPU escala | ±2g, ±250°/s | ✅ Kalman espera m/s² e °/s |
| Encoders | PPR=360, rad/s | ✅ EKF usa rad/s |

### 3.3 Mapa de pinos (`config.h`)

Documentado em [`hardware-bring-up.md`](./hardware-bring-up.md). Resumo:

| Função | GPIO |
|--------|------|
| Motor esq IN1/IN2/PWM | 16, 17, 4 |
| Motor dir IN1/IN2/PWM | 18, 19, 13 |
| Garfo IN1/IN2/PWM | 25, 26, 27 |
| Encoder esq A/B | 32, 33 |
| Encoder dir A/B | 14, 23 |
| Fim-curso garfo top/bottom | 5, 15 |
| I2C SDA/SCL | 21, 22 |

### 3.4 Compilação

Firmware C++ completo via PlatformIO (`firmware/platformio.ini`). **Não compilado
nesta máquina de dev** (PlatformIO não instalado) — equipe deve rodar:

```bash
cd src/firmware && pio run -t upload
```

---

## 4. Interfaces de comunicação — os 4 contratos

Fonte de verdade: [`serial-protocol.md`](./serial-protocol.md).

### Contrato (1) Frontend → Pi · Comando (WebSocket)

```json
{"modo":"MANUAL","joystick":{"x":0,"y":0},"garfo":"parar","ts_ms":0}
```

| Camada | Implementação | Status |
|--------|---------------|--------|
| TypeScript | `frontend/src/types/contracts.ts` | ✅ |
| Pydantic | `models.py::Command` | ✅ |
| Handler | `websocket_handler.py` | ✅ |
| Watchdog | `COMMAND_WATCHDOG_MS=400` no control loop | ✅ |

**SIM vs Real:** idêntico. Sem CRC (WebSocket garante integridade).

### Contrato (2) Pi → Frontend · Telemetria @20 Hz

```json
{
  "estado":"MANUAL",
  "rodas":{"esq":0,"dir":0},
  "imu":{"roll":0,"pitch":0},
  "visao":{"detectado":false,"id":null,"z_cm":null,"x_cm":null,"pitch_deg":null},
  "bateria":{"cel":null,"i_a":null,"temp_c":null},
  "ts_ms":0,
  "parado_reason":null,
  "nav_phase":null
}
```

Campos estendidos (EKF, missão, tags): presentes no Pydantic; frontend parcialmente tipado em `TelemetryExtended`.

| Camada | Status |
|--------|--------|
| Agregador | `telemetry/aggregator.py` ✅ |
| Frontend panel | `TelemetryPanel.jsx` ✅ |

### Contrato (3) Pi → ESP32 · Setpoint (UART)

```json
{"w_esq":0.0,"w_dir":0.0,"garfo":"parar"}
```

Framing: `{"w_esq":1.5,"w_dir":1.5,"garfo":"parar"}*a3\n`

| Camada | Encode | Decode |
|--------|--------|--------|
| Pi | `protocol.encode_setpoint()` | — |
| ESP32 | — | `decodeSetpoint()` + SetpointFrameDecoder |
| Testes | `test_protocol.py`, `test_crc8.py` | ✅ cross-check CRC |

**Unidades:** ω em **rad/s**; garfo enum `subir|descer|parar`.

### Contrato (4) ESP32 → Pi · Sensores (UART)

```json
{
  "enc":{"esq":0.0,"dir":0.0},
  "mpu":{"ax":0,"ay":0,"az":9.8,"gx":0,"gy":0,"gz":0,"temp_c":25},
  "bms":null
}
```

| Camada | Encode | Decode |
|--------|--------|--------|
| ESP32 | `encodeSensors()` | — |
| Pi | — | `SensorsFrameDecoder` + `models.Sensors` |
| Alimentação | — | Kalman (IMU) + EKF (enc + gyro Z) |

**Alinhamento verificado:**
- CRC-8/MAXIM idêntico Pi ↔ ESP (`test_crc8_cross_check_firmware_algorithm`)
- Velocidades encoder em rad/s
- MPU cru (sem filtro no ESP) — Kalman no Pi

---

## 5. Matriz de prontidão por subsistema

### ✅ Pronto — reutilizar sem mudar código

| Item | Evidência |
|------|-----------|
| Control loop @20 Hz independente do frontend | `test_control_loop.py` |
| Máquina de estados + latch PARADO | `test_state_machine.py` |
| Navegação APPROACH/FACE/RETREAT | `sim_sweep` 9/9, 25 testes |
| Missão pick-and-place | 4 mapas integração |
| EKF predict + correct + gating | `test_ekf.py` |
| Kalman roll/pitch | `test_kalman.py` |
| Protocolo serial JSON+CRC8 | `test_protocol.py`, `test_crc8.py` |
| PySerialTransport | `test_hardware_interfaces.py` |
| RealVisionSource (código) | OpenCV + pupil-apriltags |
| Firmware ESP32 (código) | main, pid, motors, encoders, protocol |
| Frontend WebSocket + UI operador | 11 testes vitest |
| Rotas missão/mapas em SIM=0 | `main.py` |

### ⚠️ Pronto com ressalvas — funciona, mas precisa calibrar no chão

| Item | Valor atual | Ação no robô |
|------|-------------|--------------|
| PID Kp/Ki/Kd | 20/5/1 | Ziegler-Nichols |
| WHEEL_BASE, WHEEL_RADIUS | 15 cm, 2.8 cm | Medir |
| ENCODER_PPR | 360 | Validar 1 volta |
| ZREF / standoff | 15 cm | Medir distância real |
| NAV_K*, EKF_Q/R | Tunados em sim | Re-tunar |
| APRILTAG_SIZE | 5 cm | Paquímetro |
| CAMERA_TO_FORK_OFFSET | (0,0,0) | Medir posição relativa |
| Convenção yaw em pose.py | Derivada de pitch | Validar vs câmera real |
| COMMAND_WATCHDOG_MS | 400 ms | Validar RTT Wi-Fi |

### ❌ Bloqueante — impede operação autônoma confiável

| Item | Estado | Ação |
|------|--------|------|
| `camera_intrinsics.json` | fx/fy/cx/cy = null | Calibração xadrez |
| Mapa arena real | Só mapas sim | Medir e criar JSON |
| Teste UART Pi↔ESP32 | Nunca rodou | Conectar USB, validar frames |
| Teste câmera real | Nunca rodou | Tag visível, detecção OK |

### ➖ Opcional / não bloqueante

| Item | Estado |
|------|--------|
| BMS digital | Firmware retorna null |
| Wi-Fi AP (Pi vs roteador) | Decisão equipe |
| Teste E2E WebSocket automatizado | Gap conhecido |
| `verify.sh` ruff lint | 58 avisos estilo (não funcional) |
| Rotas `/sim/*` | Desligadas em SIM=0 (correto) |

---

## 6. O que o simulador provou (e o que NÃO provou)

### Prova (confiança alta no real)

1. **Arquitetura de 4 loops** funciona sem deadlock
2. **1 clique AUTOMATICO** basta — control loop re-propõe setpoint @20 Hz
3. **Perda de tag → PARADO latched** — só novo comando reativa
4. **Convergência navegação** a ~15 cm com offset lateral ≤2.4 cm (9 cenários)
5. **Missão completa** em 4 mapas simulados
6. **Protocolo serial** compatível emulador ↔ testes CRC
7. **Watchdog serial** para motores (emulador; firmware espelha)

### NÃO prova (só hardware)

1. Câmera real detecta tags na distância/iluminação da arena
2. PnP real tem mesma precisão que geometria sintética + ruído 0.2 cm
3. PID real converge sem oscilar (L298n, atrito, carga)
4. Encoders NXT com level shifter reportam PPR=360 corretamente
5. Garfo worm gear segura massa real do pallet
6. EKF com ruído real de patinagem e detecções ruins
7. Wi-Fi RTT < 170 ms com celular do operador

---

## 7. Checklist de transição — ordem exata

### Fase A — Software (sem robô)

- [x] Lógica Pi implementada
- [x] Firmware ESP32 implementado
- [x] Interfaces hardware implementadas
- [x] 162 pytest + 11 frontend passam
- [x] Contratos alinhados Pi/ESP/frontend
- [ ] `pio run` compila firmware (equipe)
- [ ] `bash scripts/verify.sh` verde (lint pendente)

### Fase B — Hardware mínimo (serial only)

- [ ] Gravar firmware ESP32
- [ ] `pio device monitor` — frames sensores @20 Hz
- [ ] Girar roda → `enc.esq`/`enc.dir` mudam
- [ ] Inclinar → MPU responde
- [ ] `SIM=0`, `SERIAL_PORT=/dev/ttyACM0` (ou USB0)
- [ ] Backend log: "Serial loop (REAL) iniciado"
- [ ] Telemetria WebSocket: `rodas`, `imu` fluem
- [ ] Joystick manual move motores
- [ ] Desconectar USB → motores param <200 ms

### Fase C — Visão

- [ ] Calibrar câmera → `camera_intrinsics.json`
- [ ] Tag tag25h9 visível na câmera
- [ ] Telemetria: `visao.detectado=true`, z_cm/x_cm plausíveis
- [ ] Medir `APRILTAG_SIZE_CM`, `CAMERA_TO_FORK_OFFSET_CM`

### Fase D — Mecânica e mapa

- [ ] Medir L, r, PPR → `config.py` + `config.h`
- [ ] Criar mapa JSON arena real
- [ ] `POST /maps/load/arena_real`

### Fase E — Autonomia

- [ ] AUTOMATICO (1 clique) converge Z≈15 cm
- [ ] Perda tag → PARADO latched
- [ ] Sintonia PID Ziegler-Nichols
- [ ] Re-tunar EKF/NAV
- [ ] Missão pick-place completa

---

## 8. Configuração `.env` para transição

```bash
# Modo real
SIM=0

# Serial ESP32
SERIAL_PORT=/dev/ttyUSB0      # ls /dev/tty* após conectar
SERIAL_BAUDRATE=115200

# Câmera
CAMERA_INDEX=0
REQUIRE_CAMERA_CALIBRATION=1    # 0 só para debug sem calibração
CAMERA_FRAME_WIDTH=1280
CAMERA_FRAME_HEIGHT=720

# Mapa
MAP=arena_real_medida

# Frontend (celular)
VITE_PI_WS_URL=ws://<IP_DO_PI>:8000/ws
```

Subir:

```bash
cd src && ./scripts/run_pi.sh
```

---

## 9. Diagnóstico rápido pós-boot

| Log esperado | Se não aparecer |
|--------------|-----------------|
| `Modo REAL (hardware)` | Verificar `SIM=0` no `.env` |
| `Serial loop (REAL) iniciado` | Porta serial errada ou permissão (`dialout`) |
| `Detector criado com calibração` | `camera_intrinsics.json` null → calibrar |
| `Visão real indisponível` | Câmera não abriu ou calibração faltando |
| Telemetria @20 Hz no frontend | WebSocket URL ou firewall Wi-Fi |

---

## 10. Respostas diretas às perguntas da equipe

### "O Pi está pronto?"
**Sim** — toda a lógica, filtros, loops e interfaces estão implementados e testados
em simulação. Falta calibrar parâmetros e validar UART/câmera no hardware.

### "O ESP está pronto?"
**Sim (código)** — firmware completo com PID, encoders, MPU, garfo, protocolo,
watchdog. Falta gravar, compilar no ambiente da equipe e sintoniar PID no chão.

### "A lógica de navegação/missão está pronta?"
**Sim** — 162 testes + sim_sweep 9/9. Ganhos finos podem precisar ajuste no chão.

### "Os filtros estão prontos?"
**Sim (código)** — Kalman (IMU) e EKF 2D (odometria+tags) implementados e testados.
Covariâncias Q/R são placeholders — calibrar com dados reais.

### "As interfaces de comunicação estão prontas?"
**Sim** — 4 contratos alinhados em 3 linguagens; CRC8 cross-tested; PySerialTransport
e RealVisionSource implementados. UART real nunca foi exercitada fisicamente.

### "Posso ligar o robô amanhã?"
**Sim para smoke test manual** (joystick + garfo + serial).  
**Não para missão autônoma confiável** sem calibração câmera + mapa + sintonia.

---

## 11. Referência de arquivos críticos

```
src/
├── pi/app/
│   ├── main.py                 ← troca SIM↔real
│   ├── config.py               ← parâmetros (muitos TODO)
│   ├── hardware/interfaces.py  ← VisionSource, SerialTransport
│   ├── comms/
│   │   ├── protocol.py         ← JSON+CRC8
│   │   └── serial_transport.py ← UART real
│   ├── tasks/
│   │   ├── control_loop.py     ← 20 Hz, missão+nav
│   │   ├── serial_loop.py      ← sim + real
│   │   ├── vision_loop.py      ← SimVision + RealVision
│   │   └── websocket_handler.py
│   ├── control/
│   │   ├── ekf.py              ← localização 2D
│   │   ├── kalman.py           ← IMU roll/pitch
│   │   ├── navigation.py       ← APPROACH/FACE/RETREAT
│   │   └── state_machine.py    ← latch segurança
│   └── calibracao/
│       └── camera_intrinsics.json  ← ❌ null
├── firmware/src/
│   ├── main.cpp                ← loop dual-rate
│   ├── config.h                ← pinos + ganhos
│   ├── protocol.cpp            ← encode/decode
│   ├── pid.cpp, motors.cpp, encoders.cpp
├── frontend/src/
│   ├── types/contracts.ts      ← espelho contratos
│   └── ws/useWebSocket.js
└── docs/
    ├── serial-protocol.md      ← fonte de verdade
    └── readiness-sim-to-real.md ← este documento
```

---

## 12. Frase final

> **O software está pronto para a transição.** O robô físico não está pronto para
> operar autonomamente até a equipe completar calibração (câmera, mecânica, mapa),
> gravar o firmware, conectar UART e repetir os smoke tests que o simulador já
> validou em lógica. Não falta código — falta **medição e sintonia no chão**.
