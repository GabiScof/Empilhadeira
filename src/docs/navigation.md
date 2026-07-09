# Navegação Autônoma

Módulos: `path_planner.py`, `segment_executor.py`, `ekf.py`, `control_loop.py`.

A navegação da missão pick-and-place opera em duas malhas em cascata:

1. **Malha externa (Pi, ~20 Hz):** posição e heading → `(v, ω)` → `(ω_esq, ω_dir)`
2. **Malha interna (ESP32, ~100 Hz):** velocidade por roda via PID

O Pi não duplica o PID de roda — envia setpoints de velocidade angular
e o ESP32 fecha a malha de velocidade.

## Malha em Cascata

```
┌─────────────────────────────────────────────────────────────────┐
│  Raspberry Pi — Control Loop @ 20 Hz (control_loop.py)          │
│                                                                 │
│  EKF [x,y,θ] ──► SegmentExecutor ──► cinemática inversa         │
│       ▲              (malha externa)         │                    │
│       │                                    (ω_esq, ω_dir)       │
│  odometria + tag                           │                    │
└────────────────────────────────────────────┼────────────────────┘
                                             │ Setpoint JSON+CRC8
                                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  ESP32 — PID por roda @ ~100 Hz (firmware/src/main.cpp)         │
│                                                                 │
│  ω_medido (encoder) ──► PID ──► PWM ──► L298n ──► motor         │
│       ▲                                                         │
│  setpoint ω_esq/ω_dir @ 20 Hz                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Frequências e Responsabilidades

| Camada | Taxa | Entrada | Saída | Módulo |
|--------|------|---------|-------|--------|
| Externa | ~20 Hz | pose EKF + segmento alvo | `ω_esq`, `ω_dir` | `segment_executor.py` |
| Interna | ~100 Hz | `ω_esq`, `ω_dir` setpoint + encoder | duty PWM | `firmware/pid.cpp` |

O **Control Loop** (`control_loop.py`) orquestra missão → planejador → executor
e aplica a máquina de estados de segurança antes de publicar o setpoint.

## Planejador de Rotas (`path_planner.py`)

O planejador converte uma pose inicial e um alvo em uma lista ordenada de
segmentos executáveis.

### Tipos de Segmento

| Tipo | `value` | Descrição |
|------|---------|-----------|
| `FORWARD` | distância (m) | Avançar até `(target_x, target_y)` |
| `TURN` | ângulo (rad) | Girar in-place até `target_heading` |

### Estratégia 1 — Grafo (A*)

Quando o mapa possui `waypoints` e `edges`:

1. Encontra o waypoint mais próximo da pose atual e do alvo
2. Roda **A\*** sobre o grafo bidirecional
3. Converte a sequência de waypoints em segmentos FORWARD/TURN

Usado em arenas com corredores e restrições (ex.: `arena_grande_com_grafo`).

### Estratégia 2 — Manhattan (arena aberta)

Sem grafo, ou se A* falhar:

1. Calcula ponto intermediário `(goal_x, start_y)` — alinha eixo X primeiro
2. Depois avança em Y até `(goal_x, goal_y)`
3. Gira para `goal_heading` final, se especificado

### Giros de Ângulo Livre

Os segmentos `TURN` aceitam qualquer ângulo no intervalo `[-π, π]`.
Não há restrição a múltiplos de 90° — o robô gira in-place até atingir
`target_heading` com tolerância `NAV_HEADING_TOL_RAD` (0.07 rad, ~4°).

Threshold mínimo de giro: ~1° (`0.02 rad`) — giros menores são ignorados.

## Executor de Segmentos (`segment_executor.py`)

Executa a lista de segmentos produzida pelo planejador, um de cada vez.

### Malha FORWARD

Para cada segmento de avanço:

- Calcula distância ao alvo `(target_x, target_y)`
- Calcula erro de heading em direção ao alvo
- Se `|heading_error| > 45°`, para (`v = 0`) e corrige orientação primeiro
- Converte `(v, ω)` em `(ω_esq, ω_dir)` via cinemática inversa

### Malha TURN

Para cada segmento de giro:

- `v = 0` (gira in-place)
- `ω` proporcional ao erro de heading (ou velocidade fixa de fallback)
- Conclui quando `|heading_error| < HEADING_TOL_RAD`

### Estados do Executor

| Estado | Significado |
|--------|-------------|
| `IDLE` | Sem rota carregada |
| `RUNNING` | Executando segmento atual |
| `SEGMENT_DONE` | Segmento concluído (transitório) |
| `ROUTE_DONE` | Todos os segmentos concluídos → missão avança |
| `TIMEOUT` | Segmento excedeu `NAV_MAX_SEGMENT_TIME_S` (45 s) → FAULT |

### Ganhos

- `NAV_K_DIST = 1.5` — ganho proporcional distância → v (cap em `MAX_LINEAR_SPEED_MS`)
- `NAV_K_HEADING = 2.5` — ganho proporcional heading → ω (cap em `MAX_ANGULAR_SPEED_RADS`)

Se ambos forem zerados, o executor cai para velocidades fixas de fallback
(`NAV_FALLBACK_V_MS = 0.08 m/s`, `NAV_FALLBACK_OMEGA_RADS = 1.0 rad/s`).

### Anti-atrito estático (fix de bancada 2026-07-07)

A malha proporcional comanda velocidades minúsculas perto do alvo e o chão
engole (roda zumbe, robô parado). Pisos aplicados fora da tolerância:

- `NAV_MIN_V_MS = 0.09 m/s` — acima da zona de stick-slip
- `NAV_MIN_OMEGA_RADS = 1.0 rad/s` — skid-steer exige torque mínimo
- `NAV_TURN_MAX_OMEGA_RADS = 1.6 rad/s` — teto de giro; acima as rodas
  derrapam, a odometria conta rotação que não houve e o EKF sai torto

## EKF 2D — Feedback de Pose

Estado: **x = [x, y, θ]** em metros e radianos.

| Fase | Fonte | Descrição |
|------|-------|-----------|
| Predição | Odometria + giroscópio | Cinemática diferencial a cada tick serial (~20 Hz) |
| Correção | AprilTag (PnP) | Fix absoluto quando tag conhecida detectada |
| Gating | Mahalanobis | Rejeita correções com distância > 3σ |

Fusão de heading: média ponderada 70% giroscópio + 30% odometria
(`alpha_gyro = 0.7`, `TODO(equipe)` calibrar).

Ver `pi/app/control/ekf.py` para Jacobiano, matrizes Q/R e elipse de
covariância exportada para a UI.

## Modo AUTOMATICO sem missão

O control loop decide entre dois controladores quando não há missão ativa:

| Condição | Controlador |
|----------|-------------|
| dock ligado (default desde 2026-07-07, hardcoded `True`) | `TagDocker` — estaciona em frente a uma tag por segmentos discretos (FORWARD/TURN) usando o SegmentExecutor + EKF. Ver [`dock-to-tag.md`](./dock-to-tag.md). |
| dock desligado (via `POST /dock/disable`) | `NavigationController` legado — servo contínuo reativo à tag visível (`v = Kz·(Z−Zref)`, `ω = Kx·X + Kp·Pitch`) |

O navegador legado cobre posicionamento fino em frente a uma única tag — não
navega entre waypoints do mapa.

## Limitações Conhecidas

| Limitação | Impacto | Mitigação |
|-----------|---------|-----------|
| Odometria assume ausência de escorregamento | Deriva acumulada entre tags | Correções EKF por AprilTag |
| Ganhos externos sensíveis ao piso | Derrapagem em giro rápido; estagnação em baixa velocidade | Anti-atrito (pisos) + teto de giro (1,6 rad/s) |
| Manhattan ignora obstáculos | Rota pode cruzar paredes em arena aberta | Usar grafo de waypoints |
| A* usa waypoints discretos | Rota subótima vs. contínua | Adicionar waypoints intermediários |
| Timeout de 45 s por segmento | FAULT em corredores longos | Ajustar `NAV_MAX_SEGMENT_TIME_S` |
| Sem replanejamento dinâmico | Obstáculo novo não desvia rota | Fora de escopo desta fase |
| Erro de heading > 45° para avanço | Robô para para realinhar | Comportamento intencional |
| Tag fora do FOV durante navegação | EKF depende só de odometria | Tags nos pontos de parada ajudam |

## Parâmetros Relevantes (`config.py`)

| Constante | Default | Unidade | Descrição |
|-----------|---------|---------|-----------|
| `CONTROL_HZ` | 20 | Hz | Taxa do control loop |
| `NAV_POS_TOL_M` | 0.02 | m | Tolerância de posição |
| `NAV_HEADING_TOL_RAD` | 0.07 | rad | ~4° — folga para o piso de ω não oscilar (era 2°, alargado na bancada) |
| `NAV_MAX_SEGMENT_TIME_S` | 45 | s | Timeout por segmento (margem para corredores longos) |
| `NAV_K_DIST` | 1.5 | — | Ganho distância → v |
| `NAV_K_HEADING` | 2.5 | — | Ganho heading → ω |
| `NAV_MIN_V_MS` | 0.09 | m/s | Piso de v (anti-atrito estático) |
| `NAV_MIN_OMEGA_RADS` | 1.0 | rad/s | Piso de ω (torque mínimo para skid) |
| `NAV_TURN_MAX_OMEGA_RADS` | 1.6 | rad/s | Teto de ω em TURN (evita derrapagem) |
| `WHEELBASE_M` | 0.15 | m | Distância entre rodas |
| `WHEEL_RADIUS_M` | 0.027 | m | Raio da roda (medição da equipe 2026-07-06; confirmar por rolagem) |
| `MAX_LINEAR_SPEED_MS` | 0.19 | m/s | Saturação de v (medido na bancada 2026-07-06: 24 cm/s em velocidade máxima; gravado a 80%) |
| `MAX_ANGULAR_SPEED_RADS` | 2.5 | rad/s | Saturação de ω (derivado do teto físico 2·24/15 ≈ 3,2 × 0,8; provisório até cronometrar o giro) |

## Testes

| Arquivo | Cobertura |
|---------|-----------|
| `test_path_planner.py` | A*, Manhattan, segmentos |
| `test_navigation.py` | NavigationController legado |
| `test_integration_mission.py` | Missão completa em SIM |
| `sim_trace.py` / `full_trace.py` | Trajetórias registradas |
