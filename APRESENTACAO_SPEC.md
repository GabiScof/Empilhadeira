# Apresentação — Empilhadeira Robótica Autônoma

Conteúdo organizado em três partes: (1) Visão, (2) Controle, (3) Comunicação.
A lógica está completa e validada em simulação e bancada; a autonomia no chão
ainda não rodou. Números extraídos do código e dos documentos do repositório.

---

## Visão geral do projeto

Empilhadeira robótica em escala reduzida que transporta pallets
(~15 cm de lado) em ambiente controlado, com dois modos de operação:

- MANUAL — operador dirige por joystick virtual no celular (navegador).
- AUTOMÁTICO — o robô navega sozinho entre AprilTags fixadas no mapa e
  executa uma missão pick-and-place: sorteia/recebe duas tags-alvo, navega
  até a de *pick*, para e espera o operador acionar o garfo, navega até a de
  *place*, espera o garfo de novo e volta para *home*.
- Regra de projeto: o garfo é sempre manual nos dois modos (canal de
  comando independente; nunca entra na malha autônoma).

Arquitetura hierárquica de 3 camadas (decisão fechada):

```
┌──────────────────────────────────────────────────────┐
│  FRONTEND — celular (React + Vite, navegador)         │
│  joystick · telemetria · missão · mapa · garfo        │
└──────────▲──────────────────────────┬─────────────────┘
     (2) telemetria @20Hz      (1) comando
         WebSocket / Wi-Fi            ▼
┌──────────┴─────────────────────────────────────────────┐
│  RASPBERRY PI — alto nível (Python, FastAPI + asyncio)  │
│  4 tarefas concorrentes: WebSocket · Vision Loop ·      │
│  Serial Loop · Control Loop                             │
│  AprilTag → EKF 2D → planejador → executor → setpoint   │
└──────────▲──────────────────────────┬───────────────────┘
     (4) sensores               (3) setpoint
     UART USB 115200, 20 Hz — JSON + CRC8 + \n
                                      ▼
┌──────────┴───────────────────────────────────────────────┐
│  ESP32 — baixo nível, tempo real (C++/Arduino, PlatformIO)│
│  PID por roda ~100 Hz · encoders · MPU-6050 · PWM → L298n │
└───────────────────────────────────────────────────────────┘
```

Simulação primeiro (sim-to-real):
toda a lógica do Pi (controle, missão, EKF, navegação, telemetria, protocolo)
roda idêntica em `SIM=1` e `SIM=0` — a simulação substitui exatamente duas
peças de hardware (câmera → visão sintética; ESP32 → emulador de firmware)
atrás das mesmas interfaces (`VisionSource`, `SerialTransport`). Resultado:

| Verificação (2026-06-23) | Resultado |
|---|---|
| pytest (backend Pi) | 162/162 passam |
| vitest (frontend) | 11/11 passam |
| `sim_sweep.py` (9 cenários de aproximação) | 9/9 convergem (parada a 15,0–16,3 cm; offset lateral ≤ 2,4 cm; erro de heading ≤ 3,7°) |
| `full_trace.py` (13 cenários) | 12/13 (o 13º é LOST esperado — tag fora do FOV) |

Linha do tempo (commits): 12/05 início (aula, scripts de AprilTag) →
26/05 scaffold do monorepo → 02/06 visão v1 → 09/06 firmware ESP32 + protocolo
serial → 15–16/06 simulação completa + frontend v1 → 23/06 integração
(EKF, planejador, missão, mapas, docs) → 03/07 calibração da câmera antiga +
correções → 06/07 dia de bancada no robô real (encoders, motores, sinais,
v_máx medida, dock-to-tag, D-pad) → 07/07 câmera nova remontada (tilt de 30°)
e recalibrada a 1280×720.

Estado em 2026-07-06: eletrônica validada na
bancada (encoders, motores, PID convergindo, watchdogs, telemetria/CRC/MPU) e
v_máx medida no chão; Fase 2 (manual no chão) e Fase 3 (autonomia) do plano
de testes ainda não rodaram no hardware — a autonomia completa foi validada
apenas em simulação e testes de unidade.

Hardware: Raspberry Pi + câmera USB · ESP32 · 2× ponte-H L298n · 2 motores
Lego NXT 53787 (rodas) + motor JGY-370 12 V com rosca sem-fim (garfo) ·
encoders de quadratura 1440 pulsos/volta (decodificação x4) · IMU MPU-6050
(I2C) · arena real: corredor 0,80 × 1,60 m com 6 AprilTags
(mapa `corredor_6tags_80x160.json`).

