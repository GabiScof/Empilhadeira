# Arquitetura — Empilhadeira Robótica Autônoma

Empilhadeira robótica em escala reduzida que transporta pallets (~15 cm de lado) em
ambiente controlado. Dois modos de operação:

- **Manual:** operador comanda o robô por joystick virtual no celular.
- **Autônomo:** o robô executa missões de navegação entre AprilTags no mapa,
  posicionando-se em frente aos alvos (apenas posicionamento, não manipulação).

O garfo é sempre manual nos dois modos, num canal de comando independente.

## Missão pick-and-place com garra manual

Além do posicionamento reativo legado (aproximar de uma tag visível), o sistema
suporta uma **missão pick-and-place** completa:

1. Sorteia ou recebe dois alvos (`position_id`) do mapa carregado
2. Navega autonomamente até a tag de **pick**
3. Para e aguarda o operador acionar a garra manualmente
4. Navega até a tag de **place**
5. Aguarda novo acionamento manual da garra
6. Retorna ao ponto **home** do mapa

Detalhes da máquina de estados e da API REST em [`mission.md`](./mission.md).

## Arquitetura hierárquica de 3 camadas

```
┌─────────────────────────────────────────────────────────────────┐
│  FRONTEND — Celular (React + Vite, navegador)                   │
│  Joystick · telemetria · missão · seletor de mapa · garfo       │
└───────────────▲───────────────────────────┬─────────────────────┘
                │ (2) telemetria @20Hz       │ (1) comando
                │     WebSocket / Wi-Fi      ▼
┌───────────────┴─────────────────────────────────────────────────┐
│  RASPBERRY PI — Alto nível (Python, FastAPI + asyncio)           │
│  3 loops asyncio no startup + handler WebSocket por conexão:       │
│   • Vision Loop · Serial Loop · Control Loop                      │
│   • WebSocket Handler (FastAPI, telemetria @20 Hz por cliente)     │
│  Visão (AprilTag), EKF 2D, Kalman 1D (roll/pitch),               │
│  GyroCalibrator, cinemática, planejador de rotas,                │
│  executor de segmentos, dock-to-tag, missão pick-and-place,      │
│  máquina de estados/segurança, modelo de mundo, protocolo.       │
└───────────────▲───────────────────────────┬──────────────────────┘
                │ (4) sensores               │ (3) setpoint
                │     UART USB 115200, 20 Hz │     JSON+CRC8+\n
                │                            ▼
┌───────────────┴─────────────────────────────────────────────────┐
│  ESP32 — Baixo nível, tempo real (C++ / Arduino, PlatformIO)     │
│  PID por roda ~100 Hz · leitura encoder/MPU · PWM (LEDC)→L298n   │
│  Garfo manual + fim-de-curso local                               │
└──────────────────────────────────────────────────────────────────┘
```

Os contratos de dados entre camadas estão congelados em
[`serial-protocol.md`](./serial-protocol.md) — fonte única de verdade.

## Loops asyncio no Pi

`main.py` cria 3 `asyncio.create_task` no lifespan: Vision Loop, Serial Loop,
Control Loop. O WebSocket Handler roda por conexão via `@app.websocket("/ws")` —
não é um quarto loop no startup.

| Componente | Taxa | Responsabilidade |
|------------|------|------------------|
| **Vision Loop** | ~20 Hz | Detecção AprilTag (real ou sintética), correção EKF, cache multi-tag |
| **Serial Loop** | 20 Hz | Troca setpoint/sensores com ESP32 ou emulador, predição EKF, `GyroCalibrator`, `AttitudeKalman` (roll/pitch) |
| **Control Loop** | 20 Hz | Arbitragem (manual > missão > dock > legado), executor → setpoint, segurança |
| **WebSocket Handler** | por conexão | Comandos do frontend; sub-task `_telemetry_sender` @20 Hz por cliente |

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  WebSocket   │     │   Vision     │     │   Serial     │
│   Handler    │     │    Loop      │     │    Loop      │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │ last_command       │ correct_apriltag   │ enc + gyro(calibrado)
       │                    │ (suprimido no dock)│ ekf.predict()
       └────────────────────┼────────────────────┘
                            ▼
                   ┌─────────────────┐
                   │  Control Loop   │
                   │  MANUAL: joy→tw │
                   │  AUTO:          │
                   │   missão ativa? │──→ SegmentExecutor
                   │   dock ativo?   │──→ TagDocker
                   │   senão         │──→ NavigationCtrl
                   │  → setpoint     │
                   └────────┬────────┘
                            │ current_setpoint
                            ▼
                   Serial Loop → ESP32
