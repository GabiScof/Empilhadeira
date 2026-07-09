# Simulador → Robô Real — o que foi validado e o que transfere

Papel do simulador, o que foi validado nele, e o que transfere (ou não) para
`SIM=0` no hardware físico.

Ver também:
- [`simulation.md`](./simulation.md) — como rodar `SIM=1`, APIs `/sim/*`, falhas
- [`hardware-deployment.md`](./hardware-deployment.md) — passo a passo no robô
- [`hardware-interfaces.md`](./hardware-interfaces.md) — contratos `VisionSource` / `SerialTransport`
- [`verification-status.md`](./verification-status.md) — testes e bugs corrigidos

---

## 1. Ideia central

O simulador substitui duas peças de hardware (câmera + ESP32) nas mesmas
interfaces Python que o robô real usa.

```
                    ┌─────────────────────────────────────┐
                    │   LÓGICA COMPARTILHADA              │
                    │                                     │
  Frontend ────────►│  WebSocket Handler                  │
  (React)           │  Control Loop @20 Hz                │
                    │  Vision Loop                        │
                    │  Serial Loop                        │
                    │  EKF · Missão · Planejador          │
                    │  Navegação · Máquina de estados     │
                    │  Telemetria · Protocolo JSON+CRC8   │
                    └──────────┬──────────────┬───────────┘
                               │              │
                    SIM=1      │              │      SIM=0
                               ▼              ▼
                    ┌──────────────┐  ┌──────────────┐
                    │  EMULADOS    │  │  HARDWARE    │
                    │  (Python)    │  │  (físico)    │
                    ├──────────────┤  ├──────────────┤
                    │ SimWorld     │  │ Arena real   │
                    │ FirmwareEmu  │  │ ESP32        │
                    │ SynthVision  │  │ Câmera USB   │
                    │ FaultInject  │  │ (sem falhas  │
                    │              │  │  injetáveis) │
                    └──────────────┘  └──────────────┘
```

**Regra:** se funciona em `SIM=1`, a lógica está correta. Se falhar em `SIM=0`, o
problema está na calibração, fiação, sensores ou parâmetros físicos — não na arquitetura.

A troca acontece em um único lugar: `lifespan()` em `pi/app/main.py`.

---

## 2. O que construímos no simulador

### 2.1 Quatro componentes emulados (`pi/app/sim/`)

| Componente | Arquivo | Substitui no real |
|------------|---------|-------------------|
| SimWorld | `world.py` | Chassi físico + arena + tags coladas |
| FirmwareEmulator | `firmware_emulator.py` | ESP32 + L298n + motores + encoders + MPU + garfo |
| SyntheticVision | `synthetic_vision.py` | Câmera USB + detector AprilTag |
| FaultInjector | `fault_injector.py` | (só simulação — não existe no real) |

Mais a camada de integração:
- `SimVisionSource` — adapta `SyntheticVision` ao contrato `VisionSource`
- `serial_loop_sim()` — adapta `FirmwareEmulator` ao contrato `SerialTransport`
- Rotas `/sim/*` — reset de pose, debug, injeção de falhas
- Frontend `/demo` — dashboard com arena, telemetria, fault injector

### 2.2 SimWorld — mundo físico paramétrico

**O que faz:**
- Carrega arena, tags e `start_pose` de um mapa JSON (`pi/maps/*.json`)
- Integra cinemática diferencial a partir das velocidades das rodas (odometria)
- Atualiza `(x, y, θ)` do robô a cada tick do emulador
- Suporta slip de roda (multiplicador por eixo) e ruído de encoder

**O que não faz:**
- Não modela inércia 3D, pitch/roll do chassi, colisões com pallets
- Não simula atrito real, patinagem parcial, ou superfícies irregulares
- Não simula latência Wi-Fi entre celular e Pi

**No robô real:** o mundo físico é a arena. O mapa JSON continua existindo,
mas descreve posições medidas na arena, não um modelo idealizado.

### 2.3 FirmwareEmulator — réplica do ESP32

**O que faz (modela `firmware/src/` com simplificações):**