---

## Parte 1 — Visão

### 1.1 O que a visão faz

É o único sensor absoluto do robô. Ela responde duas perguntas:
1. **Reativa:** "onde está a tag à minha frente?" → `z_cm` (distância),
   `x_cm` (deslocamento lateral), `pitch_deg` (ângulo da face da tag) — usados
   pela aproximação reativa e pelo dock-to-tag.
2. **Global:** "onde o robô está no mapa?" → cada tag detectada tem pose conhecida
   no mapa JSON; por PnP inverte-se a observação e obtém-se a pose absoluta do
   robô, que corrige o EKF (a odometria sozinha deriva).

### 1.2 Pipeline

```
Câmera USB (1280×720) → grayscale → pupil-apriltags (tag25h9, PnP com
intrínsecos) → detecções {id, pose_R, pose_t} →
  ├─ VisionState (tag mais próxima): detectado, id, z_cm, x_cm, pitch_deg
  └─ TagObservations (todas as tags) → correção do EKF [x, y, θ]
```

- **Biblioteca:** `pupil-apriltags` (bindings do detector oficial da AprilRobotics)
  + OpenCV. Família `tag25h9`.
- **Detector:** `quad_decimate=2.0` (detecção em meia resolução, cantos
  refinados em resolução cheia — perda de precisão de pose desprezível,
  custo ~4x menor), `refine_edges=1`, `decode_sharpening=0.25`,
  `estimate_tag_pose=True` com `camera_params=(fx,fy,cx,cy)` e
  `tag_size=0,04 m`.
- Tamanho físico da tag: **4 cm** (0,04 m) — medido e reconciliado nos três
  lugares que precisam concordar (config do Pi, mapas JSON, default do
  detector). Se a tag impressa não tiver exatamente 4 cm, o `z` sai
  proporcionalmente errado (checagem com paquímetro está no plano de teste).
- **Vision Loop:** tarefa asyncio a 20 Hz; a leitura bloqueante da câmera
  (OpenCV) roda em `asyncio.to_thread` para não travar o event loop do
  backend. Um frame por tick alimenta tanto o estado reativo quanto o EKF
  (sem captura dupla).

### 1.3 Calibração da câmera (recalibração 2026-07-07)

- Câmera nova, remontada com tilt de 30°; recalibrada em 2026-07-07 com
  tabuleiro de xadrez OpenCV (`findChessboardCorners` + `calibrateCamera`)
  a **1280×720**.
- Intrínsecos atuais (`pi/calibracao/camera_intrinsics.json`):
  `fx=fy=1023,63 · cx=634,08 · cy=377,08`, com coeficientes de distorção
  completos `[k1,k2,p1,p2,k3] = [0,0403, -0,0243, 0,0029, -0,0019, -0,0493]`;
  cx/cy a 6/17 px do centro geométrico da imagem. Erro de reprojeção não
  registrado no JSON.
- Histórico: a calibração de 03/07 (câmera antiga, 640×480, 28 fotos, cantos
  internos 8×5, quadrado de 3 cm, erro de reprojeção 0,144 px, cx=399 —
  anômalo) foi descartada junto com a câmera.
- Regra: a resolução de captura tem que ser a mesma da calibração
  (1280×720, `CAMERA_FRAME_WIDTH/HEIGHT` no config); com
  `REQUIRE_CAMERA_CALIBRATION=1` o backend se recusa a subir em modo real
  sem calibração válida.
- Validação planejada com fita métrica: tag a 30,0 cm → `z` entre 28,5–31,5 cm;
  ainda detectar a 15 cm (standoff de navegação); anotar alcance máximo.

### 1.4 Mundo paramétrico (mapas)

A arena não é hardcoded: mapas JSON em `pi/maps/` declaram dimensões, tags
(`position_id`, `x_m`, `y_m`, parede, `yaw_deg`), pose inicial, pose *home* e
grafo opcional de waypoints. Trocar de arena = trocar um arquivo. O mapa real
medido é `corredor_6tags_80x160.json` (0,80×1,60 m, tags L1–L3 e R1–R3).
Schema validado por Pydantic (IDs únicos, tags dentro da arena, arestas do
grafo válidas).

### 1.5 Fusão visão + IMU + odometria (EKF 2D)

- Estado `[x, y, θ]`. **Predição** @20 Hz: odometria dos encoders + giroscópio
  Z (mistura de heading: 70% gyro / 30% odometria).