```

Modo simulação (`SIM=1`): Serial Loop e Vision Loop usam emulador e visão
sintética. Ver [`simulation.md`](./simulation.md).

## Máquina de estados de missão

Estados: `IDLE → LOAD_MAP → DRAW_TARGETS → GO_TO_PICK → AT_PICK →
GO_TO_PLACE → AT_PLACE → GO_HOME → DONE`, com ramo `FAULT` a partir de
qualquer estado ativo.

| Estado | Robô | Garra |
|--------|------|-------|
| GO_TO_* / GO_HOME | Navega (SegmentExecutor) | Manual (operador) |
| AT_PICK / AT_PLACE | Parado | Operador aciona + clica "continuar" |
| FAULT | Telemetria registra a falha e as rodas zeram no tick do fault, mas o control loop não bloqueia AUTOMATICO: com a missão inativa, o ramo cai no dock-to-tag (ou legado) no tick seguinte — operador deve resetar a missão ou mudar de modo. | — |

Prioridade de alvos: argumento explícito (UI/REST) > defaults `MISSION_DEFAULT_PICK_ID="L3"` / `MISSION_DEFAULT_PLACE_ID="R1"` (hardcoded em `config.py`) > sorteio com `_seed=42` (hardcoded em `mission_sm.py`; o `MISSION_SEED` de `config.py` não é lido pela SM).

Implementação: `pi/app/mission/mission_sm.py`. Ver [`mission.md`](./mission.md).

## Dock-to-tag (modo padrão de AUTOMATICO sem missão)

Desde 2026-07-07 (`DOCK_TO_TAG_ENABLED = True` hardcoded), o ramo AUTOMATICO
sem missão usa o `TagDocker` em vez do navegador legado. O legado só roda se
o dock for desligado em runtime (`POST /dock/disable`).

O dock vê 1 tag, planeja **uma vez** com Manhattan no **frame do robô** (não
nos eixos do mapa — escolha estranha, mas funciona sem mapa), e executa os
segmentos pelo EKF. Detalhes em [`dock-to-tag.md`](./dock-to-tag.md).

Diferença da missão: o dock usa `_plan_steps()` (Manhattan relativo ao robô:
avança no heading, gira ±90°, avança, gira final), enquanto a missão usa
`plan_route()` (A*/Manhattan nos eixos do mapa).

Durante dock ativo, correções EKF por tag são **suprimidas** (`vision_loop.py`
pula `correct_apriltag()` quando `state.docker.is_docking`) — a execução é
pura odometria. Essa é outra escolha estranha: foi feita para evitar saltos de
pose durante a aproximação curta, mas significa que a precisão depende da
qualidade da predição.

Estados: `SEEKING → DOCKING → DONE` (+ `FAULT` por timeout). Em `DONE` o docker
continua observando: se uma nova detecção gerar um alvo a mais de 0,10 m
(`_REPLAN_MIN_TRAVEL_M` — tag movida, tag nova ou robô deslocado), re-planeja
automaticamente.

## Malha em cascata de controle

```
Pose alvo (mapa)
      ↓
PathPlanner → [FORWARD, TURN, ...]
      ↓
SegmentExecutor  ─── malha EXTERNA (Pi ~20 Hz)
  pose EKF → (v, ω) → (ω_esq, ω_dir)
      ↓ setpoint serial
ESP32 PID por roda ─── malha INTERNA (~100 Hz)
  ω_medido (encoder) → duty PWM → motor
