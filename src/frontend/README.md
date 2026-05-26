# Frontend (interface de operação)

Interface web em **React + Vite** que roda no **navegador do celular**. Fala com o
Raspberry Pi por **WebSocket** sobre Wi-Fi local: envia comandos (joystick, modo,
garfo) e mostra a telemetria em tempo real.

> ⚠️ **Fase de scaffolding.** Componentes renderizam placeholders; o hook de
> WebSocket é stub (sem conexão real). Nada de lógica de controle aqui.

## Estrutura

```
src/
├── main.jsx
├── App.jsx
├── index.css                 # diretivas do Tailwind
├── types/contracts.ts        # espelho TS dos 4 contratos
├── ws/useWebSocket.js         # hook de conexão com o Pi (stub)
└── components/
    ├── ModeSelector.jsx       # MANUAL / AUTOMATICO / PARADO
    ├── Joystick.jsx           # joystick virtual (nipplejs)
    ├── ForkControl.jsx        # subir/descer/parar o garfo
    └── TelemetryPanel.jsx     # rodas, IMU, visão, bateria (Recharts)
```

## Stack

React, Vite, Tailwind CSS, nipplejs, Recharts, WebSocket nativo. [ref: Seção 8]

## Como rodar (dev)

```bash
cd frontend
npm install
npm run dev    # sobe o dev server do Vite (host exposto p/ acesso pelo celular)
```

Abra no celular `http://<IP_DA_MAQUINA>:5173`. O IP do Pi (alvo do WebSocket) vem do
`.env` na raiz do monorepo (ver `.env.example`).

Os tipos em `src/types/contracts.ts` seguem `../docs/serial-protocol.md` (fonte de
verdade) e devem casar com `pi/app/models.py`.
