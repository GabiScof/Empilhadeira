# Dock-to-Tag — Aproximação por Segmentos a UMA Tag

[ref: `pi/app/control/dock_to_tag.py`, `pi/app/tasks/control_loop.py`]

## Visão Geral

Modo **opt-in** para o cenário mais simples de navegação autônoma, mirado no
**robô real**:

> ligar o robô → ver **uma** AprilTag → estacionar **de frente** para ela,
> usando o "passinho" discreto (avança / gira 90°), **não** o servo contínuo.

É a mesma malha de execução da missão (`SegmentExecutor`), disparada por uma tag
avulsa em vez de um alvo do mapa — e **sem** o ciclo pick/place/home. Não exige
que a tag esteja no mapa. Consome as mesmas leituras (`z_cm`/`x_cm`/`pitch_deg`)
que o navegador legado já usa no hardware.

### Diferença para os dois modos existentes

| | Automático legado | Missão | **Dock-to-tag (novo)** |
|---|---|---|---|
| Controlador | `NavigationController` | `SegmentExecutor` | `SegmentExecutor` |
| Realimentação | visão (tag) contínua | pose do EKF | pose do EKF |
| Movimento | servo reativo suave | segmentos FORWARD/TURN | segmentos FORWARD/TURN |
| Disparo | ver a tag | iniciar missão (≥2 tags) | ver **1** tag |

O dock **planeja uma vez** ao ver a tag e executa a rota pela odometria do EKF
(como a missão) — robusto a perder a tag do FOV durante uma curva de 90°.

## Como ligar e testar (robô real)

Desligado por padrão → sistema idêntico ao atual. Ligável **em runtime pela
interface** (não precisa reiniciar):

**Pela interface (recomendado):** no painel **"Aproximar de uma tag"** (abaixo do
seletor de modo, tanto na tela do Operador quanto na Demo), toque em **"Ligar
aproximação por tag"** → selecione **AUTOMATICO** → mostre uma tag ao robô. O
painel mostra o estado (Procurando / Aproximando / Estacionado). Para re-aproximar
outra tag: volte a MANUAL/PARADO e selecione AUTOMATICO de novo.

**Pela API (equivalente ao botão):**

| Rota | Efeito |
|---|---|
| `POST /dock/enable` (body `{}` ou `{"mode","standoff_m"}`) | liga o dock |
| `POST /dock/disable` | desliga |
| `GET /dock/state` | estado atual |

**Por env var (só define o default inicial):**

```bash
DOCK_TO_TAG=1 python -m app.main   # já sobe com o dock ligado
```

A rota planejada aparece em `planned_path` e o rastro em `executed_trail` (mesma
visualização da missão); o estado do dock vai na telemetria (`telemetry.dock`).

**Vista de cima no robô real:** a tela `/demo` desenha o Arena (robô + tags +
rota) também no hardware, via `GET /world-state` (pose do EKF + mapa) — que
substitui o `/sim/world-state` só-de-simulação. Para isso **carregue um mapa**
antes (sem mapa não há dimensões de arena para desenhar, e o EKF roda só na
odometria). Com mapa, as tags corrigem o EKF e a vista fica igual à da missão.

### Variáveis de ambiente

| Var | Default | Efeito |
|---|---|---|
| `DOCK_TO_TAG` | `0` | `1` liga o modo (substitui o legado no ramo AUTOMATICO-sem-missão). |
| `DOCK_MODE` | `line_of_sight` | Estratégia de alvo — ver abaixo. |
| `DOCK_STANDOFF_M` | `0.15` | Distância de parada em frente à tag (m). |
| `DOCK_MIN_DETECTIONS` | `3` | Detecções consecutivas antes de planejar (anti-ruído). |
| `DOCK_PITCH_TO_TAG_YAW_OFFSET_RAD` | `0.0` | Convenção de yaw — **só** para `tag_normal`. |

## Estratégias de alvo (`DOCK_MODE`)

### `line_of_sight` (DEFAULT — recomendado para o real)

Para o robô `DOCK_STANDOFF_M` **antes** da tag, sobre a reta robô→tag, de frente
para ela. Usa **apenas** `z_cm`/`x_cm` (distância + rumo) — grandezas bem
definidas, idênticas às que o navegador legado já usa e valida no hardware.

**Não depende da convenção de yaw da tag** → seguro no robô real sem calibração
extra. Não quadra com a face da tag: para na direção em que a tag foi vista.

### `tag_normal` (opcional — precisa de yaw validado)

Quadra com a **face** da tag (aproxima pela normal da face), como a missão faz.
Mais preciso para encostar num pallet/estante. **Depende do yaw da tag**, que vem
de `pitch_deg` — e a convenção real está **não validada** (`TODO(equipe): validar
convenção de yaw` em `app/vision/pose.py`).

⚠️ Antes de usar `tag_normal` no real: ponha uma tag de yaw conhecido ~50 cm à
frente e confira se o robô encosta pela frente. Se chegar espelhado/de lado,
ajuste `DOCK_PITCH_TO_TAG_YAW_OFFSET_RAD` (real ≈ `0.0`; a visão sintética do SIM
precisa de `π`). A **posição** do alvo não depende disso — só a orientação final.

## Máquina de Estados

```
SEEKING → (N detecções estáveis, planeja) → DOCKING → (rota concluída) → DONE
   │                                            │
   └────────────── qualquer ────────────────────┴──→ FAULT (timeout de segmento)
```

- **SEEKING**: robô parado; acumula detecções. Ao atingir `DOCK_MIN_DETECTIONS`,
  calcula o alvo (conforme `DOCK_MODE`), planeja (`plan_route(world=None)` →
  planejador Manhattan → avança/gira 90°) e carrega o executor.
- **DOCKING**: executa os segmentos via EKF.
- **DONE / FAULT**: robô parado.

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

- **Planeja uma vez**: não re-planeja durante a aproximação. Se a leitura inicial
  ou a odometria do EKF tiverem erro grande, o dock não corrige relendo a tag
  (ao contrário do servo legado). Estrutura pronta para re-planejar se preciso.
- **Depende do EKF**: a precisão da chegada segue a precisão da localização.

## Verificação

`pi/tests/test_dock_to_tag.py`:
- geometria `line_of_sight` (para antes da tag; ignora `pitch_deg`);
- geometria `tag_normal` conferida contra a verdade-terreno do SIM;
- planejamento (FORWARD puro alinhado; curva de 90° quando lateral);
- máquina de estados (debounce, reset, DONE, `configure`);
- **integração de malha fechada**: o robô realmente estaciona a <5 cm do standoff;
- controle pelo frontend: rotas `/dock/*` registradas + `telemetry.dock` populado.
