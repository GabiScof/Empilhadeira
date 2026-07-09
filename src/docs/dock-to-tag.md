# Dock-to-Tag — Aproximação por Segmentos a uma Tag

Módulos: `control/dock_to_tag.py`, `tasks/control_loop.py`.

Modo padrão do ramo AUTOMATICO sem missão (desde 2026-07-07) para o cenário
mais simples de navegação autônoma no robô real: ligar o robô, ver uma
AprilTag e estacionar de frente para ela, usando movimento discreto por
segmentos (avança / gira 90°), não o servo contínuo.

É a mesma malha de execução da missão (`SegmentExecutor`), disparada por uma tag
avulsa em vez de um alvo do mapa — e sem o ciclo pick/place/home. Não exige
que a tag esteja no mapa. Consome as mesmas leituras (`z_cm`/`x_cm`/`pitch_deg`)
que o navegador legado já usa no hardware.

## Diferença para os dois modos existentes

| | Automático legado | Missão | Dock-to-tag |
|---|---|---|---|
| Controlador | `NavigationController` | `SegmentExecutor` | `SegmentExecutor` |
| Realimentação | visão (tag) contínua | pose do EKF | pose do EKF |
| Movimento | servo reativo suave | segmentos FORWARD/TURN | segmentos FORWARD/TURN |
| Disparo | ver a tag | iniciar missão (≥2 tags) | ver 1 tag |

O dock planeja uma vez ao ver a tag e executa a rota pela odometria do EKF
(como a missão) — tolera perder a tag do FOV durante uma curva de 90°.

## Como ligar e testar (robô real)

Hardcoded ligado desde 2026-07-07 (o env desligado a cada restart derrubava o
AUTOMATICO no caminho legado). Caminho padrão do AUTOMATICO-sem-missão.
Desligável em runtime pela interface (não precisa reiniciar):

Pela interface: painel "Aproximar de uma tag" (abaixo do
seletor de modo, na tela do Operador ou Demo), toque em "Ligar
aproximação por tag" → selecione AUTOMATICO → mostre uma tag ao robô. O
painel mostra o estado (Procurando / Aproximando / Estacionado). Para re-aproximar
outra tag: volte a MANUAL/PARADO e selecione AUTOMATICO de novo.

Pela API (equivalente ao botão):

| Rota | Efeito |
|---|---|
| `POST /dock/enable` (body `{}` ou `{"mode","standoff_m"}`) | liga o dock |
| `POST /dock/disable` | desliga |
| `GET /dock/state` | estado atual |

Na inicialização:

```bash
python -m app.main   # dock já sobe ligado (hardcoded True)
```

A rota planejada aparece em `planned_path` e o rastro em `executed_trail` (mesma
visualização da missão); o estado do dock vai na telemetria (`telemetry.dock`).

Vista de cima no robô real: a tela `/demo` desenha a arena (robô + tags +
rota) também no hardware, via `GET /world-state` (pose do EKF + mapa) —
substitui o `/sim/world-state`, exclusivo da simulação. Carregue um mapa
antes (sem mapa não há dimensões de arena para desenhar, e o EKF roda só na
odometria). Com mapa, as tags corrigem o EKF e a vista fica igual à da missão.

### Configuração

| Constante | Default | Efeito |
|---|---|---|
| `DOCK_TO_TAG_ENABLED` | `True` (hardcoded) | Ligado por padrão desde 2026-07-07. Não vem de env — desligável em runtime via `POST /dock/disable`. |
| `DOCK_MODE` | `line_of_sight` | Estratégia de alvo — ver abaixo. |
| `DOCK_STANDOFF_M` | `0.15` | Distância de parada em frente à tag (m). |
| `DOCK_MIN_DETECTIONS` | `3` | Detecções consecutivas antes de planejar (anti-ruído). |
| `DOCK_PITCH_TO_TAG_YAW_OFFSET_RAD` | `π` (hardcoded) | Convenção de yaw — usado somente por `tag_normal`. Hardcoded π desde 2026-07-07 (convenção unificada sim/real após negação do pitch na fronteira). O modo `line_of_sight` ignora este valor. |

## Estratégias de alvo (`DOCK_MODE`)

### `line_of_sight` (default — recomendado para o robô real)

Para o robô `DOCK_STANDOFF_M` antes da tag, sobre a reta robô→tag, de frente
para ela. Usa apenas `z_cm`/`x_cm` (distância + rumo) — grandezas bem
definidas, idênticas às que o navegador legado já usa e valida no hardware.

