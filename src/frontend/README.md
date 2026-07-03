# Empilhadeira — Frontend (React + Vite)

Interface de operação da empilhadeira robótica. Roda no navegador do celular,
conecta ao backend Pi via WebSocket.

## Funcionalidades

### Tela de Operador (`/`)
- **Joystick** (nipplejs) — controle manual, mapeia para `x,y ∈ [-1,1]`
- **Seletor de Modo** — MANUAL / AUTOMATICO / PARADO
- **Controle do Garfo** — subir / descer / parar (sempre ativo)
- **Painel de Telemetria** — rodas (rad/s), IMU (roll/pitch), visão (z/x/pitch),
  mini-gráficos (Recharts), indicador de conexão

### Tela Demo (`/demo`)
Disponível quando conectado ao backend em modo SIM:
- **Arena** (canvas) — vista de cima do almoxarifado, robô + heading, rastro,
  pallet com AprilTag, cone de FOV, anel do Zref
- **Garfo (vista lateral)** — altura do garfo + indicadores de fim-de-curso
- **Reset de Pose** — definir pose inicial arbitrária (x, y, θ)
- **Injeção de Falhas** — queda serial, tag oculta, slip de roda, bateria saturada
- **Telemetria** — mesmo painel da tela de operador

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

Conecta em `ws://<host>:8000/ws`. Envia `Command` (contrato 1), recebe
`Telemetry` (contrato 2) a ~20 Hz. Reconexão automática com backoff exponencial.