| Aspecto | Valor emulado | Fonte no firmware |
|---------|---------------|-------------------|
| PID por roda | Kp=20, Ki=5, Kd=1 | `config.h` |
| Anti-windup | ±500 | `PID_INTEGRAL_LIMIT` |
| Taxa PID | ~100 Hz | `PID_HZ` |
| Motor | 1ª ordem, τ≈50 ms, max 12.25 rad/s | `motors.cpp` |
| Encoder | PPR=1440 (x4), ω = pulsos/dt | `encoders.cpp` |
| Garfo | duty 220 (subiu de 180 na bancada), altura 0–10 cm, limites | `motors.cpp` |
| Watchdog | 200 ms sem setpoint → motores=0 | `main.cpp` |
| Protocolo | JSON+CRC8+\n @20 Hz | `protocol.cpp` |
| MPU | gravidade + ruído a partir da pose | sintético |

**O que não faz:**
- Não reproduz exatamente a não-linearidade do L298n (dead zone, aquecimento)
- Não modela bounce/backlash dos encoders NXT
- Não simula queda de tensão da bateria sob carga
- BMS sempre retorna `null` (o fault `battery_saturated` seta um flag mas nenhum componente o lê — sem efeito real)

**No robô real:** o ESP32 roda o firmware C++ real. O emulador serve para
desenvolver a lógica do Pi e calibrar ganhos iniciais; a sintonia PID final
deve ser feita no hardware (Ziegler-Nichols no chão).

### 2.4 SyntheticVision — câmera sem hardware

**O que faz:**
- Calcula geometricamente quais tags estão no FOV a partir da pose do robô
- Devolve `z_cm`, `x_cm`, `pitch_deg` no mesmo contrato que a câmera real
  (convenção do projeto: `x_cm` positivo = tag à esquerda; na câmera real o
  frame óptico OpenCV tem x positivo = direita, e o `pose.py` nega o x na
  fronteira — corrigido 2026-07-06; sem isso a navegação viraria para longe
  da tag)
- Suporta múltiplas tags (para fusão EKF multi-tag)
- Adiciona ruído gaussiano configurável (posição ±0,2 cm, ângulo ±0,5°)
- Simula FOV horizontal 60°, alcance 3–150 cm
- Permite injetar: tag oculta, blur probabilístico, drop de frame

**O que não faz:**
- Não roda PnP real (solvePnP) — usa geometria analítica perfeita + ruído
- Não simula motion blur, auto-exposure, distorção de lente, tags inclinadas 3D
- Não testa iluminação, reflexo, motion blur da câmera real
- Não usa intrínsecos de câmera (geometria pura robô→tag, sem modelo óptico)

**No robô real:** `RealVisionSource` usa OpenCV + pupil-apriltags + calibração real.
A lógica downstream (EKF, navegação, telemetria) é idêntica; só muda a qualidade
e o timing das detecções.

### 2.5 FaultInjector — injeção de falhas

Exclusivo da simulação. Permite testar modos de segurança sem risco ao hardware:

| Falha | O que testa no Pi |
|-------|-------------------|
| `serial_drop` | Watchdog ESP32 → motores param |
| `tag_hidden` | Perda de tag → PARADO + latch |
| `wheel_slip` | Deriva de odometria / EKF |
| `vision_blur/drop` | EKF e navegação sob blur/drop |
| `encoder_noise` | Predição EKF degradada |
| `gyro_drift` | Heading deriva entre tags |

**No robô real:** essas falhas acontecem naturalmente (patinagem, tag fora do FOV,
cabos soltos). Não há API para injetá-las — são provocadas fisicamente.

---

## 3. O que roda idêntico nos dois modos

Estes módulos não sabem se estão em simulação. Vão para o robô sem alteração.

### 3.1 Backend e comunicação com o celular