```

- **Externa:** posição e heading → velocidades de roda desejadas
- **Interna:** velocidade de roda → PWM (não duplicar PID no Pi)

Detalhes em [`navigation.md`](./navigation.md).

## EKF 2D — [x, y, θ]

EKF para pose no plano. O `AttitudeKalman` (1D, roll/pitch) continua rodando
em paralelo no `serial_loop.py` para a telemetria da UI — são filtros separados.

| Fase | Fonte | Módulo |
|------|-------|--------|
| Predição | Encoders + giroscópio Z (pós-`GyroCalibrator`: bias, auto-orientação de eixo) | `serial_loop.py` → `ekf.predict()` |
| Correção | AprilTag (PnP → pose no mundo) | `vision_loop.py` → `ekf.correct_apriltag()` |
| Gating | Distância de Mahalanobis > 3.0 descartada | `ekf.py` |

Fusão gyro/odom: `omega = 0.7*gyro + 0.3*odom` (hardcoded `alpha_gyro=0.7` em
`ekf.py`, não vem de `config.EKF_*` — esses existem em `config.py` mas não são
lidos pelo EKF; valores duplicados).

Q é dinâmico: escala com velocidade e giro via `speed_factor`/`turn_factor`/`dt`.
R é escalonado pela `quality` da detecção (mín. 0.1). Covariância 3×3, não 2×2.

Exceção durante dock: `vision_loop.py` **não** chama `correct_apriltag()` quando
`state.docker.is_docking` — execução em pura odometria.

Estado em SI (m, rad). Telemetria exporta elipse 2D para a UI.

## Modelo de mundo paramétrico

A arena não é hardcoded — é carregada de arquivo JSON em `pi/maps/`:

```
pi/maps/*.json  →  ArenaMap (Pydantic)  →  WorldModel
```

Expõe dimensões da arena, tags (`position_id`, pose), `start_pose`, `home_pose`
e grafo opcional de waypoints. Trocar mapa = trocar arena/missão sem alterar
código.

- Schema: `pi/app/world/map_schema.py`
- Fachada: `pi/app/world/world_model.py`
- Documentação: [`maps.md`](./maps.md)

## Decisões de projeto

- Arquitetura hierárquica de 3 camadas: Frontend → Pi → ESP32.
- Raspberry Pi em Python. Backend assíncrono com FastAPI + `asyncio`,
  3 loops no startup + handler WebSocket por conexão.
- ESP32 em C++ (Arduino, PlatformIO). PID a ~100 Hz e determinismo de tempo real.
- Frontend em React + Vite (navegador do celular).
- Frontend ↔ Pi: WebSocket full-duplex sobre Wi-Fi local.
- Pi ↔ ESP32: UART USB, 115200 baud, 20 Hz, framing JSON + CRC8(hex) + `\n`.
- Garfo sempre manual — sem atuação autônoma no protocolo serial.
- Monorepo com três apps (`pi/`, `firmware/`, `frontend/`) + `docs/` + `scripts/`.
- Mapas em JSON — arena paramétrica, não hardcoded.

## Parâmetros em aberto

Não atribuir valores por conta própria. Cada parâmetro pendente existe como
constante nomeada com placeholder marcado e `TODO(equipe)`; alguns já foram
definidos e estão indicados abaixo.

| Parâmetro | Onde mora | Observação |
|---|---|---|
| Massa real do pallet | `pi/app/config.py` | Intro do relatório diz ~1 kg, mas o cálculo do garfo usou 0,1 kg. Inconsistência aberta. |
| Versão do motor do garfo (torque) | `config` + docs | Depende da massa real; versão 40 rpm pode estar subdimensionada. |
| Modelo do Raspberry Pi | este arquivo | Decide FPS de visão e orçamento de energia. `TODO(equipe)`. |
| `L` (distância entre rodas), `r` (raio da roda) | `pi/app/config.py` | Cinemática diferencial. |
| Ganhos PID (`Kp, Ki, Kd`) por roda | `firmware/src/config.h` | Sintonia inicial Ziegler-Nichols, depois empírica. |
| Ganhos malha externa (`NAV_K_DIST`, `NAV_K_HEADING`) | `pi/app/config.py` | Valores atuais 1,5 e 2,5; sintonia fina pendente. |
| Ganhos navegação legado (`Kz, Kx, Kp_pitch`) | `pi/app/config.py` | Modo automático reativo. |
| `Zref` (distância de parada) | `pi/app/config.py` | ~15 cm provisório; depende do comprimento do garfo. |
| Ruído EKF (`EKF_Q_*`, `EKF_R_*`) | `pi/app/config.py` | Fusão odometria + tag. Não conectados: o EKF usa atributos de classe hardcoded em `ekf.py` (`Q_BASE_XY=0.001`, `Q_BASE_THETA=0.002`, `R_XY=0.01`, `R_THETA=0.05`); os `EKF_*` de config são duplicatas não lidas. |
| Intrínsecos da câmera (`fx, fy, cx, cy`) | `pi/calibracao/camera_intrinsics.json` | Definidos: recalibração de 2026-07-07 (1280×720). Ver [`camera-calibration.md`](./camera-calibration.md). |
| Tamanho físico da AprilTag | `pi/app/config.py` | Necessário para a pose. |
| Offset extrínseco câmera→garfo | `pi/app/config.py` + docs | Alinhar a câmera ≠ alinhar o garfo. |
| Timeout "manter último setpoint" (ESP32) | `firmware/src/config.h` | Definido: `SETPOINT_TIMEOUT_MS = 200` ms. |
| `MISSION_RESUME_TRIGGER` | `pi/app/config.py` | Botão vs. fim-de-curso. |
| Access Point Wi-Fi (Pi ou roteador) | este arquivo | Afeta o RTT alvo < 170 ms. `TODO(equipe)`. |

### Definições pendentes de infraestrutura (`TODO(equipe)`)

- **Modelo do Raspberry Pi:** a definir. Impacta FPS de visão e energia.
- **Access Point Wi-Fi:** a definir se o AP é o próprio Pi ou um roteador externo.
  Meta de RTT comando→ação < 170 ms.

## Restrições de engenharia a respeitar

- A cinemática assume rodas sem escorregamento; a odometria por encoder degrada
  se patinar.
- Estimar pitch de uma única tag pequena tem ambiguidade de pose conhecida.
- A tag pode sair do FOV ou sair de foco na reta final (Z pequeno); missão e
  dock ignoram tag-loss (bypassam segurança), legado para em `PARADO`.
- Em modo automático legado, `ω = Kx·X + Kp·Pitch` pode acoplar os dois termos;
  `NavigationController` tem fases (COARSE_ALIGN, APPROACH, FACE, RETREAT) com
  fallback de oscilação, não a fórmula simples — ver `navigation.py`.
- O canal de comando (WebSocket) tem watchdog de 400 ms: se cair no modo
  manual com o robô andando, o robô para (mas missão ativa anula o efeito).
- Navegação por mapa depende de correções EKF por tag — deriva de odometria
  entre detecções é esperada.

## Estado seguro / watchdogs

O sistema inicia em `PARADO` (`state_machine.py`). Transições de segurança
usam um **latch**: `PARADO` por segurança trava até `acknowledge()` explícito
(comando MANUAL ou AUTOMATICO via WebSocket). Exceção: missão e dock ativos
chamam `acknowledge()` automaticamente no tick seguinte.

Razões de parada expostas na telemetria (`parado_reason`): `tag_loss`,
`command_watchdog`, `ws_disconnect`, `serial_loss`, `force_stop`.

| Watchdog | Valor | Condição | Efeito |
|----------|-------|----------|--------|
| **Setpoint ESP32** | `SETPOINT_TIMEOUT_MS = 200` ms | Sem setpoint novo | ESP32 zera motores |
| **Comando (Pi)** | `COMMAND_WATCHDOG_MS = 400` ms | MANUAL + rodas em movimento + sem comando novo | Pi força `PARADO` |
| **Serial loss (Pi)** | `SERIAL_LOST_FRAMES = 5` (~250 ms @20 Hz) | Sem sensor frames do ESP32 | Pi força `PARADO` (defesa em profundidade) |
| **Tag-loss (Pi)** | `TAG_LOST_FRAMES = 5` (>5 frames = 6 frames ≈ 300 ms @20 Hz) | AUTOMATICO legado sem tag visível | Pi força `PARADO` |
| **Timeout de segmento** | `NAV_MAX_SEGMENT_TIME_S = 45` s | Segmento não completo | Missão → FAULT; Dock → FAULT |
| **WebSocket disconnect** | imediato | Qualquer modo | `force_stop("ws_disconnect")` |

Tag-loss e ws_disconnect são **bypassed** durante missão/dock ativos:
`control_loop.py` injeta `VisionState(detectado=True)` e auto-chama
`acknowledge()`, fazendo o robô continuar navegando sem intervenção. Isso
significa que ws disconnect só para o robô de forma confiável **sem missão
ativa** — com missão, o latch é auto-liberado no tick seguinte.

## Documentação relacionada

| Arquivo | Conteúdo |
|---------|----------|
| [readiness-sim-to-real.md](./readiness-sim-to-real.md) | Auditoria SIM→real |
| [simulator-to-real.md](./simulator-to-real.md) | Sim → real — o que aproveitamos |
| [hardware-deployment.md](./hardware-deployment.md) | Deploy no robô real — passo a passo |
| [verification-status.md](./verification-status.md) | Testes, bugs corrigidos, sim_sweep |
| [`mission.md`](./mission.md) | Missão pick-and-place, API, garra manual |
| [`maps.md`](./maps.md) | Formato JSON dos mapas da arena |
| [`navigation.md`](./navigation.md) | Planejador, executor, malha em cascata |
| [`dock-to-tag.md`](./dock-to-tag.md) | Aproximação a 1 tag sem missão |
| [`simulation.md`](./simulation.md) | Modo SIM=1, falhas, testes |
| [`hardware-bring-up.md`](./hardware-bring-up.md) | Pinos, energia, calibração |
| [`serial-protocol.md`](./serial-protocol.md) | Contratos de comunicação |
| [`camera-calibration.md`](./camera-calibration.md) | Calibração da câmera |