- **Correção** quando vê tag: pose absoluta por PnP contra o mapa; ruído de
  observação escalado pela qualidade da detecção (`decision_margin`);
  **gating de Mahalanobis a 3σ** rejeita detecções inconsistentes com a
  estimativa corrente (um falso positivo não desloca a pose estimada).
- Telemetria exporta elipse de covariância 95% para desenhar a incerteza na UI.

### 1.6 Visão sintética (simulação)

Em `SIM=1` a câmera é substituída por um modelo analítico: FOV 60°, alcance
3–150 cm, ruído gaussiano de ±0,2 cm / ±0,5°, com injeção de falhas
(`tag_hidden`, `vision_blur`, `vision_drop`). Os 9/9 cenários de aproximação
foram validados nesse modo, antes do hardware existir.

### 1.7 Dock-to-tag (06/07)

Modo ligado por default (`DOCK_TO_TAG_ENABLED = True` desde 2026-07-07): o
robô vê uma tag, planeja uma única vez uma rota de segmentos discretos
(FORWARD/TURN) até um standoff de 15 cm de frente para a tag e executa por
odometria/EKF — a mesma maquinaria da missão (SegmentExecutor), sem
pick/place. Por isso serve de ensaio para a navegação da missão. Segmentos
discretos toleram perder a tag do FOV numa curva de 90° (não é servo contínuo). Dois
modos: `line_of_sight` (default; usa só z/x, não depende de convenção de yaw)
e `tag_normal` (esquadra com a face da tag; aguarda validação do sinal do
`pitch_deg` no hardware). Estados: SEEKING → DOCKING → DONE/FAULT; teste
fechado exige estacionar a < 5 cm do standoff. Junto veio o endpoint
`GET /world-state`, que faz a "vista de cima" da UI funcionar no robô real.

### 1.8 Problemas de visão encontrados e correções

1. **Sinal do X invertido** — o frame óptico do OpenCV tem x positivo = tag à
   direita; a convenção do projeto (herdada do simulador e da navegação) é
   x positivo = tag à esquerda. Sem a negação na fronteira (`pose.py`), a
   autonomia real viraria para o lado oposto da tag — em simulação o problema
   não aparecia porque a visão sintética já nascia na convenção do projeto.
   Corrigido em 06/07. Lição: converter convenções na fronteira entre os dois
   mundos e validar sinais no hardware um a um.
2. **Tamanho da tag inconsistente (5 cm vs 4 cm)** — o legado usava 0,05 m;
   a tag impressa real tem 4 cm. Como `z` escala linearmente com o tamanho
   declarado, isso era um erro sistemático de 25% em toda distância.
   Reconciliado para 0,04 m nos três lugares de uma vez (config, mapas,
   detector).
3. **`dist_coeffs` em formato dict** — a calibração salva os coeficientes como
   dicionário nomeado; o loader passou a aceitar dict OU lista e reordenar
   para o formato OpenCV `[k1,k2,p1,p2,k3]`.
4. **OpenCV quebrado no Pi** — instalações duplicadas/parciais do OpenCV
   deixavam `cv2` sem `VideoCapture`; o harness `teste_cam.py` agora falha
   cedo com diagnóstico claro e receita de correção, e detecta automaticamente
   o modo headless quando rodando via SSH (sem display).
5. **Resolução ≠ calibração (resolvido)** — a 2ª calibração (2026-07-07) é em
   1280×720, que agora coincide com o default do config. Intrínsecos só valem
   na resolução em que foram medidos — o vision_loop força o `image_size` do
   JSON de calibração na captura.
6. **Ambiguidade de pose / convenção de yaw (aberto e assumido)** — estimar a
   orientação de uma tag pequena tem ambiguidade conhecida; a extração de
   Euler da câmera real ainda não foi validada contra o simulador
   (`TODO(equipe)` explícito). Por isso o dock usa `line_of_sight` por default.

---

## Parte 2 — Controle

### 2.1 A ideia central: malha em cascata (2 níveis, 2 processadores)

```
Pose alvo (mapa)
   ↓
PathPlanner  → lista de segmentos [FORWARD 1.2m, TURN 90°, ...]
   ↓
SegmentExecutor — malha externa no Pi @20 Hz
   pose do EKF → (v, ω) → (ω_esq, ω_dir) em rad/s
   ↓  setpoint via serial
PID por roda no ESP32 — malha interna @100 Hz
   ω medido (encoder) → duty PWM → L298n → motor
```