| Módulo | Arquivo | Função |
|--------|---------|--------|
| FastAPI + lifespan | `main.py` | Startup, rotas, missão, mapas |
| WebSocket Handler | `tasks/websocket_handler.py` | Comandos, telemetria @20 Hz, watchdog |
| Protocolo serial | `comms/protocol.py`, `crc8.py` | JSON+CRC8 — mesmo framing nos dois modos |
| Modelos Pydantic | `models.py` | 4 contratos congelados |
| Telemetria | `telemetry/aggregator.py` | Monta pacote para o frontend |

### 3.2 Controle e navegação

| Módulo | Arquivo | Função |
|--------|---------|--------|
| Control Loop | `tasks/control_loop.py` | Orquestra tudo @20 Hz |
| Máquina de estados | `control/state_machine.py` | MANUAL/AUTOMATICO/PARADO + latch segurança |
| Cinemática | `control/kinematics.py` | Joystick → (v,ω) → (ω_esq, ω_dir) |
| Navegação reativa | `control/navigation.py` | APPROACH/FACE/RETREAT, bearing, dead zone |
| Planejador | `control/path_planner.py` | A*, Manhattan, segmentos |
| Executor | `control/segment_executor.py` | Segue rota usando pose EKF |
| Missão | `mission/mission_sm.py` | Pick-and-place completo |
| Kalman IMU | `control/kalman.py` | Roll/pitch filtrados para telemetria |

### 3.3 Localização

| Módulo | Arquivo | Função |
|--------|---------|--------|
| EKF 2D | `control/ekf.py` | Fusão odometria + tags |
| Vision Loop | `tasks/vision_loop.py` | Loop @20 Hz — mesma estrutura, fonte diferente |
| Serial Loop | `tasks/serial_loop.py` | Loop @20 Hz — mesma estrutura, transporte diferente |
| World Model | `world/world_model.py` | Mapas JSON, tags, grafo |
| Robot Model | `world/robot_model.py` | Conversões SI, odometria |

### 3.4 Frontend

| Componente | Reutilização |
|------------|--------------|
| Joystick, garfo, seletor de modo | 100% — mesmo WebSocket |
| Telemetria, SafetyAlert, nav_phase | 100% |
| MissionPanel, MapSelector | 100% — rotas `/mission/*`, `/maps/*` existem nos dois modos |
| Arena visual (vista de cima) | Nos dois modos — prefere `/sim/world-state` e cai para `/world-state` (pose do EKF + mapa) em `SIM=0` |
| FaultInjector, DebugExport, PoseReset | Só SIM=1 — usam APIs `/sim/*`, que não existem em `SIM=0` |

---

## 4. O que não vai para o robô real

| Item | Motivo |
|------|--------|
| `pi/app/sim/*` (tudo) | Substituído por hardware físico |
| Rotas `/sim/*` | Desligadas quando `SIM=0` |
| Página `/demo` com fault injector | Ferramenta de dev; operador usa UI normal |
| Parâmetros `SIM_*` em `config.py` | Só afetam emulação |
| `EMU_*` (emulador) | Espelham firmware — no real o firmware é a fonte |
| Mapas JSON de simulação (`corredor_pequeno`, `arena_media`, etc.) | Coordenadas idealizadas — usar `corredor_6tags_80x160` (mapa real medido) ou recriar |
| Intrínsecos placeholder da câmera | Substituídos pela calibração real de 2026-07-07 (1280×720, fx=fy=1023,63) |
| Ruído/FOV/alcance simulados | Valores estimados — medir na câmera real |
| Ganhos PID/NAV/EKF provisórios | Ponto de partida — recalibrar no chão |

---

## 5. Parâmetros compartilhados (ajustar no chão)

Estes valores existem em dois lugares e devem ser consistentes entre sim e real:

| Parâmetro | Sim (`config.py`) | Real (`config.h` + medição) | Confiança |
|-----------|-------------------|-------------------------------|-----------|
| `WHEEL_BASE_L_CM` / `WHEELBASE_M` | 15,0 cm | Medir no chassi | provisório |
| `WHEEL_RADIUS_R_CM` | 2,7 cm | Medição da equipe 2026-07-06; confirmar por rolagem | confirmar |
| `ENCODER_PPR` | 1440 (360 ciclos × 4 da quadratura) | 1 volta manual ≈ 1440 contagens | validado na bancada 2026-07-06 |
| PID Kp/Ki/Kd | `EMU_PID_*` | `config.h` — mesmos valores iniciais | transferir como ponto de partida |
| `SETPOINT_TIMEOUT_MS` | 200 ms | 200 ms | idêntico |
| `ZREF_CM` / `TAG_APPROACH_STANDOFF_M` | 15 cm | Ajustar se garfo/câmera diferirem | validar no chão |
| Ganhos navegação `NAV_*` | Tunados em sim | Re-tunar — dinâmica real difere | ponto de partida |
| Q/R do EKF (atributos de classe em `ekf.py`; os `EKF_Q_*`/`EKF_R_*` do `config.py` não são lidos) | Tunados para ruído sim | Re-tunar para ruído real — editar em `ekf.py` | ponto de partida |
| `APRILTAG_SIZE_CM` | 4,0 cm | Conferir tag impressa com paquímetro | conferir |
| Protocolo serial 115200, 20 Hz | Emulado | UART real | idêntico |

Resumo: o protocolo, a arquitetura de controle e os ganhos iniciais transferem para
o real. Dimensões mecânicas, ruído de sensores e ganhos finos precisam de medição.

---

## 6. O que fizemos e validamos no simulador

### 6.1 Sessão 1 — Integração runtime (bugs estruturais)

Descobertos rodando backend + WebSocket + frontend ao vivo (não apareciam em testes unitários):

| Problema | Impacto no real |
|----------|-----------------|
| AUTOMATICO congelava após 1 clique | Crítico — corrigido no `control_loop.py`; vale no real |
| PARADO oscilava sem latch | Crítico — corrigido na state machine; vale no real |
| WebSocket 404 (faltava `websockets`) | Deploy — vale no real |
| APIs `/sim/*` HTTP 422 | Só sim — mas missão/mapas usam mesmo padrão FastAPI |
| PID integral não resetava | Emulador — mesmo bug existiria no ESP32; firmware já reseta |
| ZREF=5 cm → overshoot | Vale no real — 15 cm é o valor atual |
| Fallback navegação deadlock | Vale no real — lógica corrigida em `navigation.py` |

### 6.2 Sessão 2 — Navegação e telemetria

| Problema | Impacto no real |
|----------|-----------------|
| Omega bang-bang (overshoot heading) | Vale no real — bearing proporcional |
| FACE durava 1-2 ticks | Vale no real — motores precisam de tempo |
| FACE→RETREAT glitch (0,0) | Vale no real |
| Convergência falsa a 24-25 cm | Vale no real — dead zone com D |
| Telemetria instável em MANUAL | Só sim (double-noise) — não afeta o real |
| `nav_phase` no dashboard | Vale no real — contrato de telemetria |

### 6.3 Testes automatizados (210 pytest — 209 passam, 1 pulado — + 11 frontend)

| Categoria | Garante para o real? |
|-----------|---------------------|
| CRC8 + protocolo serial | sim — mesmo framing UART |
| Cinemática diferencial | sim — mesmas fórmulas |
| Máquina de estados + latch | sim — mesmo código |
| Control loop (1 comando AUTO) | sim — mesmo código |
| Navegação (31 testes) | lógica sim; ganhos podem precisar ajuste |
| EKF (predição, correção, outlier) | lógica sim; ruído real diferente |
| Missão em 4 mapas simulados | fluxo da SM sim; requer o mapa real |
| Integração sim (converge ZREF) | comportamento sim; dinâmica real difere |
| Hardware interfaces | PySerialTransport pronto; falta testar UART |
| Frontend contratos | telemetria/comandos idênticos |

### 6.4 Scripts de cenário (sim_sweep, full_trace)

sim_sweep — 9/9 convergem:
- Robô parte com offset lateral 0–20 cm, heading errado ±17°, posições variadas
- Para a ~15–16 cm da tag (ZREF=15)
- Offset lateral residual ~2 cm, heading error ~3–4°

