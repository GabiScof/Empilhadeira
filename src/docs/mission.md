# Missão Pick-and-Place com Garra Manual

Módulos: `mission/mission_sm.py`, `tasks/control_loop.py`.

O robô executa uma missão de pick-and-place onde:

1. Dois alvos (tags) são sorteados/selecionados
2. O robô navega autonomamente até a tag de pick
3. O operador aciona a garra manualmente (pick)
4. O robô navega até a tag de place
5. O operador aciona a garra manualmente (place)
6. O robô volta para home

A missão opera em modo AUTOMATICO com o planejador de rotas e o executor de
segmentos. O garfo não entra em malha fechada autônoma — apenas o
posicionamento do chassi é automático.

## Máquina de Estados

```
IDLE → LOAD_MAP → DRAW_TARGETS → GO_TO_PICK → AT_PICK(espera operador)
→ GO_TO_PLACE → AT_PLACE(espera operador) → GO_HOME → DONE
                                                        ↓
                                                      FAULT
```

### Estados

| Estado | Descrição | Transição |
|--------|-----------|-----------|
| IDLE | Aguardando missão | → LOAD_MAP (ao iniciar) |
| LOAD_MAP | Carregando mapa | → DRAW_TARGETS |
| DRAW_TARGETS | Definindo 2 position_ids (ver prioridade abaixo) | → GO_TO_PICK |
| GO_TO_PICK | Navegando até tag #1 | → AT_PICK (chegada confirmada) |
| AT_PICK | Parado, aguardando operador | → GO_TO_PLACE ("continuar") |
| GO_TO_PLACE | Navegando até tag #2 | → AT_PLACE (chegada confirmada) |
| AT_PLACE | Parado, aguardando operador | → GO_HOME ("continuar") |
| GO_HOME | Navegando para home | → DONE (chegada confirmada) |
| DONE | Missão concluída | (reset para nova missão) |
| FAULT | Falha crítica | Motores zerados, sinaliza na UI |

Qualquer estado ativo pode transicionar para FAULT (timeout de segmento, alvo
ausente no mapa, mapa com menos de 2 tags). Atenção ao comportamento real do
código: no tick do fault o executor zera as rodas, mas a máquina de segurança
(`state_machine`) **não** entra em PARADO — com a missão inativa e o modo
AUTOMATICO ainda selecionado, o ramo do control loop cai no dock-to-tag (ou no
legado) no tick seguinte. Para parar de fato, o operador deve resetar a missão
ou mudar de modo.

### Prioridade de escolha dos alvos

1. Argumento explícito em `POST /mission/start` (`pick_id`/`place_id`) — se o
   `position_id` existir no mapa.
2. Defaults `MISSION_DEFAULT_PICK_ID="L3"` / `MISSION_DEFAULT_PLACE_ID="R1"`,
   hardcoded em `config.py` (não vêm do `.env`) — se existirem no mapa.
3. Sorteio determinístico com `random.Random(42)` (`_seed=42` hardcoded em
   `mission_sm.py`; o `MISSION_SEED` de `config.py` não é lido pela SM).

## Garra Manual

A garra não é controlada automaticamente. Nos estados AT_PICK e AT_PLACE:

- O robô para completamente (`ω_esq = ω_dir = 0`)
- A UI sinaliza "pronto para acionar a garra"
- O operador aciona o garfo pelo canal manual existente (`garfo: subir/descer/parar`)
- A missão só retoma quando o operador clica "continuar" na UI

> TODO(equipe): confirmar gatilho de retomada — botão "continuar" (default)
> ou auto-retomar ao disparar o fim-de-curso. Implementar como estratégia
> configurável (`MISSION_RESUME_TRIGGER` em `config.py`).

Valores possíveis de `MISSION_RESUME_TRIGGER`:

| Valor | Comportamento |
|-------|---------------|
| `button` (default) | Operador clica "continuar" na UI |
| `limit_switch` | Retoma automaticamente ao acionar fim-de-curso *(TODO)* |

## Resolução de ID de Tag

As posições das tags são conhecidas no mapa (`position_id: L1..L3, R1..R3`
no corredor; `P1, P2, ...` nas arenas). O casamento `tag_id` (inteiro da
AprilTag) → `position_id` funciona assim no código atual:

1. **Pelo mapa (modo real):** se o mapa declara `april_tag_id` em cada tag
   (caso dos `corredor_6tags_80x160`/`80x200`), o `WorldModel` pré-carrega
   `_tag_id_to_position` no load e a detecção resolve direto por
   `get_position_for_tag_id()`. Foi por isso que o `DEFAULT_MAP` foi fixado
   em 2026-07-07 no mapa com `april_tag_id` preenchido — nos mapas sem esse
   campo, o robô real não resolve nenhuma tag contra o mapa.
2. **Pelo `position_id` da detecção (SIM):** a visão sintética já entrega o
   `position_id`; o `vision_loop` persiste o par via `resolve_tag_id()`.

Não há casamento por proximidade (posição estimada → posição mais próxima do
mapa) implementado para detecções reais: uma tag cujo `tag_id` não consta do
mapa nem foi resolvido antes entra na telemetria com `in_map=False` e **não**
corrige o EKF.

Implementação: `pi/app/tasks/vision_loop.py` + `pi/app/world/world_model.py`.

## Fluxo de Controle

```
MissionSM (estado)
    ↓ alvo (x, y, θ)
PathPlanner (grafo A* ou Manhattan)
    ↓ lista de Segment (FORWARD/TURN)
SegmentExecutor (malha externa ~20 Hz)
    ↓ (ω_esq, ω_dir)
StateMachine (segurança)
    ↓ Setpoint
Serial Loop → ESP32 PID (~100 Hz)
```

Durante navegação, o EKF fornece feedback de pose. Correções por AprilTag
são aplicadas quando uma tag conhecida entra no FOV.

## API

Rotas REST expostas pelo backend FastAPI (`pi/app/main.py`):

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/mission/start` | Inicia missão (opcionalmente com `pick_id`/`place_id`) |
| `POST` | `/mission/continue` | Operador confirma garra acionada |
| `POST` | `/mission/reset` | Reseta missão ao IDLE |
| `GET` | `/mission/state` | Estado atual |

### Exemplos

```bash
# Iniciar missão com sorteio automático
curl -X POST http://localhost:8000/mission/start \
  -H "Content-Type: application/json" \
  -d '{}'

# Iniciar com alvos fixos
curl -X POST http://localhost:8000/mission/start \
  -H "Content-Type: application/json" \
  -d '{"pick_id": "P1", "place_id": "P3"}'

# Operador confirma pick/place
curl -X POST http://localhost:8000/mission/continue

# Consultar estado
curl http://localhost:8000/mission/state
```

Resposta típica de `/mission/state`:

```jsonc
{
  "ok": true,
  "mission": {
    "state": "AT_PICK",
    "pick_position_id": "P1",
    "place_position_id": "P3",
    "fault_reason": null,
    "is_navigating": false,
    "is_waiting_operator": true,
    "elapsed_s": 12.4
  }
}
```

## Pré-requisitos

- Mapa carregado (`WorldModel` disponível em `SharedState`)
- Modo AUTOMATICO selecionado no frontend
- Mapa com pelo menos 2 tags para sortear pick e place distintos
- EKF inicializado na pose de `start_pose` do mapa

## Testes

- `pi/tests/test_mission.py` — transições da máquina de estados
- `pi/tests/test_integration_mission.py` — missão end-to-end em simulação
