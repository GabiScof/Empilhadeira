# Formato de Mapas da Arena

Schema: `map_schema.py`, fachada: `world_model.py`.

Cada mapa é um arquivo JSON em `pi/maps/`, validado por Pydantic ao carregar.
O `WorldModel` expõe arena, tags, poses inicial/home e grafo opcional de
waypoints para navegação, visão e simulação. Trocar mapa = trocar arena/missão,
sem mudar código.

## Formato do Arquivo

### Campos Obrigatórios

```jsonc
{
  "name": "nome_do_mapa",
  "arena": {
    "width_m": 1.50,         // largura da arena (metros)
    "height_m": 2.00,        // altura/comprimento (metros)
    "origin": "bottom_left"  // referência de coordenadas
  },
  "start_pose": {
    "x_m": 0.20,             // posição inicial X do robô
    "y_m": 0.20,             // posição inicial Y
    "theta_deg": 90           // orientação inicial (graus)
  },
  "home_pose": {              // igual ao start_pose para voltar ao ponto de partida
    "x_m": 0.20,
    "y_m": 0.20,
    "theta_deg": 90
  },
  "tags": [
    {
      "position_id": "P1",   // identificador único da posição
      "x_m": 0.05,           // posição X da tag
      "y_m": 0.60,           // posição Y
      "wall": "left",        // parede onde está (opcional)
      "yaw_deg": 0            // orientação da tag (graus)
    }
  ],
  "tag_size_m": 0.04,        // tamanho físico da tag impressa (metros)
  "tag_family": "tag25h9"    // família de tags
}
```

### Sistema de Coordenadas

- Origem: canto inferior esquerdo (`origin: "bottom_left"`)
- Eixo X: cresce para a direita (largura da arena)
- Eixo Y: cresce para cima (comprimento da arena)
- `theta_deg`: anti-horário a partir de +X (0° = olhando para +X)

Todas as grandezas internas do Pi usam SI (m, rad); o JSON do mapa usa
metros e graus por legibilidade.

### Campos Opcionais — Grafo de Waypoints

Para arenas com restrições (corredores, paredes internas), adicione um grafo
de waypoints navegáveis:

```jsonc
{
  "waypoints": [
    { "id": "w0", "x_m": 0.20, "y_m": 0.20 },
    { "id": "w1", "x_m": 0.20, "y_m": 1.80 }
  ],
  "edges": [ ["w0", "w1"] ]
}
```

Se o mapa não tem grafo, a arena é tratada como aberta e o planejador
usa Manhattan (alinha um eixo, depois o outro).

As arestas são não direcionadas — o `WorldModel` constrói grafo bidirecional.

## Como Criar um Novo Mapa

1. Meça a arena real (largura × altura em metros)
2. Marque a posição de cada tag (x, y em metros a partir da origem)
3. Marque a posição inicial/home do robô
4. Crie o JSON seguindo o schema acima
5. Salve em `pi/maps/nome_do_mapa.json`
6. Selecione na UI (`MapSelector`) ou via `POST /maps/load/{nome}` (nota: `MAP=` no `.env` **não é lido** pelo código)

Para arenas com obstáculos, posicione waypoints nos corredores navegáveis e
conecte com arestas que não cruzam paredes.

### Validações Automáticas

- `position_id` de cada tag deve ser único
- Posições das tags devem estar dentro dos limites da arena
- IDs de waypoints devem ser únicos
- Arestas devem referenciar waypoints existentes
- Cada aresta deve ter exatamente 2 nós

Erros de validação levantam `pydantic.ValidationError` com mensagem descritiva.

## Seleção de Mapa

| Canal | Como usar |
|-------|-----------|
| `config.py` | `DEFAULT_MAP = "corredor_6tags_80x160"` (hardcoded; `MAP=` no `.env` **não é lido**) |
| API REST | `POST /maps/load/{map_name}` |
| UI | `MapSelector` na página de demo |
| Listagem | `GET /maps/list` — retorna nome, dimensões, nº de tags, se tem grafo |

Em modo simulação (`SIM=1`), trocar mapa reinicializa `SimWorld`, emulador e
visão sintética. Em modo real, apenas o `WorldModel` em memória é atualizado.

## Mapas de Exemplo

| Mapa | Dimensões | Tags | Grafo | Descrição |
|------|-----------|------|-------|-----------|
| corredor_pequeno | 0.80×2.00 m | 3 | Não | Corredor estreito |
| corredor_6tags | 0.60×3.00 m | 6 | Não | Corredor longo estreito |
| **corredor_6tags_80x160** | 0.80×1.60 m | 6 | Não | Arena real medida — tags na metade superior |
| corredor_6tags_80x200 | 0.80×2.00 m | 6 | Não | Corredor antigo (dimensões anteriores) |
| arena_media | 1.50×1.50 m | 4 | Não | Arena quadrada aberta |
| arena_grande_com_grafo | 3.00×2.00 m | 6 | Sim (9 wp) | Arena grande com waypoints |

> `corredor_6tags_80x160` é o mapa da arena real. Tags coladas nas
> paredes laterais (L1–L3 à esquerda, R1–R3 à direita), centros em y=0,825/1,20/1,575 m.
> A metade inferior do corredor (y < 0,80 m) não tem tags — o robô parte de lá.

## Relação com Outros Módulos

```
pi/maps/*.json
    ↓ load_map() / ArenaMap
WorldModel
    ├── PathPlanner (grafo ou Manhattan)
    ├── MissionSM (tag_pose_m_rad por position_id)
    ├── SyntheticVision (posições das tags em SIM)
    └── EKF (correção por tag conhecida após resolve_tag_id)
```
