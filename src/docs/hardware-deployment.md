# Deploy no Robô Real — Guia Operacional

> **Objetivo:** sair de `SIM=1` (simulação validada) para `SIM=0` (hardware físico)
> com passos concretos, sem ambiguidade sobre o que já está implementado, o que falta
> medir e onde o código liga cada peça.

Documentação complementar:
- [`hardware-bring-up.md`](./hardware-bring-up.md) — pinos, energia, fiação
- [`hardware-interfaces.md`](./hardware-interfaces.md) — contratos `VisionSource` / `SerialTransport`
- [`serial-protocol.md`](./serial-protocol.md) — JSON + CRC8 (fonte de verdade dos 4 contratos)
- [`camera-calibration.md`](./camera-calibration.md) — intrínsecos da câmera
- [`verification-status.md`](./verification-status.md) — o que foi testado em simulação

---

## 1. Estado atual do software

| Camada | Status | Observação |
|--------|--------|------------|
| Lógica de controle (Pi) | ✅ Implementada | Control loop @20 Hz, EKF, missão, navegação |
| Simulação (`SIM=1`) | ✅ Validada | 162 testes pytest + 11 frontend; sim_sweep 9/9 convergem |
| Firmware ESP32 | ✅ Implementado | PID, encoders, MPU, garfo, protocolo serial |
| Interfaces hardware Pi | ✅ Implementadas | `RealVisionSource`, `PySerialTransport` |
| Calibração câmera real | ❌ Pendente | `camera_intrinsics.json` ainda com `null` |
| Teste UART real Pi↔ESP32 | ❌ Pendente | Código pronto; nunca rodou no chão |
| Mapa da arena real | ❌ Pendente | JSONs em `pi/maps/` são da simulação |
| Parâmetros mecânicos | ⚠️ Provisórios | Valores em `config.py` / `config.h` — medir no robô |

**Regra de ouro:** a lógica (navegação, EKF, missão, máquina de estados) **não muda**
entre simulação e real. Só trocam as implementações injetadas em `app/main.py`.

---

## 2. Onde o hardware é ativado no código

Único ponto de troca: `lifespan()` em `pi/app/main.py`.

```
SIM=1 (simulação)                    SIM=0 (real)
─────────────────                    ──────────────
SimVisionSource                      RealVisionSource  ← OpenCV + pupil-apriltags
serial_loop_sim()                    serial_loop_real() ← PySerialTransport (UART)
FirmwareEmulator                     ESP32 via USB serial
SyntheticVision                      Câmera física
SimWorld                             Arena física + mapa JSON medido
```

As **quatro tarefas asyncio** sobem em ambos os modos:

| Tarefa | Arquivo | Função |
|--------|---------|--------|
| WebSocket Handler | `tasks/websocket_handler.py` | Comandos do operador, telemetria @20 Hz |
| Vision Loop | `tasks/vision_loop.py` | Detecção AprilTag → EKF |
| Serial Loop | `tasks/serial_loop.py` | Setpoint ↔ sensores @20 Hz |
| Control Loop | `tasks/control_loop.py` | Missão/navegação → setpoint @20 Hz |

Se câmera ou serial falharem no boot real, a app **continua** (log de erro) — útil para
bring-up parcial, mas missão autônoma exige ambos funcionando.

---

## 3. Fluxo de dados no hardware real

```
┌─────────────┐  ws://Pi:8000/ws   ┌──────────────────────────────────────┐
│  Celular    │◄──────────────────►│  Raspberry Pi                        │
│  (React)    │  comando + telem.  │                                      │
└─────────────┘                    │  Control Loop → current_setpoint     │
                                   │       ▲                              │
                                   │  Vision Loop ← câmera USB            │
                                   │       │ correct_apriltag (EKF)       │
                                   │  Serial Loop ↔ UART                  │
                                   └───────────────┬──────────────────────┘
                                                   │ /dev/ttyUSB0 @115200
                                                   │ JSON+CRC8+\n @20 Hz
                                                   ▼
                                   ┌──────────────────────────────────────┐
                                   │  ESP32                               │
                                   │  PID 100 Hz → PWM → L298n → motores  │
                                   │  Encoders + MPU-6050 → frame sensores│
                                   └──────────────────────────────────────┘
```

### O que o Pi **envia** ao ESP32 (contrato 3 — setpoint)

```json
{"w_esq": 0.0, "w_dir": 0.0, "garfo": "parar"}
```