full_trace — 12/13:
- 1 cenário LOST (`far_off25_h20`) — tag fora do FOV a 130 cm com offset 25 cm + heading 20°
- Comportamento correto: máquina de estados deve ir a PARADO

O que isso não garante no real:
- Que a câmera real enxergue a mesma distância/FOV
- Que o PID real freie na mesma distância (inércia, atrito)
- Que tags inclinadas/impressas gerem a mesma precisão de pose

---

## 7. Fluxo de dados comparado

### SIM=1 (simulador)

```
Operador clica AUTOMATICO (1x)
        │
        ▼
Control Loop @20 Hz ──► NavigationController / SegmentExecutor
        │                      │
        │                      ▼
        │               current_setpoint (ω_esq, ω_dir, garfo)
        ▼
Serial Loop (sim) ──► encode_setpoint ──► FirmwareEmulator
                                              │
                                         PID 100 Hz
                                              │
                                         SimWorld.step()
                                         (cinemática + slip)
                                              │
                                         pose (x,y,θ)
                                              │
Vision Loop (sim) ◄── SyntheticVision.compute_all(pose)
        │                      │
        │                      ▼
        │               EKF.correct_apriltag()
        ▼
Telemetria @20 Hz ──► WebSocket ──► Celular
```

### SIM=0 (robô real)

```
Operador clica AUTOMATICO (1x)
        │
        ▼
Control Loop @20 Hz          ◄── mesmo código
        │
Serial Loop (real) ──► PySerialTransport ──► ESP32 (firmware C++)
        ▲                                        │
        │                                   motores físicos
        │                                        │
Vision Loop (real) ◄── RealVisionSource ◄── câmera USB
        │                      │
        │                      ▼
        │               EKF.correct_apriltag()  ◄── mesmo código
        ▼
Telemetria @20 Hz ──► WebSocket ──► Celular  ◄── mesmo código
```

A única diferença visível para a lógica é a origem de `Sensors` (enc, mpu) e de
`VisionState` / `TagObservation`.

---

## 8. Matriz de decisão — confiança por item no real

| O que validamos no sim | Confiança no real | Ação no chão |
|------------------------|-------------------|--------------|
| Control loop roda @20 Hz sem streaming | Alta | Confirmar com 1 clique AUTOMATICO |
| PARADO latched após perda de tag | Alta | Ocultar tag fisicamente |
| Convergência a ~15 cm | Média | Medir distância real; ajustar ZREF |
| Offset lateral ~2 cm residual | Média | Pode ser pior com ruído de câmera |
| Missão pick-place (4 mapas) | Média | Recriar mapa medido |
| EKF corrige deriva entre tags | Média | Validar com tags espaçadas |
| PID Kp=20 converge sem oscilar | Baixa | Ziegler-Nichols no ESP32 |
| FOV 60° / alcance 150 cm | Baixa | Medir câmera real |
| Ruído visão ±0,2 cm | Baixa | Calibrar; ruído real provavelmente maior |
| Garfo sobe/desce com limites | Baixa | Chaves de fim-de-curso ainda não montadas (`PIN_FORK_LIMIT_*=-1` no firmware); instalar e testar quando existirem |
| Watchdog serial 200 ms | Média-alta | Desconectar USB e cronometrar |
| Wi-Fi RTT < 170 ms | Não testado | Medir com celular real |

---

## 9. Limitações conhecidas da simulação

Itens que só o hardware pode validar:

1. **Calibração de câmera** — PnP real, distorção, auto-exposure
2. **Dinâmica de motor** — dead zone L298n, aquecimento, carga no garfo
3. **Encoders NXT** — level shifter, bounce (PPR já validado na bancada 2026-07-06: 1440 com decodificação x4, que cancela transições de ruído)
4. **Patinagem** — sim usa multiplicador escalar; chão real é irregular
5. **FOV e foco** — verificar se a tag sai do FOV na reta final com a câmera real
6. **Massa do pallet** — capacidade do garfo JGY-370 (0,1 kg vs ~1 kg aberto)
7. **Alimentação** — queda de tensão ao acionar 3 motores
8. **Latência Wi-Fi** — não simulada
9. **Ambiente** — iluminação, reflexo nas tags, sombras
10. **BMS** — firmware retorna `null`; telemetria de bateria vazia