Regra: o Pi nunca duplica o PID de roda — a malha externa cuida de
posição/heading, a interna de velocidade. Divisão também de *tempo real*: o
ESP32 garante determinismo a 100 Hz; o Pi roda a 20 Hz com Python/asyncio.

### 2.2 Baixo nível (ESP32 — C++/Arduino/PlatformIO)

- **PID por roda @100 Hz:** ganhos iniciais **Kp=20, Ki=5, Kd=1** (motores
  Lego NXT a 12 V via L298n), anti-windup com integral limitada a ±500.
  Sintonia final planejada por Ziegler-Nichols no chão (os ganhos foram
  acertados com a roda no ar; com carga a dinâmica muda — overshoot ~10%
  já observado a 8 rad/s).
- **PWM:** LEDC do ESP32 a 20 kHz (acima da faixa audível), 8 bits (0–255).
- **Encoders de quadratura, decodificação x4:** interrupções em CHANGE nas
  duas fases, tabela de transição de 16 entradas (ISR em IRAM; transição
  inválida = 0, o que cancela bounce naturalmente) → **1440 contagens/volta**.
- **IMU MPU-6050 cru pela serial:** acelerômetro ±2g e gyro ±250°/s enviados
  crus (m/s², °/s) — toda a fusão é feita no Pi (decisão: manter o firmware
  simples e determinístico; a filtragem fica onde há ponto flutuante e testes
  fáceis).
- **Watchdog local:** sem setpoint válido por **200 ms** (4 mensagens perdidas
  @20 Hz) → motores zerados + PID resetado. É a última linha de defesa, não
  depende de nada acima.
- **Garfo:** duty fixo, rosca sem-fim segura a carga parada (sem esforço em
  PARAR); fins-de-curso previstos no código mas desabilitados (não montados).

### 2.3 Alto nível (Pi — Python)

- **EKF 2D `[x, y, θ]`** (detalhes na Parte 1): predição por
  odometria + gyro, correção por AprilTag, gating 3σ.
- GyroCalibrator — calibração automática no boot: com o
  robô parado ~2–3 s, usa a gravidade para descobrir qual eixo do
  MPU aponta para cima, o sinal do yaw (projeção do gyro no vetor "up" de
  um sensor destro) e o bias de taxa-zero (com rastreamento térmico lento
  por EMA). Consequência prática: a posição/orientação física do MPU no chassi
  não importa — o sensor pode ser remontado sem mudança de código.
  Procedimento de boot: robô imóvel em chão firme por 3 s (pneus macios
  balançam o chassi; calibrar com o chassi oscilando faz o heading derivar).
- **PathPlanner:** A* sobre o grafo de waypoints do mapa quando existe;
  fallback Manhattan (alinha X, depois Y) quando não. Saída: segmentos
  FORWARD/TURN com pose-alvo.
- **SegmentExecutor (malha externa):** FORWARD com `v = K_DIST·dist` e correção
  de heading `ω = K_HEADING·erro` (se o erro de heading passa de 45°, para e
  gira primeiro); TURN girando no lugar até tolerância de ~2°; tolerância de
  posição 2 cm; timeout de segmento → FAULT da missão.
- **Navegação reativa legada (1 tag): APPROACH → FACE → RETREAT**, controle
  por *bearing* proporcional, desaceleração limitada
  (`v = √(2·a·d)`), zona morta com histerese, detector de oscilação (conta
  trocas de sinal de ω numa janela) com fallback. Uma análise comparativa
  (Stanley, Pure Pursuit, bearing unificado — `compare_nav.py`) concluiu que o
  mode-switching reativo é o adequado para robô diferencial com câmera frontal;
  o Stanley ficou no repo como alternativa experimental.
- **Máquina de missão pick-and-place:**
  `IDLE → LOAD_MAP → DRAW_TARGETS → GO_TO_PICK → AT_PICK → GO_TO_PLACE →
  AT_PLACE → GO_HOME → DONE`, com ramo FAULT de qualquer estado. Em AT_* o
  robô para e espera o operador acionar o garfo e clicar
  "continuar". Sorteio de alvos com seed reprodutível.
- **Modos de operação:** MANUAL / AUTOMÁTICO / PARADO com **latch de
  segurança** — parada por segurança trava e só um comando explícito do
  operador destrava (sem o latch, o loop de 20 Hz re-entraria no modo ativo a
  cada tick, oscilando).

### 2.4 Números de calibração medidos