| Campo | Unidade | Origem no Pi |
|-------|---------|--------------|
| `w_esq`, `w_dir` | rad/s | Control loop → cinemática / segment executor |
| `garfo` | `"subir"` \| `"descer"` \| `"parar"` | Comando WebSocket do operador (sempre manual) |

Enviado por `PySerialTransport.send_setpoint()` → `encode_setpoint()` em `comms/protocol.py`.

### O que o ESP32 **devolve** ao Pi (contrato 4 — sensores)

```json
{"enc": {"esq": 0.0, "dir": 0.0}, "mpu": {"ax":..,"ay":..,"az":..,"gx":..,"gy":..,"gz":..,"temp_c":..}, "bms": null}
```

| Campo | Unidade | Uso no Pi |
|-------|---------|-----------|
| `enc.esq`, `enc.dir` | rad/s | EKF predict + telemetria |
| `mpu.*` | m/s², °/s, °C | Kalman roll/pitch + EKF gyro Z |
| `bms` | null ou `{cel, i_a, temp_c}` | Telemetria (BMS **não integrado** no firmware ainda) |

Lido por `PySerialTransport.read_sensors()` → `SensorsFrameDecoder` → `serial_loop_real()`.

### O que a câmera **fornece** (interno — não vai na serial)

| Saída | Tipo | Uso |
|-------|------|-----|
| `VisionState` | z_cm, x_cm, pitch_deg | Telemetria + navegação legado |
| `TagObservation[]` | posição relativa + yaw | Correção multi-tag no EKF |

Implementado em `RealVisionSource` (`tasks/vision_loop.py`).

> **O que provavelmente vai mudar no hardware real**
>
> - Intrínsecos da câmera (`fx, fy, cx, cy`) — após calibração xadrez
> - Offset câmera→garfo — erro sistemático de posicionamento se não medido
> - Ganhos PID (`config.h`) — sintonia Ziegler-Nichols no chão
> - Ganhos EKF (`EKF_Q_*`, `EKF_R_*`) — ruído real ≠ simulado
> - Ganhos navegação (`NAV_*`) — dinâmica real, inércia, patinagem
> - `ENCODER_PPR`, `WHEEL_RADIUS`, `WHEELBASE` — medição mecânica
> - FOV/alcance da câmera — validar vs. `SIM_VISION_*` da simulação
> - Unidade de `bms.cel` — marcado `TODO(equipe)` (provavelmente V por célula)
> - Convenção de `yaw_rad` em `pose.py` — validar contra frame real da câmera

---

## 4. Passo a passo no robô (ordem obrigatória)

### Fase A — Montagem elétrica (sem energizar motores)

1. Conferir mapa de pinos em [`hardware-bring-up.md`](./hardware-bring-up.md)
   (alinhado com `Testes_eletronica.ino`: ESQ=12/14/13, DIR=27/26/25, garfo=18/19/5,
   ENC-ESQ=23/15 — refiado 2026-07-06, era 34/35 —, ENC-DIR=32/33).
2. GND comum: fonte 12 V, L298n ×2, ESP32, Pi, MPU-6050.
3. Remover jumpers ENA/ENB dos dois L298n.
4. Level shifter nos encoders NXT se saída > 3,3 V (medir com multímetro).
5. Encoders sem pull-up externo: os pinos atuais (23/15 e 32/33) têm pull-up
   interno (`INPUT_PULLUP`). GPIO 34/35 ficaram livres (refiado 2026-07-06 —
   sobrecontavam por ruído; se reutilizados, exigem pull-up externo).
   **Não** colocar pull-up no GPIO 12 (strapping).
6. Fim-de-curso garfo: **desabilitados** (-1 em `config.h` — chaves não montadas;
   garfo nunca bloqueia por limite). Ao instalar, usar GPIOs livres — GPIO 5 agora
   é o PWM do garfo.
7. MPU-6050: SDA=21, SCL=22, endereço 0x68.

### Fase B — Firmware ESP32 (isolado)

```bash
cd src/firmware
pio run --target upload
pio device monitor -b 115200
```

**Validar:**
- [ ] Frames de sensores a ~20 Hz (JSON+CRC8)
- [ ] Girar roda manualmente → `enc.esq`/`enc.dir` mudam de sinal
- [ ] Inclinar chassi → `mpu.ax/ay/az` respondem
- [ ] Enviar setpoint de teste via monitor (ou script) → motor responde
- [ ] Desconectar serial → motores param em < 200 ms (watchdog)

### Fase C — Calibração mecânica

Medir e atualizar **antes** de confiar na odometria/EKF:

| Parâmetro | Arquivo | Como medir |
|-----------|---------|------------|
| `WHEEL_BASE_L_CM` | `pi/app/config.py` | Centro eixo esq → centro eixo dir |
| `WHEEL_RADIUS_R_CM` | `pi/app/config.py` | Diâmetro roda ÷ 2 |
| `ENCODER_PPR` | `firmware/src/config.h` + `config.py` | 1 volta manual → ~1440 contagens (x4; validado 2026-07-06) |
| `EMU_FORK_MAX_HEIGHT` | `pi/app/config.py` | Curso vertical do garfo |
| `PALLET_MASS_KG` | `pi/app/config.py` | Balança |
| `APRILTAG_SIZE_CM` | `pi/app/config.py` | Paquímetro na tag impressa |
| `CAMERA_TO_FORK_OFFSET_CM` | `pi/app/config.py` | Posição relativa câmera ↔ garfo |

Espelhar `WHEELBASE_M`, `WHEEL_RADIUS_M` em `config.py` (derivados automaticamente).

### Fase D — Calibração câmera

1. Seguir [`camera-calibration.md`](./camera-calibration.md).
2. Preencher `pi/calibracao/camera_intrinsics.json` com `fx, fy, cx, cy` reais.
3. Confirmar família `tag25h9` e tamanho físico da tag.

Enquanto `null`, `RealVisionSource` **falha no boot** se `REQUIRE_CAMERA_CALIBRATION=1`
(padrão). Para teste sem calibração: `REQUIRE_CAMERA_CALIBRATION=0` (pose imprecisa).

### Fase E — Mapa da arena real

1. Medir arena com fita métrica (origem = canto inferior esquerdo).
2. Posicionar tags: `(x_m, y_m, yaw_deg)` + `position_id` (ex.: "L1", "P3").
3. Copiar template de `pi/maps/corredor_pequeno.json` e ajustar.
4. Validar: `python3 -c "from app.world.map_schema import load_map; load_map('maps/seu_mapa.json')"`

### Fase F — Backend Pi em modo real

Criar `src/.env`:

```bash
SIM=0
PI_HOST=0.0.0.0
PI_PORT=8000
SERIAL_PORT=/dev/ttyUSB0      # ou /dev/ttyACM0 — ls /dev/tty*
SERIAL_BAUDRATE=115200
MAP=arena_real_medida
REQUIRE_CAMERA_CALIBRATION=1
CAMERA_INDEX=0
VITE_PI_WS_URL=ws://<IP_DO_PI>:8000/ws
```

Subir:

```bash
cd src
pip install -e ".[dev]"
./scripts/run_pi.sh
```

**Smoke tests (ordem):**

| # | Teste | Esperado |
|---|-------|----------|
| 1 | Log "Modo REAL (hardware)" | SIM=0 ativo |
| 2 | Log "Serial loop (REAL) iniciado" | UART aberta |
| 3 | Log "Detector criado com calibração" | Câmera OK |
| 4 | Telemetria WebSocket @20 Hz | `rodas`, `imu`, `visao` fluem |
| 5 | Joystick manual | Rodas giram na direção correta |
| 6 | Garfo subir/descer | Motor garfo responde. ⚠️ Fim-de-curso desabilitado (-1): operador solta o botão antes do fim do curso |
| 7 | Desconectar USB serial | Motores param < 200 ms |
| 8 | Modo AUTOMATICO (1 clique) | Robô navega sem streaming de comando |
| 9 | Ocultar tag | PARADO + latch; só novo comando reativa |

### Fase G — Sintonia PID (ESP32)

Procedimento em `firmware/README.md` § Ziegler-Nichols:

1. Ki=0, Kd=0; aumentar Kp até oscilar → Ku
2. Medir período Tu
3. Kp=0.6·Ku, Ki=2·Kp/Tu, Kd=Kp·Tu/8
4. Ajustar empiricamente; atualizar `firmware/src/config.h`
5. Recompilar e regravar firmware

### Fase H — Sintonia navegação + EKF

1. Confirmar `ZREF_CM=15` dá margem de frenagem (ajustar se necessário).
2. Testar aproximação reativa (modo AUTOMATICO sem missão).
3. Comparar odometria pura vs. EKF com tags visíveis.
4. Ajustar `EKF_Q_*`, `EKF_R_*`, `NAV_K_DIST`, `NAV_K_HEADING`.
5. Rodar missão em arena aberta antes de corredores.

### Fase I — Missão completa

