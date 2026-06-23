# Arquitetura — Empilhadeira Robótica Autônoma

[ref: Seções 1, 2, 3 e 4 da AGENTS.md]

## Visão geral

Empilhadeira robótica em escala reduzida que transporta pallets (~15 cm de lado) em
ambiente controlado. Dois modos de operação:

- **Manual:** operador comanda o robô por joystick virtual no celular.
- **Autônomo:** o robô executa missões de navegação entre AprilTags no mapa,
  posicionando-se em frente aos alvos (**apenas posicionamento**, não manipulação).

O **garfo é sempre manual** nos dois modos, num canal de comando independente.

### Missão pick-and-place com garra manual

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
│  4 tarefas concorrentes:                                         │
│   • WebSocket Handler   • Vision Loop                            │
│   • Serial Loop         • Control Loop                           │
│  Visão (AprilTag), EKF 2D, cinemática, planejador de rotas,      │
│  executor de segmentos, máquina de missão, máquina de estados,   │
│  modelo de mundo paramétrico, protocolo (JSON+CRC8).             │
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

## Quatro tarefas asyncio no Pi

| Tarefa | Taxa | Responsabilidade |
|--------|------|------------------|
| **WebSocket Handler** | evento | Comandos do frontend, telemetria @20 Hz |
| **Vision Loop** | ~20 Hz | Detecção AprilTag (real ou sintética), correção EKF |
| **Serial Loop** | 20 Hz | Troca setpoint/sensores com ESP32 ou emulador, predição EKF |
| **Control Loop** | 20 Hz | Missão → planejador → executor → setpoint; segurança |

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  WebSocket   │     │   Vision     │     │   Serial     │
│   Handler    │     │    Loop      │     │    Loop      │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │ last_command       │ last_vision        │ enc + IMU
       │                    │ correct_apriltag   │ ekf.predict()
       └────────────────────┼────────────────────┘
                            ▼
                   ┌────────────────┐
                   │  Control Loop  │
                   │  mission → nav │
                   │  → setpoint    │
                   └────────┬───────┘
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
| FAULT | Motores zerados | — |

Implementação: `pi/app/mission/mission_sm.py`. Especificação completa em
[`mission.md`](./mission.md).

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

Substitui o filtro de atitude (roll/pitch) para navegação no plano.

| Fase | Fonte | Módulo |
|------|-------|--------|
| Predição | Odometria (encoders) + giroscópio Z | `serial_loop.py` → `ekf.predict()` |
| Correção | AprilTag (PnP → pose no mundo) | `vision_loop.py` → `ekf.correct_apriltag()` |
| Gating | Distância de Mahalanobis ≤ 3σ | `ekf.py` |

Estado interno em SI (m, rad). A telemetria exporta elipse de covariância 2D
para visualização na UI.

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

## Decisões fechadas (não rediscutir) — [ref: Seção 2]

- Arquitetura **hierárquica de 3 camadas**: Frontend → Pi → ESP32.
- **Raspberry Pi em Python.** Backend assíncrono único com **FastAPI** + `asyncio`,
  **quatro** tarefas concorrentes (WebSocket Handler, Vision Loop, Serial Loop,
  Control Loop).
- **ESP32 em C++ (Arduino, PlatformIO).** PID a ~100 Hz e determinismo de tempo real.
- **Frontend em React + Vite** (navegador do celular).
- **Frontend ↔ Pi:** WebSocket full-duplex sobre Wi-Fi local.
- **Pi ↔ ESP32:** UART USB, **115200 baud**, **20 Hz**, framing **JSON + CRC8(hex) + `\n`**.
- **Garfo sempre manual** — sem atuação autônoma no protocolo serial.
- **Monorepo** com três apps (`pi/`, `firmware/`, `frontend/`) + `docs/` + `scripts/`.
- **Mapas em JSON** — arena paramétrica, não hardcoded.

## Parâmetros em aberto — NÃO INVENTAR VALOR — [ref: Seção 3]

Cada um existe como **constante nomeada** com placeholder marcado e `TODO(equipe)`.