| Grandeza | Valor | Como |
|---|---|---|
| v_máx real no chão | **24,0 cm/s** | cronometrado: 100 cm em 4,16 s em comando máximo (06/07) |
| `MAX_LINEAR_SPEED` | **19 cm/s** (~80% da medida) | folga p/ PID + queda de bateria |
| `MAX_ANGULAR_SPEED` | 2,5 rad/s (provisório) | derivado do teto físico; falta cronometrar 1 volta |
| Raio da roda | 2,7 cm | medição da equipe; confirmar por teste de rolagem (o pneu deforma sob carga) |
| Entre-eixos (wheelbase) | 15 cm | refinar pelo giro de 360° |
| Encoder | 1440 pulsos/volta (x4) | validado na bancada, ±sinais conferidos |
| Standoff de aproximação | 15 cm (ZREF) | 5 cm causava overshoot na sim |
| PID roda | Kp=20 · Ki=5 · Kd=1, integral ±500 | inicial; Ziegler-Nichols no chão se precisar |

### 2.5 Problemas de controle encontrados e correções

1. **Canais dos motores trocados na fiação (bancada, 06/07):**
   o canal A do L298n acionava a roda direita e o B a esquerda — o inverso do
   rótulo do código de referência da eletrônica. Com isso as malhas PID
   ficaram cruzadas: cada PID lia o encoder de uma roda e acionava a outra.
   Sintoma: uma roda saturava no máximo e a outra morria, alternando o
   lado aleatoriamente entre testes (realimentação positiva: o PID acelera, a
   "sua" roda não responde, integral explode). Corrigido por remapeamento em
   software no `config.h`. Lição: testar sempre um lado por
   vez (`--w-esq X --w-dir 0`) — o teste com as duas rodas juntas não detecta
   canais trocados.
2. **Encoder esquerdo sobrecontando ~420 pulsos/volta:** estava nos GPIOs
   34/35, que são input-only e não têm pull-up interno — linha flutuando
   = contagem por ruído. Refiado no mesmo dia para 23/15 (com `INPUT_PULLUP`).
   Na mesma intervenção, a decodificação passou de x1 para x4 completa com
   tabela de transição, que rejeita bounce por construção.
3. **Parada incondicional em setpoint zero:**
   com um encoder morto (medida=0), o comando de parar tinha erro 0 mas a
   integral acumulada segurava o duty no máximo — o robô ignorava o comando
   de parada. Correção de segurança no firmware: setpoint 0 = parada
   incondicional que bypassa o PID e reseta a integral. O robô fica seguro e
   dirigível mesmo com encoder com defeito.
4. **MPU-6050 em sleep / barramento I2C caindo:** duas assinaturas distintas
   diagnosticadas no stream: (a) tudo-zero com `temp = 36,53 °C` = sensor
   em sleep (o I2C responde 14 bytes zerados; 36,53 °C é o offset da fórmula
   de temperatura com leitura crua = 0, o que identifica a condição);
   (b) tudo-zero com `temp = 0` + erro do driver Wire = queda do barramento
   (contato/EMI perto do L298n).
   Correções: o firmware se recupera re-enviando o wake após ~1 s de
   leituras mortas; e o GyroCalibrator no Pi descarta frames mortos
   (‖accel‖ < 2 m/s² é fisicamente impossível com o sensor operando)
   para não corromper a média de gravidade nem erodir o bias.
5. **Oscilação com heading > 45° → fase COARSE_ALIGN:** quase perpendicular à
   tag, recalcular ω a cada frame criava um ciclo-limite (pequenas rotações
   trocavam o sinal da leitura). Correção: girar com ω fixo e direção travada
   na entrada, com histerese (entra a 45°, sai a 35°), e só então APPROACH.
6. **Gravação do firmware falhando (`chip stopped responding`):** os encoders
   estavam alimentados pelos GPIOs 2/4 — e o GPIO 2 é pino de strapping de
   boot do ESP32. Sequência de troubleshooting documentada (segurar BOOT,
   desconectar o fio do GPIO 2, desligar a fonte 12 V durante a gravação).
7. **Ganhos de bancada ≠ chão (assumido no prontuário):** atrito estático faz
   o robô não partir com comando baixo (comportamento esperado — a integral
   acumula devagar); bateria caindo faz o PID saturar antes.

### 2.6 Bugs encontrados em simulação antes do hardware

Bugs corrigidos ainda em sim: AUTOMÁTICO congelava após 1 comando (control
loop desacoplado do frontend), PARADO oscilava sem latch, deadlock de rotação
no fallback, integral do PID não resetava em PARADO, ZREF=5 cm com overshoot
(→15 cm), perda de tag com offset lateral (bearing guard + histerese), omega
bang-bang (→ proporcional por bearing), FACE de 1–2 ticks (→ mínimo 0,5 s),
parada falsa a 24–25 cm (dead zone com histerese). Nenhum deles precisou do
robô físico para ser encontrado.

