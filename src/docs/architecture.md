# Arquitetura — Empilhadeira Robótica Autônoma

[ref: Seções 1, 2, 3 e 4 da AGENTS.md]

## Visão geral

Empilhadeira robótica em escala reduzida que transporta pallets (~15 cm de lado) em
ambiente controlado. Dois modos de operação:

- **Manual:** operador comanda o robô por joystick virtual no celular.
- **Autônomo:** o robô detecta uma AprilTag no pallet, estima a pose e se posiciona
  em frente ao alvo (**apenas posicionamento**, não manipulação).

O **garfo é sempre manual** nos dois modos, num canal de comando independente.

## Arquitetura hierárquica de 3 camadas

```
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND — Celular (React + Vite, navegador)                │
│  Joystick virtual · painel de telemetria · seletor de modo   │
└───────────────▲───────────────────────────┬─────────────────┘
                │ (2) telemetria @20Hz       │ (1) comando
                │     WebSocket / Wi-Fi      ▼
┌───────────────┴───────────────────────────────────────────────┐
│  RASPBERRY PI — Alto nível (Python, FastAPI + asyncio)         │
│  3 tarefas concorrentes:                                       │
│   • WebSocket Handler  • Vision Loop  • Serial Loop            │
│  Visão (AprilTag), Kalman, cinemática, navegação, máquina de   │
│  estados, protocolo (JSON+CRC8).                               │
└───────────────▲───────────────────────────┬───────────────────┘
                │ (4) sensores               │ (3) setpoint
                │     UART USB 115200, 20 Hz │     JSON+CRC8+\n
                │                            ▼
┌───────────────┴───────────────────────────────────────────────┐
│  ESP32 — Baixo nível, tempo real (C++ / Arduino, PlatformIO)   │
│  PID por roda ~100 Hz · leitura encoder/MPU · PWM (LEDC)→L298n │
└────────────────────────────────────────────────────────────────┘
```

Os contratos de dados entre camadas estão congelados em
[`serial-protocol.md`](./serial-protocol.md) — fonte única de verdade.

## Decisões fechadas (não rediscutir) — [ref: Seção 2]

- Arquitetura **hierárquica de 3 camadas**: Frontend → Pi → ESP32.
- **Raspberry Pi em Python.** Backend assíncrono único com **FastAPI** + `asyncio`,
  três tarefas concorrentes (WebSocket Handler, Vision Loop, Serial Loop).
- **ESP32 em C++ (Arduino, PlatformIO).** PID a ~100 Hz e determinismo de tempo real.
- **Frontend em React + Vite** (navegador do celular).
- **Frontend ↔ Pi:** WebSocket full-duplex sobre Wi-Fi local.
- **Pi ↔ ESP32:** UART USB, **115200 baud**, **20 Hz**, framing **JSON + CRC8(hex) + `\n`**.
- **Monorepo** com três apps (`pi/`, `firmware/`, `frontend/`) + `docs/` + `scripts/`.

## Parâmetros em aberto — NÃO INVENTAR VALOR — [ref: Seção 3]

Cada um existe como **constante nomeada** com placeholder marcado e `TODO(equipe)`.

| Parâmetro | Onde mora | Observação |
|---|---|---|
| Massa real do pallet | `pi/app/config.py` | Intro do relatório diz ~1 kg, mas o cálculo do garfo usou 0,1 kg. **Inconsistência aberta.** |
| Versão do motor do garfo (torque) | `config` + docs | Depende da massa real; versão 40 rpm pode estar subdimensionada. |
| Modelo do Raspberry Pi | este arquivo | Decide FPS de visão e orçamento de energia. **`TODO(equipe)`**. |
| `L` (distância entre rodas), `r` (raio da roda) | `pi/app/config.py` | Cinemática diferencial. |
| Ganhos PID (`Kp, Ki, Kd`) por roda | `firmware/src/config.h` | Sintonia inicial Ziegler-Nichols, depois empírica. |
| Ganhos de navegação (`Kz, Kx, Kp_pitch`) | `pi/app/config.py` | Modo automático. |
| `Zref` (distância de parada) | `pi/app/config.py` | ~5 cm; depende do comprimento do garfo. |
| Intrínsecos da câmera (`fx, fy, cx, cy`) | `pi/calibracao/camera_intrinsics.json` | Saída da calibração (xadrez / 3DF Zephyr). |
| Tamanho físico da AprilTag | `pi/app/config.py` | Necessário para a pose. |
| Offset extrínseco câmera→garfo | `pi/app/config.py` + docs | Alinhar a câmera ≠ alinhar o garfo. |
| Timeout "manter último setpoint" (ESP32) | `firmware/src/config.h` | Antes de cair em estado seguro. |
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
- Em modo automático, `ω = Kx·X + Kp·Pitch` pode **acoplar/brigar**; prever fallback.
- O canal de comando (WebSocket) precisa de **watchdog próprio**: se cair no modo
  manual com o robô andando, o robô deve **parar**, não manter o último comando.

## Estado seguro / watchdogs — [ref: Seção 7]

- **Serial cai** → ESP32 zera os motores (após `SETPOINT_TIMEOUT_MS`).
- **Comando (WebSocket) cai no manual** → Pi força `PARADO`.