| Parâmetro | Onde mora | Observação |
|---|---|---|
| Massa real do pallet | `pi/app/config.py` | Intro do relatório diz ~1 kg, mas o cálculo do garfo usou 0,1 kg. **Inconsistência aberta.** |
| Versão do motor do garfo (torque) | `config` + docs | Depende da massa real; versão 40 rpm pode estar subdimensionada. |
| Modelo do Raspberry Pi | este arquivo | Decide FPS de visão e orçamento de energia. **`TODO(equipe)`**. |
| `L` (distância entre rodas), `r` (raio da roda) | `pi/app/config.py` | Cinemática diferencial. |
| Ganhos PID (`Kp, Ki, Kd`) por roda | `firmware/src/config.h` | Sintonia inicial Ziegler-Nichols, depois empírica. |
| Ganhos malha externa (`NAV_K_DIST`, `NAV_K_HEADING`) | `pi/app/config.py` | Segment executor. |
| Ganhos navegação legado (`Kz, Kx, Kp_pitch`) | `pi/app/config.py` | Modo automático reativo. |
| `Zref` (distância de parada) | `pi/app/config.py` | ~15 cm provisório; depende do comprimento do garfo. |
| Ruído EKF (`EKF_Q_*`, `EKF_R_*`) | `pi/app/config.py` | Fusão odometria + tag. |
| Intrínsecos da câmera (`fx, fy, cx, cy`) | `pi/calibracao/camera_intrinsics.json` | Saída da calibração (xadrez / 3DF Zephyr). |
| Tamanho físico da AprilTag | `pi/app/config.py` | Necessário para a pose. |
| Offset extrínseco câmera→garfo | `pi/app/config.py` + docs | Alinhar a câmera ≠ alinhar o garfo. |
| Timeout "manter último setpoint" (ESP32) | `firmware/src/config.h` | Antes de cair em estado seguro. |
| `MISSION_RESUME_TRIGGER` | `pi/app/config.py` | Botão vs. fim-de-curso. |
| Access Point Wi-Fi (Pi ou roteador) | este arquivo | Afeta o RTT alvo < 170 ms. **`TODO(equipe)`**. |

### Definições pendentes de infraestrutura (`TODO(equipe)`)

- **Modelo do Raspberry Pi:** _a definir._ Impacta FPS de visão e energia.
- **Access Point Wi-Fi:** _a definir_ se o AP é o próprio Pi ou um roteador externo.
  Meta de RTT comando→ação < **170 ms**.

## Restrições de engenharia a respeitar — [ref: Seção 4]

- A cinemática assume rodas **sem escorregamento**; a odometria por encoder degrada
  se patinar.
- Estimar **Pitch** de uma única tag pequena tem **ambiguidade de pose** conhecida.
- A tag pode **sair do FOV / sair de foco** na reta final (Z pequeno); a aproximação
  precisa lidar com perda de detecção perto do alvo.
- Em modo automático legado, `ω = Kx·X + Kp·Pitch` pode **acoplar/brigar**; prever fallback.
- O canal de comando (WebSocket) precisa de **watchdog próprio**: se cair no modo
  manual com o robô andando, o robô deve **parar**, não manter o último comando.
- Navegação por mapa depende de **correções EKF por tag** — deriva de odometria
  entre detecções é esperada.

## Estado seguro / watchdogs — [ref: Seção 7]

- **Serial cai** → ESP32 zera os motores (após `SETPOINT_TIMEOUT_MS`).
- **Comando (WebSocket) cai no manual** → Pi força `PARADO`.
- **Missão em FAULT** → motores zerados, UI sinaliza falha.
- **Segmento timeout** (30 s) → missão transiciona para FAULT.

## Documentação relacionada

| Arquivo | Conteúdo |
|---------|----------|
| [**readiness-sim-to-real.md**](./readiness-sim-to-real.md) | **Auditoria completa SIM→real** |
| [**simulator-to-real.md**](./simulator-to-real.md) | Sim → real — o que aproveitamos |
| [**hardware-deployment.md**](./hardware-deployment.md) | **Deploy no robô real** — passo a passo, o que falta |
| [verification-status.md](./verification-status.md) | Testes, bugs corrigidos, sim_sweep |
| [`mission.md`](./mission.md) | Missão pick-and-place, API, garra manual |
| [`maps.md`](./maps.md) | Formato JSON dos mapas da arena |
| [`navigation.md`](./navigation.md) | Planejador, executor, malha em cascata |
| [`simulation.md`](./simulation.md) | Modo SIM=1, falhas, testes |
| [`hardware-bring-up.md`](./hardware-bring-up.md) | Pinos, energia, calibração |
| [`serial-protocol.md`](./serial-protocol.md) | Contratos de comunicação |
| [`camera-calibration.md`](./camera-calibration.md) | Calibração da câmera |
