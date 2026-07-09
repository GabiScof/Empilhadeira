# Empilhadeira — Frontend (React + Vite)

## Funcionalidades

### Tela de Operador (`/`)
- Joystick (nipplejs) — controle manual, mapeia para `x,y ∈ [-1,1]`
- D-Pad — comandos puros (frente/ré/esquerda/direita) com heartbeat de 100 ms
- Seletor de modo — MANUAL / AUTOMATICO / PARADO
- Controle do garfo — subir / descer / parar (sempre ativo)
- Painel dock-to-tag — ligar/desligar aproximação, estado (Procurando/Aproximando/Estacionado)
- Painel de missão — iniciar/continuar missão pick-and-place
- SafetyAlert — eventos de segurança (tag-loss, ws disconnect, etc.)
- Painel de telemetria — rodas, IMU, visão, EKF, mini-gráficos (Recharts)
- Links para Demo e Mapa

### Tela Demo (`/demo`)
Funciona tanto em SIM=1 quanto no hardware real (tenta `/sim/world-state`,
faz fallback para `/world-state` que usa a pose do EKF + mapa):
- Arena (canvas) — vista de cima, robô + heading, rastro, rota planejada,
  tags com AprilTag, cone de FOV, standoff (0,15 m)
- Garfo (vista lateral) — altura + indicadores de fim-de-curso (só sim)
- Reset de pose — definir pose inicial arbitrária (x, y, θ) (só sim)
- Seletor de mapa — carregar mapas via `POST /maps/load/{nome}`
- Injeção de falhas — queda serial, tag oculta, slip de roda, vision blur/drop,
  encoder noise, gyro drift, bateria saturada
- D-Pad, Joystick, ModeSelector, DockPanel, MissionPanel, DebugExport
- Telemetria — mesmo painel da tela de operador

### Tela de Mapa (`/map`)
- Visualização do mapa carregado (tags, waypoints, arestas, arena)

## Como rodar

```bash
# Instalar dependências
cd src/frontend && npm install

# Desenvolvimento (dev server em http://localhost:5173)
npm run dev

# Build para produção
npm run build

# Testes de componente
npm test

# Lint + formato
npm run lint
npm run format
```

## Stack

- React 18 + Vite 5
- Tailwind CSS 3
- nipplejs (joystick)
- Recharts (gráficos)
- react-router-dom (rotas)
- Vitest + Testing Library (testes)

## WebSocket

Conecta em `ws://<host>:8000/ws` (override via `VITE_PI_WS_URL` em dev).
Envia `Command` (contrato 1), recebe `Telemetry` (contrato 2, incluindo campos
estendidos: `ekf`, `mission`, `dock`, `navigation`, `parado_reason`, `detected_tags`,
`map_name`) a ~20 Hz. Reconexão automática com backoff (500 ms → 10 s).

REST derivado do mesmo host: missão (`/mission/*`), dock (`/dock/*`), mapas
(`/maps/*`), mundo (`/world-state`).