1. Carregar mapa: `POST /maps/load/arena_real_medida`
2. Iniciar: `POST /mission/start` (ou painel Mission no frontend)
3. Robô navega até pick → para → operador usa garfo → "continuar"
4. Navega até place → operador usa garfo → "continuar"
5. Retorna home → DONE

---

## 5. O que falta implementar / definir

### Bloqueantes para operação autônoma confiável

| Item | Onde | Ação da equipe |
|------|------|----------------|
| Calibração câmera | `pi/calibracao/camera_intrinsics.json` | Calibrar com xadrez |
| Mapa arena real | `pi/maps/*.json` | Medir e criar JSON |
| Medição L, r, PPR | `config.py` + `config.h` | Medir no chassi |
| Offset câmera→garfo | `config.py` | Medir posição relativa |
| Teste UART real | campo | Conectar Pi↔ESP32 e validar frames |
| Sintonia PID | `config.h` | Ziegler-Nichols no hardware |

### Definições de infraestrutura (não bloqueiam código)

| Item | Impacto | Decisão pendente |
|------|---------|------------------|
| Modelo Raspberry Pi | FPS visão, energia | Pi 4/5 recomendado para 720p @ 20 Hz |
| Access Point Wi-Fi | RTT < 170 ms | Pi como AP vs. roteador externo |
| Massa real do pallet | Motor garfo | 0,1 kg vs ~1 kg — inconsistência aberta |
| `MISSION_RESUME_TRIGGER` | UX missão | Botão "continuar" (default) vs. fim-de-curso |
| Unidade `bms.cel` | Telemetria bateria | Confirmar V por célula |
| Integração BMS digital | Firmware | `main.cpp` tem TODO — BMS retorna null hoje |

### Melhorias recomendadas (pós bring-up)

- Teste E2E automatizado com WebSocket real (`httpx` + TestClient)
- Validar convenção `yaw_rad` em `pose.py` contra tags físicas
- Medir FOV real da câmera vs. `SIM_VISION_FOV_H_DEG=60°`
- Documentar mapa Wi-Fi e IP fixo do Pi para o celular

---

## 6. Interfaces — o que a equipe pode trocar sem tocar na lógica

Definidas em `pi/app/hardware/interfaces.py`:

### `VisionSource`

```python
def get_vision(self) -> VisionState
def get_all_detections(self) -> list[TagObservation]
```

- **Real:** `RealVisionSource` — OpenCV + pupil-apriltags
- **Sim:** `SimVisionSource` — geometria robô-tag
- **Substituir por:** qualquer classe que implemente os dois métodos
- **Injeção:** passar instância customizada em `main.py` no branch `SIM=0`

### `SerialTransport`

```python
async def open(self)
async def send_setpoint(self, setpoint: Setpoint)
async def read_sensors(self, timeout_s) -> list[Sensors]
async def close(self)
```

- **Real:** `PySerialTransport` — UART USB
- **Sim:** `FirmwareEmulator` via `serial_loop_sim`
- **Substituir por:** socket, CAN, mock para teste
- **Injeção:** `serial_loop_real(state, transport=MeuTransporte())`

Teste sem hardware: `tests/test_hardware_interfaces.py::TestSerialLoopReal`.

---

## 7. Checklist final antes da competição / demo

```
[ ] Firmware gravado e frames @ 20 Hz no monitor serial
[ ] Encoders respondem; sentido de rotação correto
[ ] MPU retorna dados não-zero
[ ] Garfo sobe/desce (fim-de-curso desabilitado — operador controla o curso)
[ ] camera_intrinsics.json preenchido
[ ] Mapa JSON da arena validado
[ ] SIM=0 sobe sem erro fatal
[ ] Joystick manual OK
[ ] AUTOMATICO converge em frente à tag (Z ≈ 15 cm)
[ ] Perda de tag → PARADO latched
[ ] Watchdog serial OK (< 200 ms)
[ ] Missão pick-place completa em arena real
[ ] Frontend conecta via Wi-Fi (VITE_PI_WS_URL correto)
[ ] Parâmetros TODO(equipe) revisados e confirmados
```

---

## 8. Comandos de referência rápida

```bash
# Verificação completa (simulação)
cd src && bash scripts/verify.sh

# Simulação + dashboard
SIM=1 ./scripts/run_pi.sh
cd frontend && npm run dev    # http://localhost:5173/demo

# Hardware real
SIM=0 ./scripts/run_pi.sh

# Testes
cd src && python3 -m pytest pi/tests/ -v
cd src && python3 pi/tests/sim_sweep.py

# Gravar firmware
cd src/firmware && pio run -t upload
```
