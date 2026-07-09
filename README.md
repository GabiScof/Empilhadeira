# Empilhadeira Robótica Autônoma

Projeto da disciplina ENG4061 — Projeto Robótica (PUC-Rio, Turma 3VB).

Empilhadeira em escala reduzida que transporta pallets (~15 cm) em ambiente
controlado (corredor 0,80 × 1,60 m com 6 AprilTags). Dois modos de operação:

- **Manual** — o operador dirige por joystick virtual no celular.
- **Autônomo** — o robô navega sozinho entre AprilTags no mapa, executa missão
  pick-and-place ou estaciona em frente a uma tag (dock-to-tag).

O garfo é sempre manual: tem canal de comando independente nos dois modos e
nunca entra na malha autônoma.

Este README é o ponto de entrada do repositório: resume o que foi feito, como
o sistema funciona e aponta para a documentação detalhada de cada parte
(seção [Mapa da documentação](#mapa-da-documentação)).

---

## Estrutura do repositório

```
Empilhadeira/
├── src/                        Monorepo de software (Pi + ESP32 + frontend + docs)
├── Eletrônica/                 Hardware elétrico: esquemáticos, datasheets, caixas, testes
├── Apresentações_&_Relatório/  PDFs entregues (pré-projeto e entrega final)
├── modelagem_3D/               STLs das peças mecânicas (garfo, polias, eixo, carretel, suporte)
├── images/                     Imagens de apoio (folha de AprilTags tag25h9)
├── APRESENTACAO_SPEC.md        Roteiro técnico da apresentação (visão, controle, comunicação)
└── requirements.txt            Dependências Python fixadas para deploy no Pi
```

---

## Arquitetura

Três camadas hierárquicas, cada uma em um processador e linguagem próprios:

```
┌──────────────────────────────────────────────────────────┐
│  FRONTEND — celular (React + Vite, navegador)             │
│  joystick · D-pad · garfo · missão · mapa · arena · dock  │
└──────────▲──────────────────────────┬─────────────────────┘
     (2) telemetria @20Hz      (1) comando
         WebSocket / Wi-Fi            ▼
┌──────────┴───────────────────────────────────────────────┐
│  RASPBERRY PI — alto nível (Python, FastAPI + asyncio)    │
│  3 loops (Vision · Serial · Control) + WS handler          │
│                                                            │
│  AprilTag → EKF 2D → planejador → executor → setpoint     │
└──────────▲──────────────────────────┬─────────────────────┘
     (4) sensores               (3) setpoint
     UART USB 115200, 20 Hz — JSON + CRC8 + \n
                                      ▼
┌──────────┴───────────────────────────────────────────────┐
│  ESP32 — baixo nível, tempo real (C++/Arduino/PlatformIO) │
│  PID por roda ~100 Hz · encoders · MPU-6050 · PWM → L298n │
└───────────────────────────────────────────────────────────┘
```

Há quatro contratos de dados congelados entre as camadas, espelhados em Python
(Pydantic), C++ (ArduinoJson) e TypeScript. Qualquer mudança de contrato
precisa ser aplicada nas três linguagens.
Detalhes: [`src/docs/serial-protocol.md`](src/docs/serial-protocol.md).

---

## Visão

A câmera USB é o único sensor absoluto. Pipeline:

```
Câmera USB (1280×720) → grayscale → pupil-apriltags (tag25h9, PnP)
  ├─ VisionState (tag mais próxima): detectado, id, z_cm, x_cm, pitch_deg
  └─ TagObservations (todas) → correção do EKF 2D [x, y, θ]
```

**Compensação de tilt:** a câmera fica inclinada 30° para baixo (no topo do
trilho do garfo). `pose.py` rotaciona a pose bruta pelo ângulo de tilt antes
de extrair z/x — converte distância no eixo óptico para distância horizontal.

**Convenções de sinal (validadas na bancada em 2026-07-07):**

- **x negado** na fronteira: no OpenCV, x+ significa tag à direita; na
  convenção do projeto, x+ significa tag à esquerda. Sem essa negação o robô
  se afastaria da tag no hardware (em simulação o problema não aparecia porque
  a visão sintética já usava a convenção do projeto).
- **pitch negado**: a câmera real reporta sinal oposto ao do simulador.
- **Offset câmera→garfo** aplicado em z (−10 cm, lente atrás da ponta do
  garfo) e x, para que z_cm represente a distância da ponta do garfo à tag.

**Multi-tag:** `estimate_vision_state` retorna a tag mais próxima para o
controle reativo; `estimate_tag_observations` retorna todas para o EKF.

**Braço de alavanca lente→eixo:** a pose medida é a da lente, mas o EKF estima
o centro do robô. A correção subtrai `LENS_TO_AXLE_FORWARD_CM` (18 cm) na
direção do heading para evitar viés sistemático.

### Calibração

Procedimento: tabuleiro de xadrez OpenCV. Calibração atual: 2026-07-07,
câmera nova remontada com tilt de 30°, a 1280×720. Intrínsecos:
fx=fy=1023,63 · cx=634,08 · cy=377,08, com coeficientes de distorção
completos (erro de reprojeção não registrado). Uma calibração anterior
(câmera antiga, 640×480, 28 fotos com cantos internos 8×5 e quadrado de
3 cm, reprojeção 0,144 px) foi descartada por valores anômalos.

Regra operacional: a resolução de captura precisa ser a mesma da calibração.
Com `REQUIRE_CAMERA_CALIBRATION=1`, o backend não sobe em modo real sem
calibração válida.

### Visão sintética (SIM=1)

FOV 60°, alcance 3–150 cm, ruído gaussiano ±0,2 cm / ±0,5°, com injeção de
falhas (`tag_hidden`, `vision_blur`, `vision_drop`). Os 9/9 cenários de
aproximação foram validados nessa visão sintética antes de existir robô
físico.

---

## Controle

### Malha em cascata (2 níveis, 2 processadores)

```
Pose alvo (mapa)
   ↓
PathPlanner → [FORWARD 1.2m, TURN 90°, ...]
   ↓
SegmentExecutor — malha EXTERNA no Pi @20 Hz
   pose EKF → (v, ω) → (ω_esq, ω_dir) em rad/s
   ↓ setpoint via serial
PID por roda no ESP32 — malha INTERNA @100 Hz
   ω medido (encoder) → duty PWM → motor
```

O Pi não duplica o PID de roda: a malha externa cuida de posição/heading, a
interna de velocidade. A divisão também é de tempo real — o ESP32 garante
determinismo a 100 Hz; o Pi roda a 20 Hz em Python/asyncio.

### Arbitragem do control loop

O `control_loop.py` roda a 20 Hz e decide qual controlador gera o setpoint:

| Condição | Controlador |
|----------|-------------|
| `MANUAL` | Joystick → cinemática diferencial |
| `AUTOMATICO` + missão ativa | Missão → PathPlanner → SegmentExecutor compartilhado |
| `AUTOMATICO` + dock ligado + sem missão | TagDocker (plano e executor próprios) |
| `AUTOMATICO` + dock desligado + sem missão | NavigationController legado (servo contínuo) |
| `PARADO` / sem comando | Rodas zeradas |

O dock está ligado por default (hardcoded `True` desde 2026-07-07) — o caminho
padrão do AUTOMATICO sem missão é o dock, não o navegador legado.

### Cinemática diferencial

`v = y × MAX_LINEAR_SPEED`, `ω = −x × MAX_ANGULAR_SPEED` (x negado: joystick
x+ = direita, mas ω+ = anti-horário). Velocidades de roda:
`w_esq = (v − ωL/2)/r`, `w_dir = (v + ωL/2)/r`.

### PathPlanner

Se o mapa tem grafo de waypoints: A* sobre o grafo, segmentos TURN/FORWARD
entre waypoints. Se não tem: fallback Manhattan (alinha X, depois Y).
Segmentos menores que 0,5 cm são descartados.

### SegmentExecutor

Malha proporcional sobre a pose do EKF:

- `v = K_DIST × distância` (K=1,5, cap 0,30 m/s)
- `ω = K_HEADING × erro_heading` (K=2,5)
- Tolerância de posição: 2 cm; heading: 4° (folga para o piso de ω não oscilar)
- Forward: se o erro de heading passa de 45°, para e gira primeiro (`v = 0`)
- Timeout por segmento: 45 s → FAULT da missão

**Anti-atrito estático (correção de bancada, 2026-07-07):** perto do alvo, a
malha proporcional comanda velocidades pequenas demais para vencer o atrito
estático — o motor recebe duty mas o robô não anda. Pisos: `v ≥ 0,09 m/s`
(acima da zona de stick-slip) e `|ω| ≥ 1,0 rad/s` (skid-steer precisa de
torque). Teto de giro: `ω ≤ 1,6 rad/s` — acima disso as rodas derrapam, a
odometria conta rotação que não houve e o EKF acumula erro.

### Dock-to-tag

Modo que estaciona o robô em frente a uma única tag por segmentos discretos.
O plano é feito uma vez; a execução usa odometria/EKF. Usa a mesma maquinaria
de navegação da missão (PathPlanner + SegmentExecutor), então serve de ensaio
para ela: se o dock funciona, a navegação da missão funciona.

**Estados:** `SEEKING` (acumula detecções) → `DOCKING` (executa rota) →
`DONE` / `FAULT`

**Planejamento (Manhattan no frame do robô, não do mapa):**

1. Projeta o alvo no frame do robô: `dz` para frente, `dlat` para o lado.
2. Rota: avança `dz` → gira ±90° → avança `|dlat|` → giro final para alinhar.
   Pernas menores que 1 cm são descartadas.

**Estratégias:** `line_of_sight` (default — usa só z/x, não depende de
convenção de yaw) e `tag_normal` (esquadra com a face da tag; usa a convenção
de yaw com offset π, validada na bancada em 2026-07-07).

**EKF suprimido durante DOCKING:** a `vision_loop` não faz correção por tag
enquanto o dock executa, para evitar salto de pose se a tag não estiver
exatamente na posição declarada no mapa.

**Re-planejamento:** quando DONE, se aparece uma tag que exige deslocamento
maior que 0,10 m, replaneja automaticamente.

### Navegação reativa legada (1 tag)

Controlador servo-contínuo sobre a leitura da câmera. Usado quando o dock está
desligado e não há missão. Quatro fases:

| Fase | Comportamento |
|------|---------------|
| `COARSE_ALIGN` | Entra quando `|pitch| > 45°`. Gira com ω fixo (±2,0 rad/s), sinal travado na entrada. Sai quando `|pitch| < 35°` (histerese). v=0. |
| `APPROACH` | v proporcional à distância (desaceleração `v_max = √(2·a·d)`); ω por bearing proporcional (longe do centro) ou pitch+x (perto). Heading guard: `|pitch| > 30°` → v=0. FOV guard: reduz v perto da borda do FOV. Centering: reduz v quando `|x| > 1,5 cm`. |
| `FACE` | Perto do Zref e lateralmente alinhado, mas com pitch grande. Gira no lugar com ω ampliado (3× KP_PITCH). |
| `RETREAT` | Marcha-ré a −4 cm/s até z ≥ 30 cm, depois volta a APPROACH. |

Detector de oscilação: 5 ou mais trocas de sinal de ω em 10 amostras →
fallback com `allow_stuck_retreat` (se preso, força ré).

### EKF 2D — [x, y, θ]

Estado em metros/radianos. Predição por odometria diferencial + giroscópio
(fusão 70% gyro / 30% odometria para heading). Correção por observação
absoluta de tag: `H = I`, ruído R escalado pela qualidade da detecção, gate de
Mahalanobis 3,0. Exporta elipse de covariância 95% para a UI.

Nota: as constantes de ruído (`EKF_Q_*`, `EKF_R_*`) existem em `config.py`,
mas não estão conectadas ao `ekf.py` — os valores estão hardcoded na classe.

### Kalman IMU (roll/pitch)

Filtro separado para roll e pitch a partir do acelerômetro e giroscópio (via
filterpy). Saída em graus para a telemetria. Não é usado pelo EKF para
heading — esse vem do giroscópio Z diretamente.

### Auto-calibração do giroscópio

Na partida (robô parado ~2–3 s), o `GyroCalibrator`:

1. Usa a gravidade para descobrir qual eixo do MPU aponta para cima.
2. Determina o sinal do yaw (projeção do gyro no vetor "up" de um sensor destro).
3. Estima o bias de taxa-zero.
4. Rastreia drift térmico lento por EMA (α=0,01) após calibrado.

A posição/orientação física do MPU no chassi não importa — o sensor pode ser
remontado sem alterar código. Guard contra MPU morto: se `|accel| < 2,0 m/s²`
(fisicamente impossível com o sensor funcionando), o frame é descartado.

---

## Missão pick-and-place

```
IDLE → LOAD_MAP → DRAW_TARGETS → GO_TO_PICK → AT_PICK
→ GO_TO_PLACE → AT_PLACE → GO_HOME → DONE   (+ FAULT)
```

- Em `AT_PICK` / `AT_PLACE` o robô para, o operador aciona o garfo e clica
  "continuar" (`POST /mission/continue`).
- Prioridade dos alvos: argumento explícito (UI/curl) > default em config
  (L3/R1) > sorteio com seed 42 (hardcoded na state machine).
- Alvos são `position_id` do mapa (ex.: L3, R1).
- A rota é planejada pelo PathPlanner e executada pelo SegmentExecutor
  compartilhado. Na chegada, `mission.notify_route_done()` avança o estado.
- Timeout de segmento → `mission.fault()`.

API REST: `POST /mission/start`, `/mission/continue`, `/mission/reset`,
`GET /mission/state`.

---

## Máquina de estados e segurança

**Modos:** `MANUAL`, `AUTOMATICO`, `PARADO`

**Latch de segurança:** parada por segurança trava e só `acknowledge()`
destrava. Sem o latch, o loop de 20 Hz re-entraria no modo ativo a cada tick.
Durante missão e dock, o control loop chama `acknowledge()` automaticamente e
alimenta `detectado=True` sintético para suprimir o tag-loss (a tag sai do FOV
em curvas normais de 90°).

**Triggers de parada:**

- Tag perdida por mais de 5 frames em AUTOMATICO
- Command watchdog em MANUAL (400 ms sem comando com rodas em movimento)
- `force_stop()` por perda de serial ou desconexão do WebSocket

### Cadeia de watchdogs (5 vigias em 3 processadores)

| Elo que cai | Limite | Ação |
|---|---|---|
| Celular ↔ Pi (Wi-Fi, MANUAL andando) | 400 ms | PARADO com latch, motivo `command_watchdog` |
| WebSocket fecha | imediato | `force_stop` + comando limpo |
| Tag some em AUTOMATICO | 5 frames (~250 ms) | PARADO com latch (suspenso durante missão/dock) |
| UART sem sensores | 5 ciclos (~250 ms) | `force_stop`, motivo `serial_loss` |
| ESP32 sem setpoint | 200 ms | motores zerados + PID reset (local, independe das camadas acima) |

O watchdog do firmware é a última linha de defesa: roda no ESP32 e não depende
de nada acima dele.

---

## Firmware ESP32

**PID por roda a ~100 Hz:** Kp=20, Ki=5, Kd=1, anti-windup com integral
limitada a ±500. PWM LEDC a 20 kHz, 8 bits (0–255).

**Bypass de setpoint zero (correção de bancada, 2026-07-06):** com um encoder
morto (medida=0), o comando de parar tinha erro 0, mas a integral acumulada
segurava o duty no máximo — o robô ignorava o STOP. Correção: setpoint 0 vira
parada incondicional que bypassa o PID e reseta a integral.

**Encoder x4:** interrupções em CHANGE nas duas fases, tabela de transição de
16 entradas (ISR em IRAM). Transição inválida vale 0, o que rejeita bounce por
construção. 1440 contagens/volta.

**IMU MPU-6050 cru:** acelerômetro ±2g e gyro ±250°/s enviados crus (m/s²,
°/s). Toda a fusão fica no Pi (decisão: firmware simples e determinístico;
filtros ficam onde há ponto flutuante e teste fácil). Auto-recuperação: após
~1 s de leituras mortas, o firmware re-envia o wake (`0x6B`).

**Watchdog local:** 200 ms sem setpoint válido → motores zerados + PID
resetado.

**Garfo:** duty fixo (220); a rosca sem-fim segura a carga parada.
Fins-de-curso previstos no código, mas desabilitados (não montados).

Detalhes: [`src/firmware/README.md`](src/firmware/README.md).

---

## Frontend

Três páginas:

- **Operador** (`/`) — joystick, seletor de modo, D-pad, garfo, dock,
  telemetria, missão, alertas de segurança.
- **Demo** (`/demo`) — arena vista de cima (sim ou real via `/world-state`),
  missão, injeção de falhas, reset de pose, export de debug, seletor de mapa.
- **Mapa** (`/map`) — visualização de mapas JSON com tags, waypoints e grafos.

**D-pad (instrumento de teste):** botões que enviam vetores puros — Frente com
ω exatamente 0 (reta), Gira com v exatamente 0 (giro no lugar), em 30/60/100%
da velocidade. Re-envia a cada 100 ms (heartbeat para o watchdog de 400 ms).
Elimina a variabilidade do joystick nos testes de retidão e odometria.

**Arena:** canvas 2D com grid, tags (pick em vermelho, place em verde), robô
(triângulo azul com cone de FOV), elipse do EKF, trilha executada e rota
planejada (segmentos FORWARD em tracejado).

**WebSocket (reconnect + anti-flapping):** backoff exponencial 500 ms → 10 s.
Guard contra sockets órfãos da dupla montagem do React 18 StrictMode.

### Duas topologias de rede

- **Modo DEV:** frontend no Mac (`npm run dev`, porta 5173); backend no Pi;
  `VITE_PI_WS_URL=ws://<IP_DO_PI>:8000/ws` obrigatório.
- **Modo OPERAÇÃO:** `npm run build` no Mac, `rsync dist/` para o Pi; o
  backend serve o SPA na porta 8000 — sem Node/npm no Pi, uma porta só, e o
  WebSocket resolve sozinho para o host da página.

Detalhes: [`src/frontend/README.md`](src/frontend/README.md).

---

## Simulação (sim-to-real)

Toda a lógica do Pi roda idêntica em `SIM=1` e `SIM=0`. A simulação substitui
duas peças de hardware atrás das mesmas interfaces:

| Componente | Real (`SIM=0`) | Simulado (`SIM=1`) |
|---|---|---|
| Câmera | `RealVisionSource` (OpenCV) | `SimVisionSource` (visão sintética, FOV 60°, ruído) |
| ESP32 | `PySerialTransport` (UART) | `FirmwareEmulator` (PID em Python, motor de 1ª ordem, τ=50 ms) |

As interfaces `VisionSource` e `SerialTransport` garantem que não existe
`if SIM` no código de navegação, controle ou missão.

**Injeção de falhas:** `serial_drop` (ESP32 ignora setpoints), `tag_hidden`
(visão retorna vazio), `wheel_slip` (multiplicadores por roda),
`vision_blur/drop` (probabilidade por frame), `encoder_noise`, `gyro_drift`.

**Mundo simulado:** cinemática diferencial com opção de slip por roda, clamp
na arena, trilha de 2000 pontos.

---

## Problemas encontrados e correções

### Hardware (bancada, 2026-07-06 e 2026-07-07)

1. **Canais dos motores trocados na fiação:** o canal A do L298n acionava a
   roda direita e o B a esquerda — as malhas PID ficaram cruzadas (cada PID
   lia um encoder e acionava a outra roda). Sintoma: uma roda saturava e a
   outra parava, alternando de lado entre testes. Corrigido por remapeamento
   em software. Lição: testar sempre um lado por vez (`--w-esq X --w-dir 0`).

2. **Encoder sobrecontando ~420 pulsos/volta:** estava nos GPIOs 34/35, que
   são input-only e sem pull-up interno — a linha flutuando gerava contagem
   por ruído. Refiado para os GPIOs 23/15 com `INPUT_PULLUP`. Na mesma
   mudança, a decodificação passou de x1 para x4 completa com tabela de
   transição.

3. **Robô ignorava STOP com encoder morto:** a integral acumulada segurava o
   duty no máximo. Correção: setpoint 0 vira parada incondicional que bypassa
   o PID.

4. **MPU-6050 dormindo / barramento I2C caindo:** (a) leituras todas zero com
   temp=36,53 °C indicam sensor dormindo (36,53 é o offset da fórmula de
   temperatura com raw=0); (b) todas zero com temp=0 + erro do Wire indicam
   queda do barramento (contato/EMI perto do L298n). Correções: o firmware
   auto-recupera após ~1 s; o GyroCalibrator descarta frames com
   `|accel| < 2 m/s²`.

5. **Gravação falhando ("chip stopped responding"):** um encoder estava
   alimentado pelo GPIO 2, que é pino de strapping de boot do ESP32.

6. **Ganhos de bancada ≠ chão (assumido):** o atrito estático impede a partida
   com comando baixo; a bateria caindo faz o PID saturar antes.

### Lógica (encontrados em simulação)

- AUTOMATICO congelava após 1 comando (control loop desacoplado do frontend)
- PARADO oscilava sem latch de segurança
- Integral do PID não resetava em PARADO
- ZREF=5 cm causava overshoot (ajustado para 15 cm)
- Perda de tag com offset lateral (bearing guard + histerese)
- Omega bang-bang (substituído por proporcional por bearing)
- FACE durava 1–2 ticks (imposto mínimo de 0,5 s)
- Parada falsa a 24–25 cm (dead zone com histerese)

### Convenções de sinal (fronteira sim↔real)

- Joystick x → ω negado (x+ = direita, ω+ = anti-horário)
- Visão x/pitch negados na fronteira (`pose.py`)
- Dock Manhattan calculado no frame do robô, não do mapa (bug de bancada)
- EKF corrige para o centro do robô (lente→eixo = 18 cm)
- Tilt da câmera 30° + offset z = −10 cm

---

## Decisões de projeto

- Arquitetura hierárquica de 3 camadas: Frontend → Pi → ESP32.
- Pi em Python/FastAPI/asyncio. ESP32 em C++/Arduino/PlatformIO.
- Frontend em React + Vite (navegador do celular).
- Frontend ↔ Pi: WebSocket. Pi ↔ ESP32: UART USB, JSON + CRC8.
- Garfo sempre manual — sem atuação autônoma no protocolo serial.
- Monorepo com três apps (`pi/`, `firmware/`, `frontend/`) + `docs/` + `scripts/`.
- Mapas em JSON — arena paramétrica, não hardcoded.
- PID de roda no ESP32 (100 Hz, C++); malha de posição no Pi (20 Hz, Python).
- Toda a fusão sensorial no Pi (firmware simples e determinístico).
- Simulação atrás de interfaces (`VisionSource`, `SerialTransport`), sem `if SIM`.

---

## Hardware

- Raspberry Pi + câmera USB (1280×720)
- ESP32 DevKit V1
- 2× ponte-H L298n (4 canais: 2 rodas + 1 garfo)
- 2× motor Lego NXT 53787 (rodas) com encoder de quadratura (1440 pulsos/volta, x4)
- Motor JGY-370 12 V com rosca sem-fim (garfo)
- IMU MPU-6050 (I2C)
- Alimentação: 3× 18650 em série (12,6 V) + BMS 3S 40A + regulador LM2596 (5,3 V)
- Arena: corredor 0,80 × 1,60 m com 6 AprilTags (tag25h9, 4 cm)
- Mapa: `corredor_6tags_80x160.json` (tags L1–L3 e R1–R3)

A parte elétrica (bateria, BMS, regulador, drivers, esquemáticos, datasheets,
caixas dos eletrônicos) está documentada em
[`Eletrônica/README.md`](Eletrônica/README.md).

---

## Quick start

### Simulação (sem hardware)

```bash
cd src
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

SIM=1 ./scripts/run_pi.sh           # backend em http://localhost:8000

cd frontend && npm install && npm run dev   # http://localhost:5173/demo
```

### Testes

```bash
python3 -m pytest pi/tests/ -v              # backend (210 testes)
cd frontend && npx vitest run               # frontend (11 testes)
python3 pi/tests/sim_sweep.py               # 9 cenários de aproximação
```

### Deploy no robô real

1. Copie `src/.env.example` para `src/.env` e configure `SIM=0`, a porta
   serial e a câmera.
2. No Pi: `pip install -e .` e `./scripts/run_pi.sh`
3. Frontend (modo operação): `npm run build` no Mac e copie `frontend/dist/`
   para o Pi — o backend serve o SPA em `http://<IP_DO_PI>:8000/`

Guia completo: [`src/docs/hardware-deployment.md`](src/docs/hardware-deployment.md)

---

## Números de referência

| Item | Valor |
|---|---|
| Arena | corredor 0,80 × 1,60 m, 6 tags (L1–L3, R1–R3) |
| AprilTag | família tag25h9, 4 cm |
| Câmera | USB, 1280×720; fx=fy=1023,6 · cx=634,1 · cy=377,1 (calibração 2026-07-07) |
| Tilt da câmera | 30° para baixo; offset z = −10 cm (lente→garfo); lente→eixo = 18 cm |
| Loops do Pi | 3 no startup (Vision · Serial · Control, 20 Hz cada); Telemetria via WS handler por conexão |
| PID firmware | 100 Hz, Kp=20 Ki=5 Kd=1, anti-windup ±500, PWM 20 kHz 8 bits |
| Encoders | quadratura x4, 1440 pulsos/volta |
| EKF | estado [x,y,θ]; heading 70% gyro + 30% odom; gate Mahalanobis 3,0 |
| SegmentExecutor | K_DIST=1,5 · K_HEADING=2,5 · tol. posição 2 cm · tol. heading 4° |
| Anti-atrito | v ≥ 0,09 m/s · \|ω\| ≥ 1,0 rad/s · ω_turn ≤ 1,6 rad/s |
| Serial | UART USB 115200 baud, 20 Hz, JSON + CRC-8/MAXIM + `\n` |
| Watchdogs | comando 400 ms · serial 250 ms · firmware 200 ms · tag-loss 250 ms |
| v_máx medida | 24 cm/s (100 cm em 4,16 s) → config 19 cm/s (80%, folga para PID + bateria) |
| Geometria | roda r=2,7 cm · entre-eixos 15 cm · standoff 15 cm |
| Missão | IDLE→LOAD_MAP→DRAW_TARGETS→GO_TO_PICK→AT_PICK→GO_TO_PLACE→AT_PLACE→GO_HOME→DONE (+FAULT) |

---

## Estrutura do monorepo `src/`

```
src/
├── pi/                    Backend Python (FastAPI + asyncio)
│   ├── app/
│   │   ├── control/       EKF, navegação, planejador, executor, Kalman, dock-to-tag
│   │   ├── mission/       Máquina de estados pick-and-place
│   │   ├── tasks/         3 loops asyncio (visão, serial, controle) + WS handler
│   │   ├── comms/         Protocolo serial (CRC8, framing, transporte)
│   │   ├── vision/        Detector AprilTag, calibração, pose (tilt, offsets)
│   │   ├── hardware/      Interfaces VisionSource / SerialTransport
│   │   ├── sim/           Emulador de firmware, visão sintética, falhas, mundo
│   │   ├── world/         Modelo de mundo, mapas (JSON/Pydantic), robô
│   │   ├── telemetry/     Agregador de telemetria
│   │   ├── config.py      Parâmetros centralizados
│   │   ├── models.py      4 contratos Pydantic
│   │   ├── state.py       Estado compartilhado (lock asyncio)
│   │   └── main.py        Ponto de entrada + rotas REST
│   ├── maps/              Mapas JSON da arena
│   ├── calibracao/        Intrínsecos da câmera (JSON)
│   └── tests/             210 testes pytest
├── firmware/              ESP32 (C++/PlatformIO)
│   └── src/               main, pid, motors, encoders, protocol, config
├── frontend/              React + Vite + Tailwind
│   └── src/
│       ├── pages/         Operador (/), Demo (/demo), Mapa (/map)
│       ├── components/    Joystick, DPad, Arena, Telemetria, Missão, Dock, etc.
│       ├── ws/            useWebSocket (reconnect, anti-flapping)
│       └── types/         contracts.ts (espelho TypeScript)
├── docs/                  Documentação técnica
└── scripts/               Scripts de operação e teste
```

---

## Mapa da documentação

### Ponto de entrada por app

| Documento | Conteúdo |
|-----------|----------|
| [`src/README.md`](src/README.md) | Visão geral do monorepo de software, como rodar e testar |
| [`src/pi/README.md`](src/pi/README.md) | Backend do Raspberry Pi |
| [`src/firmware/README.md`](src/firmware/README.md) | Firmware do ESP32 |
| [`src/frontend/README.md`](src/frontend/README.md) | Frontend React |
| [`Eletrônica/README.md`](Eletrônica/README.md) | Bateria, BMS, regulador, motores, drivers, sensores |

### Conceito e arquitetura

| Documento | Conteúdo |
|-----------|----------|
| [`src/docs/architecture.md`](src/docs/architecture.md) | Arquitetura de 3 camadas, EKF, decisões, parâmetros em aberto |
| [`src/docs/serial-protocol.md`](src/docs/serial-protocol.md) | Os 4 contratos de comunicação (fonte de verdade) |
| [`src/docs/navigation.md`](src/docs/navigation.md) | Planejador, executor, malha em cascata |
| [`src/docs/mission.md`](src/docs/mission.md) | Missão pick-and-place, API REST, garra manual |
| [`src/docs/dock-to-tag.md`](src/docs/dock-to-tag.md) | Aproximação por segmentos a uma tag |
| [`src/docs/maps.md`](src/docs/maps.md) | Formato JSON dos mapas da arena |
| [`src/docs/simulation.md`](src/docs/simulation.md) | Modo SIM=1, injeção de falhas, endpoints `/sim/*` |

### Hardware e operação

| Documento | Conteúdo |
|-----------|----------|
| [`src/docs/hardware-bring-up.md`](src/docs/hardware-bring-up.md) | Pinos, energia, montagem, calibração |
| [`src/docs/hardware-deployment.md`](src/docs/hardware-deployment.md) | Deploy no robô real, passo a passo |
| [`src/docs/hardware-interfaces.md`](src/docs/hardware-interfaces.md) | Interfaces `VisionSource` / `SerialTransport` (SIM↔real) |
| [`src/docs/camera-calibration.md`](src/docs/camera-calibration.md) | Calibração da câmera (xadrez OpenCV) |

### Testes e status

| Documento | Conteúdo |
|-----------|----------|
| [`src/docs/real-robot-test-plan.md`](src/docs/real-robot-test-plan.md) | Plano de testes no hardware em 3 fases |
| [`src/docs/readiness-sim-to-real.md`](src/docs/readiness-sim-to-real.md) | Auditoria de prontidão SIM→real |
| [`src/docs/simulator-to-real.md`](src/docs/simulator-to-real.md) | O que a simulação provou e o que não provou |
| [`src/docs/verification-status.md`](src/docs/verification-status.md) | Testes passando, bugs corrigidos |

### Apresentação e relatórios

| Documento | Conteúdo |
|-----------|----------|
| [`APRESENTACAO_SPEC.md`](APRESENTACAO_SPEC.md) | Roteiro técnico da apresentação (visão, controle, comunicação) |
| `Apresentações_&_Relatório/` | PDFs entregues: relatório pré-projeto, entrega de pré-projeto e entrega final |

---

## Verificação

| Teste | Resultado |
|-------|-----------|
| pytest (backend Pi) | 210 testes — 209 passam, 1 pulado |
| vitest (frontend) | 11/11 passam |
| sim_sweep (9 cenários de aproximação) | 9/9 convergem (parada a 15,0–16,3 cm; offset lateral ≤ 2,4 cm; heading ≤ 3,7°) |
| full_trace (13 cenários) | 12/13 (1 LOST esperado — tag fora do FOV) |
| Bancada 2026-07-07 | encoders x4, motores/sentido, PID, watchdog < 200 ms, CRC e MPU validados |
| Câmera | recalibrada em 2026-07-07 (1280×720, câmera nova) |
| v_máx no chão | cronometrada: 100 cm em 4,16 s = 24 cm/s → config 19 cm/s |

## Status

| Item | Estado |
|------|--------|
| Lógica + simulação | Validado (210 pytest + 9/9 sim_sweep) |
| Firmware ESP32 | Pronto para gravar |
| Backend Pi (câmera + serial) | Implementado |
| Calibração da câmera + mapa real | Feito |
| Bancada (encoders, motores, PID, watchdogs) | Validado |
| Dock-to-tag | Implementado, aprovado em teste de unidade |
| Modo operação (Pi serve o frontend) | Funcionando |
| Fase 2 — manual no chão | Pendente |
| Fase 3 — autonomia no chão | Pendente |

## Tech stack

| Camada | Stack |
|--------|-------|
| Pi | Python 3.11+ · FastAPI · asyncio · OpenCV · pupil-apriltags · filterpy · Pydantic · pyserial-asyncio |
| ESP32 | C++ · Arduino · PlatformIO · ArduinoJson |
| Frontend | React 18 · Vite · Tailwind CSS |