---

## Parte 3 — Comunicação

### 3.1 Os 4 contratos congelados

O sistema tem exatamente 4 contratos de dados, documentados em
`serial-protocol.md` e espelhados em três linguagens: Pydantic (Python/Pi),
structs C++ (firmware) e TypeScript (frontend). Mudou o contrato, muda nos
três.

```
(1) comando    Frontend → Pi     WebSocket/Wi-Fi   JSON       {modo, joystick{x,y}, garfo, ts_ms}
(2) telemetria Pi → Frontend     WebSocket @20 Hz  JSON       estado, rodas, imu, visão, EKF, missão, nav, dock, tags, mapa, parado_reason
(3) setpoint   Pi → ESP32        UART @20 Hz       JSON+CRC8  {"w_esq":rad/s, "w_dir":rad/s, "garfo":"subir|descer|parar"}
(4) sensores   ESP32 → Pi        UART @20 Hz       JSON+CRC8  {enc{esq,dir}, mpu{ax..gz,temp_c}, bms:null}
```

### 3.2 Serial Pi ↔ ESP32 (UART USB, 115200 baud, 20 Hz)

- **Framing:** `<json compacto>*<crc8 em 2 hex minúsculos>\n`.
  Exemplo real: `{"w_esq":1.5,"w_dir":1.5,"garfo":"parar"}*a3\n`.
- **Checksum CRC-8/MAXIM (Dallas/1-Wire)** — polinômio 0x31 refletido,
  implementado idêntico em Python e C++, com testes de unidade dos dois lados
  comparando vetores conhecidos.
- Descarte de frames inválidos: os decodificadores dos dois lados são
  incrementais (byte a byte), ressincronizam no `\n` e descartam o frame
  inteiro em CRC/JSON/schema inválido — frame ruim nunca vira comando; no pior
  caso vira watchdog.
- No Pi, o transporte é `pyserial-asyncio` dentro do Serial Loop @20 Hz: envia
  o setpoint corrente, lê frames de sensores, alimenta o Kalman de atitude e a
  predição do EKF a cada tick.

### 3.3 WebSocket + REST (Pi ↔ celular)

- **FastAPI** com WebSocket `/ws`: comandos entram validados por Pydantic
  (inválido = descartado com warning, nunca derruba o handler); telemetria sai
  a 20 Hz. Desconectou → `force_stop` imediato + comando limpo.
- **REST:** mapas (`GET /maps/list`, `POST /maps/load/{name}`,
  `GET /maps/{name}`, `GET /maps/current`), missão (`/mission/start`,
  `/continue`, `/reset`, `/state`), dock (`/dock/enable`, `/disable`,
  `/state`), `GET /world-state` (vista de cima real). Em SIM, endpoints extras
  de injeção de falha (`/sim/inject-fault`: serial_drop, tag_hidden,
  wheel_slip, vision_blur/drop, encoder_noise, gyro_drift), reset de pose e
  `debug-dump` completo (exportável em TXT/CSV pela UI).
- Frontend React + Vite + Tailwind, páginas: operador (joystick, D-pad,
  garfo, modo, telemetria, alertas), mapa e demo (arena vista de cima, missão,
  injeção de falhas, export de debug).

### 3.4 Cadeia de segurança fim-a-fim

Cada enlace tem seu próprio watchdog — a falha de qualquer elo para o robô:

| Elo que cai | Vigia | Limite | Ação |
|---|---|---|---|
| Celular↔Pi (Wi-Fi, em MANUAL andando) | Command watchdog (Pi) | **400 ms** | PARADO com latch, motivo `command_watchdog` |
| WebSocket fecha | Handler (Pi) | imediato | `force_stop` + comando limpo |
| Tag some em AUTOMÁTICO | Tag-loss (Pi) | 5 frames (~250 ms) | PARADO com latch (suspenso durante missão/dock — a tag sai do FOV em curvas normais; aí valem PARADO na UI e os watchdogs abaixo) |
| UART para de entregar sensores | Serial lost-frames (Pi) | 5 ciclos (~250 ms) | `force_stop`, motivo `serial_loss` |
| Setpoint para de chegar no ESP32 | Setpoint timeout (firmware) | **200 ms** | motores zerados + PID resetado, local, independe de tudo |