---

## 10. Plano de transição SIM → REAL

### Fase 1 — Aproveitar direto (zero código)

- [ ] Subir backend com `SIM=0`
- [ ] Frontend apontando para `VITE_PI_WS_URL`
- [ ] Gravar firmware ESP32 (mesmo protocolo testado contra emulador)
- [ ] Usar ganhos PID/NAV atuais como ponto de partida

### Fase 2 — Medir e substituir placeholders

- [x] `camera_intrinsics.json` — calibração feita em 2026-07-07 (câmera nova, 1280×720)
- [x] `ENCODER_PPR` — validado na bancada 2026-07-06 (1440, decodificação x4)
- [ ] `WHEEL_BASE_L_CM`, `WHEEL_RADIUS_R_CM` — medição da equipe 2026-07-06 (15,0 / 2,7 cm); confirmar bitola e raio por rolagem
- [ ] `CAMERA_TO_FORK_OFFSET_CM`, `APRILTAG_SIZE_CM`
- [x] Mapa JSON da arena real — `corredor_6tags_80x160` medido; remedir tags no local do desafio
- [ ] `PALLET_MASS_KG`

### Fase 3 — Re-validar os mesmos smoke tests do sim

| Teste (já feito no sim) | Repetir no real |
|-------------------------|-----------------|
| Joystick manual | sim |
| Garfo sobe/desce (fim-de-curso ainda não montado — chaves desabilitadas no firmware) | sim |
| AUTOMATICO com 1 clique | sim |
| Convergência Z ≈ 15 cm | sim — medir com fita |
| Ocultar tag → PARADO latched | sim |
| Desconectar serial → motores param | sim |
| Missão pick-place completa | sim — com mapa real |

### Fase 4 — Re-tunar o que o sim não garante

- [ ] PID Ziegler-Nichols no ESP32
- [ ] Q/R do EKF com odometria real (editar os atributos de classe em `ekf.py` — os `EKF_Q_*`/`EKF_R_*` do `config.py` não são lidos)
- [ ] `NAV_K_DIST`, `NAV_K_HEADING` para segmentos de missão
- [ ] `NAV_KZ/KX/KP_PITCH` para aproximação reativa
- [ ] FOV/alcance — ajustar `TAG_LOST_FRAMES` se necessário

---

## 11. Como continuar usando o simulador depois do bring-up

Mesmo com o robô funcionando, mantenha `SIM=1` para:

- Desenvolver novos mapas e rotas sem arriscar o hardware
- Testar regressões de navegação (`sim_sweep.py`, `full_trace.py`)
- Reproduzir bugs de missão com `POST /sim/reset-pose`
- Treinar operadores no frontend `/demo`
- CI: `pytest pi/tests/` roda sem hardware

O simulador permanece a referência de comportamento esperado. Se algo quebra no
real mas passa no sim, o diagnóstico é calibração, sensor ou parâmetro mecânico.

---

## 12. Comandos de referência

```bash
cd src

# Simulação completa
SIM=1 ./scripts/run_pi.sh
cd frontend && npm run dev    # http://localhost:5173/demo

# Testes (sem hardware)
python3 -m pytest pi/tests/ -v
python3 pi/tests/sim_sweep.py
python3 pi/tests/full_trace.py

# Hardware real
SIM=0 ./scripts/run_pi.sh

# Debug sim em runtime
curl http://localhost:8000/sim/debug-dump | jq .
curl -X POST http://localhost:8000/sim/reset-pose \
  -H "Content-Type: application/json" \
  -d '{"x": 1.0, "y": 1.5, "theta": -1.57}'
```

---

## Resumo

O simulador substitui câmera e ESP32, validou a lógica do Pi (controle, navegação,
missão, EKF, segurança, frontend) com 210 testes e cenários de convergência. No
robô real reutilizamos essa lógica, trocamos os encaixes de hardware e recalibramos
parâmetros físicos que o sim não mede.