Não depende da convenção de yaw da tag — seguro no robô real sem calibração
extra. Não quadra com a face da tag: para na direção em que a tag foi vista.

### `tag_normal` (opcional)

Quadra com a face da tag (aproxima pela normal da face), como a missão faz.
Mais preciso para encostar num pallet/estante. Depende do yaw da tag, que vem
de `pitch_deg`.

O offset é π nos dois mundos (convenção unificada desde 2026-07-07: o pitch da
câmera real é negado na fronteira em `pose.py`, ficando na mesma convenção da
visão sintética). Tag de frente: pitch=0 → yaw da tag = θ_robô + π. Se a
aproximação chegar espelhada, o sinal da negação em `pose.py` mudou — conferir.
A posição do alvo não depende disso — só a orientação final.

## Máquina de Estados

```
SEEKING → (N detecções estáveis, planeja) → DOCKING → (rota concluída) → DONE
   │                                            │
   └────────────── qualquer ────────────────────┴──→ FAULT (timeout de segmento)
```

- **SEEKING**: robô parado; acumula detecções. Ao atingir `DOCK_MIN_DETECTIONS`,
  calcula o alvo (conforme `DOCK_MODE`) e planeja com `_plan_steps()` — Manhattan
  **no frame do robô** (avança no heading atual, gira ±90°, avança lateral, gira
  para o alvo), **não** `plan_route()` que a missão usa nos eixos do mapa. Escolha
  deliberada: funciona sem mapa carregado, mas gera rotas menos eficientes que
  o A* do grafo.
- **DOCKING**: executa os segmentos via EKF. Correções EKF por AprilTag são
  **suprimidas** durante esta fase (`vision_loop.py` pula `correct_apriltag()`
  quando `state.docker.is_docking`) — execução é pura odometria. Razão: evitar
  saltos de pose durante aproximação curta. Consequência: a precisão de chegada
  depende da qualidade da predição (encoders + giroscópio calibrado).
- **DONE**: robô parado, mas continua observando. Se mover > 0,10 m (`_REPLAN_MIN_TRAVEL_M`),
  re-planeja automaticamente para a tag mais recente.
- **FAULT**: timeout de segmento (45 s) ou erro; robô parado.

## Geometria

`line_of_sight` (sem yaw):

```
z, x  = z_cm/100, x_cm/100
dist  = hypot(z, x)
bearing = rθ + atan2(x, z)
reach = max(dist − standoff, 0)
goal  = (rx + reach·cos(bearing), ry + reach·sin(bearing), bearing)
```

`tag_normal` (com yaw — inverte `vision_loop._feed_ekf_from_detections`):

```
tag_x = rx + dist·cos(bearing)
tag_y = ry + dist·sin(bearing)
tag_yaw = rθ + radianos(pitch_deg) + DOCK_PITCH_TO_TAG_YAW_OFFSET_RAD
goal  = (tag_x + standoff·cos(tag_yaw),
         tag_y + standoff·sin(tag_yaw),
         tag_yaw + π)
```

## Limitações (v1)

- **Planeja uma vez durante DOCKING**: não re-planeja durante a aproximação
  (re-planeja só em DONE se mover > 10 cm). Se a leitura inicial ou a odometria
  tiverem erro grande, o dock não corrige relendo a tag.
- **Correções EKF suprimidas**: durante DOCKING, a tag não corrige a pose — é pura
  odometria. Se a odometria derivar, o dock erra o alvo.
- **Manhattan no frame do robô**: o planejamento não é ótimo (não usa o grafo do
  mapa). Para distâncias curtas funciona; para longas, a missão com A* é melhor.
- **Tag-loss bypassed**: o control loop injeta `detectado=True` durante dock ativo,
  desabilitando a proteção de tag-loss da state machine.

## Verificação

`pi/tests/test_dock_to_tag.py`:
- geometria `line_of_sight` (para antes da tag; ignora `pitch_deg`);
- geometria `tag_normal` conferida contra a verdade-terreno do SIM;
- planejamento (FORWARD puro alinhado; curva de 90° quando lateral);
- máquina de estados (debounce, reset, DONE, `configure`);
- integração de malha fechada: o robô estaciona a menos de 5 cm do standoff;
- controle pelo frontend: rotas `/dock/*` registradas + `telemetry.dock` populado.