- O **latch** existe porque o control loop repropõe o modo do operador a
  20 Hz — sem trava, o robô re-entraria no modo ativo a cada tick.
- Os valores foram fechados como contrato: 400 ms > RTT alvo (<170 ms) +
  heartbeat do frontend (100 ms); o 200 ms do firmware = 4 mensagens perdidas.
- Validado na bancada: Ctrl-C com rodas girando → parada em menos de 200 ms.

### 3.5 D-pad "Comando exato" (06/07)

Painel com botões que enviam vetores puros: Frente = ω exatamente 0
(reta), Gira = v exatamente 0 (giro no lugar), em 30/60/100% da
velocidade máxima — remove a variação manual do joystick dos testes de
retidão e odometria (1 m medido com fita; 360° e conferir o heading).
Cada botão re-envia o vetor a cada 100 ms (heartbeat) para satisfazer o
command watchdog de 400 ms; ao soltar, envia `{0,0}` imediatamente.

### 3.6 Duas topologias de rede (decisão operacional)

- **Modo dev** (desenvolvimento): frontend servido pelo Mac (`npm run dev`,
  porta 5173, exposto na rede), backend no Pi; o celular abre a página do Mac
  e o WebSocket aponta para o Pi via `VITE_PI_WS_URL=ws://<IP_DO_PI>:8000/ws`
  (obrigatório neste modo — o fallback de mesmo-host apontaria para o Mac).
- **Modo operação** (demo/desafio): `npm run build` no Mac, `rsync` do `dist/`
  para o Pi, e o backend FastAPI serve o frontend estático na própria porta
  8000 (montado por último, com fallback SPA para o BrowserRouter) —
  sem Node/npm no Pi, uma porta só, e o WebSocket resolve sozinho para o
  host da página. O celular abre `http://<IP_DO_PI>:8000/`.

### 3.7 Problemas de comunicação encontrados e correções

1. **WebSocket "flapping" (React 18 StrictMode):** em dev, o StrictMode monta
   componentes duas vezes; o socket órfão da primeira montagem disparava
   `onclose` e agendava reconexões em cima do socket vivo — tempestade de
   conexões, UI alternando "Conectado/Desconectado". Correção: todo handler
   valida `wsRef.current !== ws` (socket órfão é ignorado), `connect()` não
   abre se já há socket OPEN/CONNECTING, cleanup anula os handlers antes de
   fechar, e reconexão tem backoff exponencial 500 ms → 10 s.
2. **Watchdog de comando 500 → 400 ms:** valor renegociado ao unificar os
   branches (contrato de segurança adotado do main), documentado em todos os
   docs afetados.
3. **Watchdog serial existia mas não estava ligado:** o `SERIAL_LOST_FRAMES`
   foi efetivamente conectado ao `serial_loop_real` num fix dedicado — lição:
   segurança não é o parâmetro existir, é o caminho de código rodar.
4. **`VITE_PI_WS_URL` ignorado:** o frontend não honrava a env e conectava no
   host errado no modo DEV; corrigido como parte do "contrato" de env
   (`envDir` apontando para o `.env` do monorepo).
5. **uvicorn/uv:** migração da toolchain para `uv` + `uvicorn[standard]`
   (inclui websockets/uvloop) com lockfile — deploy reprodutível no Pi;
   `requirements.txt` completo e fixado para o deploy real.
6. **Porta serial é uma só:** monitor do PlatformIO, script de bancada e
   backend disputam a UART (`Device or resource busy`) — virou regra
   operacional no plano de testes: fechar um antes de abrir o outro.
7. **BMS previsto no contrato mas não integrado:** o campo `bms` viaja como
   `null` — o contrato já reserva o lugar sem quebrar ninguém quando chegar.

---

## 4. Status (2026-07-07)

Feito e validado
- Lógica completa validada em simulação: 162 testes backend + 11 frontend,
  9/9 cenários de aproximação convergem, missão completa em 4 mapas.
- Bancada (06/07): encoders x4 validados (sinais, PPR 1440, isolamento),
  canais/sentido dos motores corrigidos e conferidos um a um, PID convergindo,
  watchdog serial < 200 ms medido, telemetria/CRC/MPU sãos, todas as
  convenções de sinal do firmware confirmadas no stream cru.
- Câmera nova recalibrada (07/07, 1280×720, fx=fy=1023,63) após remontagem
  com tilt de 30°.
- v_máx medida no chão (24 cm/s) e configurada com folga (19 cm/s).
- Dock-to-tag + vista de cima real implementados e passando em teste de unidade.
- Modo operação (Pi sozinho servindo tudo, sem Node) funcionando.

Falta (em ordem, do plano de testes)
- Fase 2 no chão: manual completo (retidão, ré, sinais de giro no chão),
  garfo com carga, watchdogs com o robô em movimento, sanidade de odometria
  (1 m e 360°).
- Medições restantes: raio por rolagem, bitola refinada, ω máx cronometrado,
  offset câmera→garfo, tag no paquímetro.
- Últimas convenções de sinal no hardware: `x_cm` (tag à esquerda → positivo),
  `pitch_deg`, sinal do `gz` no giro à mão.
- Fase 3 inteira (autonomia) ainda não rodou no hardware: aproximação reativa
  → segurança em autonomia → EKF no corredor → dock → missão 3× seguidas →
  ensaio geral do dia D.

Riscos conhecidos e mapeados (prontuário): ganhos de bancada vs chão,
raio efetivo desigual entre pneus, queda de tensão da bateria (PID satura
antes), Wi-Fi do local com RTT > 400 ms, escorregamento nas curvas de 90°
degradando odometria, tag impressa fora de medida. Cada um com sintoma e
ação documentados.

---

## 5. Lições de engenharia

1. Simulação com as mesmas interfaces compensa o investimento: dezenas de
   bugs de lógica foram corrigidos antes do robô existir; no hardware sobraram
   só os bugs de hardware (fiação, sinais, ruído) — os que a simulação não cobre.
2. Convenções de sinal são a fronteira mais arriscada do sim-to-real:
   OpenCV vs projeto, joystick vs ω, encoder vs sentido — todos os bugs de
   06/07 foram de sinal, nenhum de lógica. Validar um a um, com checklist.
3. Segurança em camadas independentes: 5 watchdogs em 3 processadores;
   qualquer elo caindo para o robô, e o de baixo (200 ms no firmware) não
   depende de nada acima.
4. Teste um grau de liberdade por vez: o teste com as duas rodas juntas
   não detecta canais trocados; o D-pad de comandos puros existe pelo mesmo
   motivo.
5. Contratos congelados e espelhados em 3 linguagens evitam a deriva
   frontend/Pi/firmware; frame inválido se descarta, não se interpreta.
6. Parâmetro medido em vez de estimado: v_máx cronometrada com fita e
   gravada a 80%; nenhum valor inventado (política "não inventar valores",
   com `TODO(equipe)` em cada placeholder).
7. Diagnóstico escrito vira ativo: as duas assinaturas de falha do MPU e o
   prontuário de sintomas aceleram o diagnóstico do próximo bug.

---

## Apêndice — Tabela de números para consulta rápida

| Item | Valor |
|---|---|
| Arena real | corredor 0,80 × 1,60 m, 6 tags |
| AprilTag | família tag25h9, **4 cm** |
| Câmera | USB, **1280×720**, fx=fy=1023,63 · cx=634,08 · cy=377,08 (recalibração 2026-07-07, xadrez OpenCV, pós-remontagem com tilt de 30°) |
| Loops no Pi | Vision 20 Hz · Serial 20 Hz · Control 20 Hz · Telemetria 20 Hz |
| PID firmware | 100 Hz, Kp=20 Ki=5 Kd=1, anti-windup ±500, PWM 20 kHz 8 bits |
| Encoders | quadratura x4, 1440 pulsos/volta |
| EKF | estado [x,y,θ]; heading 70% gyro + 30% odom; gate Mahalanobis 3σ |
| Serial | UART USB 115200 baud, 20 Hz, JSON + CRC-8/MAXIM + `\n` |
| Watchdogs | comando 400 ms · serial 5 frames (~250 ms) · firmware 200 ms · tag-loss 5 frames · WS disconnect imediato |
| Velocidades | v_máx medida 24 cm/s → config 19 cm/s · ω 2,5 rad/s (provisório) |
| Geometria | roda r=2,7 cm · entre-eixos 15 cm · standoff 15 cm |
| Missão | IDLE→LOAD_MAP→DRAW_TARGETS→GO_TO_PICK→AT_PICK→GO_TO_PLACE→AT_PLACE→GO_HOME→DONE (+FAULT) |
| Verificação | 162 pytest + 11 vitest + 9/9 sim_sweep + 12/13 full_trace |
| Stack | Pi: Python/FastAPI/asyncio/OpenCV/pupil-apriltags/filterpy · ESP32: C++/Arduino/PlatformIO/ArduinoJson · Front: React/Vite/Tailwind |
