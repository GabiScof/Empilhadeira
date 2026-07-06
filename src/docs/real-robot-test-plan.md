# Plano de Testes no Robô Real — 3 Fases com Portões

> **Regra:** só avance de fase com a anterior 100% verde. Se algo quebrar numa
> fase, a causa está quase sempre na própria fase — as de baixo já foram validadas.
>
> - **Fase 1** isola problemas de **fio e configuração** (baratos na bancada, caros no chão)
> - **Fase 2** isola **dinâmica e segurança** com o operador no controle (só MANUAL)
> - **Fase 3** liga a **autonomia** quando tudo abaixo já foi provado

Docs relacionados: [`hardware-bring-up.md`](./hardware-bring-up.md) (fiação/pinos),
[`hardware-deployment.md`](./hardware-deployment.md), [`camera-calibration.md`](./camera-calibration.md).

Estado consolidado (2026-07-03):
- Mapa real: `pi/maps/corredor_6tags_80x200.json` ✅ (valida no schema)
- Calibração: `pi/calibracao/camera_intrinsics.json` ✅ — OpenCV, **640×480**,
  erro de reprojeção 0,144 px (fotos em `roboticaMengo/imagens/`)
- Captura deve rodar em **640×480** (`CAMERA_FRAME_WIDTH/HEIGHT` no `.env`)
- Pinagem firmware alinhada ao `Testes_eletronica.ino`; fim-de-curso desabilitado (-1)
- Inversões: `MOTOR_ESQ_INV=true` já compensa a roda esquerda invertida da placa
- **Encoder instável?** Há uma **Trilha sem encoder (malha aberta)** logo após a
  FASE 0 (`OPEN_LOOP=true`): valida comunicação, motores, garfo, watchdogs e
  MANUAL sem esperar o encoder; a odometria/autonomia ficam para o **Retorno ao
  encoder** na mesma seção.

---

## FASE 0 — Setup e topologia

### As duas topologias (não misturar)

**MODO DEV — enquanto estamos programando (Mac + Pi):**

```
Mac (você)                         Raspberry Pi (no robô)
├── edita o código                 ├── backend SIM=0 (./scripts/run_pi.sh)
├── serve o frontend               ├── câmera USB
│   (npm run dev, porta 5173)      └── UART ↔ ESP32
└── git push ──────► git pull no Pi + reiniciar backend
Celular/navegador → http://<IP_DO_MAC>:5173  ──WebSocket──► ws://<IP_DO_PI>:8000/ws
```

- No `.env` **do Mac**: `VITE_PI_WS_URL=ws://<IP_DO_PI>:8000/ws` (obrigatório
  neste modo — a página vem do Mac, então o fallback de mesmo-host apontaria
  para o Mac, errado).
- O dev server já expõe na rede (`host: true` no vite.config) e recarrega a
  cada edição — ideal para iterar.
- Sincronizar código com o Pi: `git push` no Mac → `git pull` no Pi → reiniciar
  o backend. (Alternativa rápida sem commit:
  `rsync -av --exclude .venv --exclude node_modules src/ pi@<IP>:~/Empilhadeira/src/`)
- Todos os passos de firmware/bancada/câmera (1.2–1.4) rodam **no Pi via SSH**
  — o ESP32 e a câmera estão plugados nele.

**MODO OPERAÇÃO — demo/desafio (só Pi, Mac desligado, SEM Node no Pi):**

```
Mac (antes):  cd src/frontend && npm run build
              rsync -av dist/ pi@<IP>:~/Empilhadeira/src/frontend/dist/
Pi (sozinho): ./scripts/run_pi.sh   ← o backend serve o frontend buildado
Celular     → http://<IP_DO_PI>:8000/   (tudo numa porta; WebSocket resolve sozinho)
```

O backend detecta `frontend/dist/` no boot e serve o app na própria porta 8000
(log: `Frontend estático montado de ...`). **Não precisa de Node/npm no Pi** —
o build é feito no Mac e só os arquivos estáticos são copiados.

Use DEV para os testes das Fases 1–3 enquanto itera; valide o modo OPERAÇÃO
inteiro pelo menos uma vez antes do dia do desafio (item 3.6).

### Setup único do Raspberry Pi

O Pi grava o firmware do ESP32 (USB), roda o backend e a câmera. Você opera
o Pi por SSH.

```bash
# 1. Código
git clone <url-do-repo> && cd Empilhadeira/src        # ou git pull

# 2. Python + dependências do backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 3. PlatformIO (para gravar o ESP32 A PARTIR do Pi)
pip install platformio
# A PRIMEIRA compilação baixa o toolchain ESP32 inteiro (centenas de MB).
# Precisa de internet e demora vários minutos no Pi — é uma vez só.

# 4. Permissões de serial e câmera
sudo usermod -aG dialout,video $USER
# DESLOGAR e logar de novo (grupo só vale em sessão nova de SSH)

# 5. Descobrir porta do ESP32 e IP do Pi (anote os dois)
ls /dev/ttyUSB* /dev/ttyACM*
hostname -I
```

**Regra de ouro da porta serial:** só UM programa pode usar a UART por vez.
`pio device monitor`, `bench_setpoint.py` e o backend brigam pela mesma porta —
**sempre feche um antes de abrir o outro** (erro típico: `Device or resource busy`).

---

## RUNBOOK PASSO A PASSO — Trilha A (sem encoder) e Trilha B (com encoder)

> Duas trilhas na mesma bancada/robô, comando a comando.
> **Trilha A (malha aberta, `OPEN_LOOP=true`)** valida tudo que NÃO precisa de
> odometria: comunicação, motores, garfo, watchdogs, câmera, teleoperação MANUAL
> e o modo OPERAÇÃO. Faça agora, enquanto o encoder está instável.
> **Trilha B (malha fechada, `OPEN_LOOP=false`)** fecha a malha PID e libera
> odometria + autonomia (FASE 3). Faça quando o encoder estiver confiável — ela
> só re-roda os gates que a Trilha A não pôde provar; o resto já está verde.
>
> **Convenção de terminal em cada passo:**
> **[MAC]** terminal no seu Mac · **[PI]** terminal SSH no Raspberry Pi ·
> **[CEL]** navegador do celular · **[MÃO]** ação física na bancada/robô.
> Cada passo traz **comando → Esperado → Testar → Se falhar**.

### Por que separar as trilhas
A malha PID do firmware faz `erro = setpoint − velocidade_medida`. Com encoder
morto, `medido ≈ 0`: o erro fica preso no setpoint, o integral (Ki=5) satura e
**as duas rodas vão a duty máximo com qualquer comando** — impossível teleoperar.
A Trilha A troca o PID por um mapa direto `duty = |w| · OPEN_LOOP_DUTY_PER_RADS`
(sem encoder) → joystick proporcional e dirigível. A Trilha B devolve o PID.

---

### PRÉ — uma vez, vale para as duas trilhas

**PRÉ.1 [PI]** Anotar porta serial do ESP32 e IP do Pi (usados o tempo todo):
```bash
ls /dev/ttyUSB* /dev/ttyACM*     # → anote (ex.: /dev/ttyUSB0)
hostname -I                      # → anote o IP do Pi (ex.: 192.168.0.10)
```
**PRÉ.2 [MAC]** Anotar o IP do Mac (só o modo DEV precisa):
```bash
ipconfig getifaddr en0           # Wi-Fi; en1/en... se for outra interface
```
**PRÉ.3 [PI]** `.env` do backend (`~/Empilhadeira/src/.env`, base no `.env.example`):
```bash
SIM=0
REQUIRE_CAMERA_CALIBRATION=1
CAMERA_FRAME_WIDTH=640
CAMERA_FRAME_HEIGHT=480
MAP=corredor_6tags_80x200
SERIAL_PORT=/dev/ttyUSB0         # a porta do PRÉ.1
```
> **Regra de ouro da serial:** só UM programa por vez na UART. `pio device
> monitor`, `bench_setpoint.py` e o backend brigam pela mesma porta — feche um
> (Ctrl-C) antes de abrir o outro (erro típico: `Device or resource busy`).

---

## TRILHA A — SEM ENCODER (malha aberta)

### A1 [PI] — Ligar a malha aberta e gravar o firmware
```bash
# Confirme em firmware/src/config.h:  constexpr bool OPEN_LOOP = true;  (default atual)
cd ~/Empilhadeira/src/firmware && source ../.venv/bin/activate
pio run                 # 1ª vez baixa o toolchain — tem que dar SUCCESS
pio run -t upload       # travou em "Connecting..."? segurar o botão BOOT do ESP32
```
- **Esperado:** `SUCCESS` na compilação e `Writing... / Hash of data verified` no upload.
- **Se falhar:** não grava = GPIO 12 puxado HIGH (strapping) → desconectar o
  driver do 12 e regravar; `pio` não achado = faltou `source ../.venv/bin/activate`.

### A2 [PI] — Ver sensores no monitor (robô suspenso, rodas no ar)
```bash
pio device monitor -b 115200
```
- **Esperado:** JSON a ~20 Hz com `az≈9.8` (MPU sente a gravidade).
- **Testar (só o que NÃO depende do encoder):** [MÃO] inclinar o chassi →
  `ax/ay/az` mudam. **Pule** os checks de sinal/PPR do encoder (`enc.*` pode ficar 0).
- **Se falhar:** lixo no monitor = baudrate errado; nada = TX/RX invertidos ou
  cabo só-carga. **Feche o monitor com Ctrl-C** antes do próximo passo.

### A3 [PI] — Motores na bancada (RODAS NO AR, fonte 12 V ligada)
```bash
cd ~/Empilhadeira/src && source .venv/bin/activate
python3 scripts/bench_setpoint.py --w-esq 2 --w-dir 2 --seconds 5
python3 scripts/bench_setpoint.py --garfo subir --seconds 2
# use --port /dev/ttyACM0 se essa for a porta do PRÉ.1
```
- **Esperado:** `[OK] ... Enviando w_esq=2 w_dir=2 ...` e linhas
  `enc esq=... dir=... rad/s | mpu az=.. gz=..`. Em malha aberta com encoder
  morto o `enc` sai 0 — **normal**; o que importa é a roda girar.
- **Testar:**
  1. [MÃO] **As duas rodas giram para FRENTE** (`MOTOR_ESQ_INV=true` já compensa a
     esquerda). Inverteu uma? Ajustar `MOTOR_*_INV` no `config.h` e regravar (A1).
  2. [MÃO] `--garfo subir` **sobe** (senão `FORK_INV=true`). **Soltar antes do fim
     do curso mecânico** (sem fim-de-curso montado).
  3. **Watchdog:** Ctrl-C com as rodas girando → param **< 200 ms**. Reprovou = pare.
- **Se falhar:** `[FALHA] Nenhum frame` = baudrate/TX-RX/CRC; não gira = fonte
  desligada ou jumper ENA/ENB ainda no L298n.
- **Pule** o check "`enc.* ≈ +2.0`" — é a malha fechando, só existe na Trilha B.

### A4 [PI] — Câmera (via SSH, headless automático)
```bash
cd ~/Empilhadeira/src/pi && python3 teste_cam.py
```
- **Esperado:** `[OK] Detector criado com calibração da câmera.` +
  `[OK] Câmera aberta (índice 0, 640x480)` + linhas `N tag(s): [ids]`.
- **Testar:** [MÃO] tag a **30,0 cm** → `z` entre 28,5–31,5 cm (fita métrica);
  tag a **15 cm** (standoff) ainda detecta; anotar distância máxima de detecção.
- **Se falhar:** `[AVISO] Câmera não calibrada` = JSON de calibração fora do
  lugar; `z` fora da faixa = resolução de captura ≠ calibração (640×480) ou
  `APRILTAG_SIZE_CM`/`tag_size_m` errado. **Ctrl-C** para sair.

### A5 [PI] — Subir o backend
```bash
cd ~/Empilhadeira/src && ./scripts/run_pi.sh
```
- **Esperado (nesta ordem):** `Modo REAL (hardware)` → `Serial loop (REAL)
  iniciado` → `Detector criado com calibração`.
- **Se faltar:** `Modo REAL` ausente = `.env` não carregou ou `SIM≠0`; `Serial
  loop` ausente = porta errada/ocupada (fechou monitor e bench?) ou grupo
  `dialout` sem relogar; `Detector` ausente = calibração quebrada (voltar A4).
- Deixe rodando neste terminal. **Deixe o robô imóvel ~3 s** agora: o
  GyroCalibrator usa a gravidade p/ achar o eixo vertical, sinal do yaw e bias.

### A6 [MAC] — Frontend, MODO DEV (itera rápido; a página vem do Mac)
```bash
# no .env DO MAC:  VITE_PI_WS_URL=ws://<IP_DO_PI>:8000/ws     (IP do PRÉ.1)
cd src/frontend && npm install       # 1ª vez só
npm run dev                          # expõe na rede (host:true), porta 5173
```
- **[CEL]** abrir `http://<IP_DO_MAC>:5173` (IP do PRÉ.2).
- **Esperado:** app carrega e conecta (indicador de conexão verde/telemetria fluindo).
- **Se falhar:** não conecta = `VITE_PI_WS_URL` errado ou não reiniciou o
  `npm run dev` após editar o `.env` (a env é lida na partida).

### A7 [CEL] — Validar telemetria e teleoperação MANUAL
- **Testar telemetria (~20 Hz):**
  - [MÃO] inclinar o robô → bloco `imu` mexe.
  - [MÃO] tag na frente da câmera → `visao.detectado = true`.
  - Campo `rodas`/`enc` fica ~0 (encoder morto) — **esperado** nesta trilha.
- **Testar MANUAL (robô no chão, área livre, [MÃO] no PARADO):**
  - Joystick à frente devagar → **anda** (proporcional ao talo). Muito rápido/lento
    → [PI] ajustar `OPEN_LOOP_DUTY_PER_RADS` no `config.h` (atual 24) e regravar (A1).
  - Ré → anda para trás; giro no lugar → gira.
  - **Só julgue SENTIDO** (frente/ré/giro). **NÃO** julgue "anda reto": sem
    correção por roda ele pode derivar — isso é da Trilha B.
- **NÃO clicar em AUTOMATICO nesta trilha** (autonomia depende de odometria).

### A8 [CEL] — Os dois watchdogs (andando de verdade)
1. [MÃO] desplugar o USB do ESP32 com o robô andando → para **< 200 ms**.
2. [MÃO] desligar o Wi-Fi do celular andando → para **< ~400 ms**
   (`COMMAND_WATCHDOG_MS`).

### A9 [MAC]/[PI] — Modo OPERAÇÃO (demo sem Node no Pi)
```bash
# [MAC] buildar e copiar os estáticos:
cd src/frontend && npm run build
rsync -av dist/ pi@<IP_DO_PI>:~/Empilhadeira/src/frontend/dist/
# [PI] reiniciar o backend (Ctrl-C no de A5 e subir de novo):
cd ~/Empilhadeira/src && ./scripts/run_pi.sh
```
- **Esperado:** log do backend mostra `Frontend estático montado de ...`.
- **[CEL]** abrir `http://<IP_DO_PI>:8000/` — uma porta só; sem `VITE_PI_WS_URL`
  o front conecta em `ws://<host da página>:8000/ws`, que já é o Pi. Repetir A7 (MANUAL).
- **Checar de outra máquina:** `curl http://<IP_DO_PI>:8000/maps/current` →
  `corredor_6tags_80x200`.

### ✅ PORTÃO A (sem encoder)
Firmware grava em malha aberta · MPU @20 Hz (`az≈9.8`) · motores no sentido certo ·
garfo com carga · watchdog bench < 200 ms · câmera com `z` na fita · backend com
os 3 logs · telemetria no celular · **MANUAL dirigível** · os dois watchdogs
andando · modo OPERAÇÃO servido pelo Pi (`Frontend estático montado`).

---

## TRILHA B — COM ENCODER (malha fechada) · fechar o robô COMPLETO

> Pré-requisito: **PORTÃO A verde** e o encoder já lendo (pull-up 10 kΩ → 3V3 nos
> GPIO 34/35 conferido no item 1.1). Aqui só re-rodamos os gates que dependem do
> encoder; comunicação, garfo, câmera e OPERAÇÃO já foram provados na Trilha A.

### B1 [PI] — Voltar para malha fechada e regravar
```bash
# firmware/src/config.h:  constexpr bool OPEN_LOOP = false;
cd ~/Empilhadeira/src/firmware && source ../.venv/bin/activate
pio run -t upload
```
- **Esperado:** `SUCCESS` + upload verificado. A partir daqui o PID fecha a malha.

### B2 [PI] — Encoder: sinal e PPR (monitor, rodas no ar)
```bash
pio device monitor -b 115200
```
- **Testar:**
  1. [MÃO] girar cada roda **para frente** → `enc.esq`/`enc.dir` **positivos**.
     Negativo → `ENC_*_INV=true` no `config.h`, regravar (B1). Direito sempre
     zero → pull-up do 1.1.
  2. [MÃO] **1 volta exata** → ~360 pulsos. Diferente → ajustar `ENCODER_PPR`
     (firmware) **e** `EMU_ENCODER_PPR` (pi/app/config.py). **Ctrl-C** ao fim.

### B3 [PI] — Malha fechando: comando → motor → encoder
```bash
cd ~/Empilhadeira/src && source .venv/bin/activate
python3 scripts/bench_setpoint.py --w-esq 2 --w-dir 2 --seconds 5
```
- **Esperado:** agora `enc esq/dir` impresso **≈ +2.0 rad/s** (o PID persegue o
  setpoint). Ficou longe/oscilando → sintonia PID (item 3.1, Ziegler-Nichols).
- **Testar:** Ctrl-C com rodas girando → param **< 200 ms** (watchdog, agora com PID ativo).

### B4 [PI]/[MAC]/[CEL] — Subir o stack e revalidar MANUAL com malha fechada
- [PI] `./scripts/run_pi.sh` (mesmos 3 logs da A5) · [MAC] `npm run dev` ·
  [CEL] abrir e ficar em MANUAL.
- **Testar retidão (o que a Trilha A não podia):**
  - Frente devagar → **anda reto**. Curva suave = PPR/raio desigual (anotar p/ 3.1);
    vira no lugar = inversão de um lado (voltar a A3/B2).
  - Ré → reto para trás. Giro no lugar → gira **sem transladar**.
  - Parado → heading da telemetria **estável** (senão o gyro não calibrou; deixar
    imóvel ~3 s no boot).

### B5 [CEL] — Odometria e visão dirigindo MANUAL
1. [MÃO] 1 m reto medido com fita → a pose no painel avança ~1 m (erro grande =
   `WHEEL_RADIUS_R_CM`/`ENCODER_PPR`).
2. [MÃO] 360° no lugar → heading volta ~ao mesmo valor (erro = `WHEEL_BASE_L_CM` ou gyro).
3. [MÃO] aproximar de tag → `z_cm` cai suave e bate com a fita em 60/30/15 cm.

### B6 — Fechar os números e liberar a autonomia
- Gravar em `config.py`/`config.h` os valores medidos: `WHEEL_BASE_L_CM`,
  `WHEEL_RADIUS_R_CM`, `CAMERA_TO_FORK_OFFSET_CM`, `APRILTAG_SIZE_CM`
  (= `tag_size_m` do mapa); sintonizar PID se B4 oscilou (item 3.1).
- **Só então** seguir para a **FASE 3** (autonomia/EKF/missão) — todos os itens
  dela dependem da odometria provada em B5.

### ✅ PORTÃO B (com encoder)
Encoders positivos p/ frente e ~360 ppr · `enc ≈ +2.0` fechando a malha ·
watchdog < 200 ms com PID · **anda reto** · odometria ~1 m e heading ~360° ·
visão confere com a fita → **libera a FASE 3**.

---

## FASE 1 — Check completo: tudo conectado e conversando (robô suspenso, nada anda)

### 1.1 Fiação (fonte DESLIGADA)

Pinos: ESQ 12/14/13 · DIR 27/26/25 · Garfo 18/19/5 · ENC-E 32/33 · ENC-D 34/35 · I2C 21/22.

- [ ] **Pull-up 10 kΩ → 3V3 nos GPIO 34 e 35** (sem isso o encoder direito lê zero eternamente)
- [ ] **Nenhum pull-up no GPIO 12** (strapping — ESP32 não sobe/não grava se HIGH no boot)
- [ ] Jumpers ENA/ENB removidos dos dois L298n
- [ ] GND comum em estrela (fonte, 2× L298n, ESP32, Pi, MPU)
- [ ] Multímetro na saída dos encoders NXT: > 3,3 V → level shifter/divisor
- [ ] Fim-de-curso: **nada ligado** (desabilitado com -1 — esperado)

### 1.2 Firmware: compilar, gravar, ver sensores (no Pi, ESP32 no USB do Pi)

```bash
cd ~/Empilhadeira/src/firmware
source ../.venv/bin/activate          # pio foi instalado no venv (Fase 0)
pio run                               # 1ª vez demora (baixa toolchain) — tem que dar SUCCESS
pio run -t upload                     # se travar em "Connecting...", segurar o botão BOOT
pio device monitor -b 115200
```

**Esperado:** JSON @ ~20 Hz com `az≈9.8` no MPU.

Checks de sensor (na mão, sem motor):
1. Girar cada roda **para frente** → `enc.esq`/`enc.dir` **positivos**.
   Negativo → `ENC_*_INV=true` em `config.h`, regravar.
   Direito sempre zero → pull-up do 1.1.
2. 1 volta exata → ~360 pulsos (senão ajustar `ENCODER_PPR` nos dois configs).
3. Inclinar o chassi → `ax/ay/az` mudam.

Erros: lixo no monitor = baudrate; nada = TX/RX invertidos ou cabo só-carga;
não grava = GPIO 12 puxado HIGH (desconectar driver e regravar).

**Feche o `pio device monitor` (Ctrl-C) antes do próximo passo** — a porta é uma só.

### 1.3 Motores em bancada (RODAS NO AR — fonte 12 V ligada)

```bash
cd ~/Empilhadeira/src && source .venv/bin/activate
python3 scripts/bench_setpoint.py                               # 2 rad/s frente, 5 s
python3 scripts/bench_setpoint.py --garfo subir --seconds 2     # garfo
```

(`--port /dev/ttyACM0` se for a porta anotada na Fase 0.)

1. **As duas rodas giram para FRENTE** (ESQ já compensada com `MOTOR_ESQ_INV=true`;
   se alguma inverter, ajustar o flag e regravar).
2. `enc.*` impresso ≈ +2.0 rad/s (fecha o ciclo comando→motor→encoder).
3. `--garfo subir` sobe (senão `FORK_INV=true`). **Soltar antes do fim do curso mecânico.**
4. **Watchdog:** Ctrl-C com rodas girando → param **< 200 ms**. Reprovou = não avance.

### 1.4 Câmera no Pi (via SSH)

```bash
cd ~/Empilhadeira/src/pi && python3 teste_cam.py
```

Via SSH ele detecta que não há display e entra em modo headless sozinho
(só imprime no terminal; `HEADLESS=1` força, se precisar).

**Esperado:** `[OK] Detector criado com calibração` + `Câmera aberta (índice 0, 640x480)`
+ detecções com id/z.

Validações com fita métrica:
1. Tag a 30,0 cm → z entre 28,5–31,5 cm. Fora disso → resolução de captura ≠
   calibração, ou `tag_size` errado. (Plano B: reverter para a calibração
   alternativa anotada em `_alternativa_zephyr` no JSON e repetir.)
2. Tag a 15 cm (standoff da navegação) → ainda detecta.
3. Anotar a distância máxima de detecção (< ~1,5 m compromete tags distantes).
4. Medir a tag impressa com paquímetro — mapa declara `tag_size_m: 0.05`;
   se diferente, corrigir no mapa E em `APRILTAG_SIZE_CM`.

### 1.5 Backend no Pi + frontend (conforme a topologia da Fase 0)

`.env` **no Pi** (base no `.env.example`):

```bash
SIM=0
REQUIRE_CAMERA_CALIBRATION=1
CAMERA_FRAME_WIDTH=640
CAMERA_FRAME_HEIGHT=480
MAP=corredor_6tags_80x200
SERIAL_PORT=/dev/ttyUSB0        # a porta anotada na Fase 0
```

**No Pi (SSH) — backend:**
```bash
cd ~/Empilhadeira/src && ./scripts/run_pi.sh
```

| Log esperado (ordem) | Se não aparecer |
|---|---|
| `Modo REAL (hardware)` | `.env` não carregou ou SIM≠0 |
| `Serial loop (REAL) iniciado` | porta errada/ocupada (fechou o monitor? bench?), ou grupo dialout sem relogar |
| `Detector criado com calibração` | JSON de calibração quebrado → refazer 1.4 |

**Frontend — MODO DEV (Mac, o nosso caso agora):**
```bash
# no .env DO MAC:  VITE_PI_WS_URL=ws://<IP_DO_PI>:8000/ws
cd src/frontend && npm run dev        # já expõe na rede (host: true), porta 5173
```
Abrir no navegador do Mac ou do celular: `http://<IP_DO_MAC>:5173`.
Mudou o `VITE_PI_WS_URL`? Reiniciar o `npm run dev` (a env é lida na partida).

**Frontend — MODO OPERAÇÃO (servido pelo backend do Pi, sem Node no Pi):**
```bash
# No Mac: buildar e copiar os estáticos
cd src/frontend && npm run build
rsync -av dist/ pi@<IP_DO_PI>:~/Empilhadeira/src/frontend/dist/
# No Pi: reiniciar o backend — log deve mostrar "Frontend estático montado"
```
Celular abre `http://<IP_DO_PI>:8000/` — uma porta só; sem `VITE_PI_WS_URL`
o frontend conecta em `ws://<host da página>:8000/ws`, que já é o Pi.

**Validação (igual nos dois modos):** telemetria ~20 Hz na tela; girar roda na
mão move `rodas`; inclinar move `imu`; tag na frente da câmera →
`visao.detectado=true`.
Não conecta → mesma rede Wi-Fi?, IPs certos (`hostname -I` no Pi, `ipconfig
getifaddr en0` no Mac), porta 8000 acessível (`curl http://<IP_DO_PI>:8000/maps/current`
de outra máquina).

### ✅ PORTÃO 1
Frames 20 Hz · encoders positivos p/ frente · motores no sentido certo ·
watchdog < 200 ms · câmera com z correto na fita · telemetria no celular.

---

## FASE 2 — Só MODO MANUAL (robô no chão, área livre, mão no PARADO)

**Não clicar em AUTOMATICO nesta fase.**

### 2.0 Ritual de boot (gyro)
Subir o backend e **deixar o robô imóvel ~3 s**. O GyroCalibrator usa a gravidade
para detectar o eixo vertical, o sinal do yaw e o bias (a posição do MPU no chassi
não importa, desde que um eixo fique vertical; > 10° de inclinação gera aviso no log).
Robô mexendo no boot = calibração adiada até a primeira parada.

### 2.1 Joystick

| Teste | Esperado | Se falhar |
|---|---|---|
| Frente devagar | Anda **reto** | Vira no lugar = inversão de um lado (voltar ao 1.3); curva suave = PPR/raio desigual — anotar p/ Fase 3 |
| Ré | Reto para trás | idem |
| Giro no lugar | Gira sem transladar | cinemática/wheelbase — anotar |
| Parado | Heading da telemetria **estável** | gyro não calibrou (2.0) |

### 2.2 Garfo com carga
Vazio, depois com o pallet real. Não sobe = `FORK_DUTY` 180→220 e regravar.
**Sempre soltar antes do limite mecânico** (sem fim-de-curso!). Worm gear segura parado.

### 2.3 Os dois watchdogs (andando de verdade)
1. Desplugar USB do ESP32 andando → para **< 200 ms**.
2. Desligar Wi-Fi do celular andando → para **< ~400 ms** (`COMMAND_WATCHDOG_MS`).

### 2.4 Sanidade de odometria e visão (dirigindo manual)
1. 1 m reto medido com fita → pose avança ~1 m (erro grande = `WHEEL_RADIUS`/PPR).
2. 360° no lugar → heading volta ~ao mesmo valor (erro grande = `WHEEL_BASE` ou gyro).
3. Aproximar de tag → `z_cm` cai suave e bate com a fita em 60/30/15 cm.

### ✅ PORTÃO 2
Anda reto · watchdogs ok · garfo com carga ok · odometria/heading plausíveis ·
visão confere com fita.

---

## FASE 3 — Autonomia e preparação para o desafio

### 3.1 Fechar os números (pré-requisito)
1. Medir e gravar em `config.py`: `WHEEL_BASE_L_CM`, `WHEEL_RADIUS_R_CM`,
   `CAMERA_TO_FORK_OFFSET_CM`, `APRILTAG_SIZE_CM` (= `tag_size_m` do mapa).
2. PID se necessário (se 2.1 oscilou/mole): Ziegler-Nichols em `config.h` —
   Ki=Kd=0; subir Kp até oscilar (Ku); medir período Tu; Kp=0.6·Ku, Ki=2·Kp/Tu,
   Kd=Kp·Tu/8; regravar.

### 3.2 Primeira autonomia: aproximação reativa (1 tag, arena aberta)
Robô a ~60 cm da tag, alinhado, fora do corredor. 1 clique em AUTOMATICO:
- `nav_phase` percorre APPROACH→FACE→RETREAT; para a **15 ± 2 cm** (fita).
- Sistematicamente longe/perto = escala da calibração (1.4) ou `TAG_STANDOFF_M`.
- Oscila/serpenteia = reduzir `NAV_K_HEADING`; lento demais = subir `NAV_K_DIST`.
Repetir com offset lateral 10–20 cm e heading ±15° (cenários que o sim passou 9/9).

### 3.3 Segurança em autonomia (obrigatório antes do corredor)
1. **Cobrir a tag** durante AUTOMATICO → `PARADO` latched + `parado_reason`;
   só novo comando reativa.
2. Desplugar serial durante AUTOMATICO → para < 200 ms.
3. Matar Wi-Fi durante AUTOMATICO → control loop continua a manobra sozinho
   com segurança (1 clique basta).

### 3.4 EKF no corredor real
Dirigir MANUAL pelo corredor 80×200 olhando a pose no painel:
- Pose "teleporta" ao ver tag = subir `EKF_Q_*` (odometria superestimada).
- Pose ignora tags = descer `EKF_R_*`.
- Entre tags a pose deriva pouco e corrige suave a cada tag nova.

### 3.5 Missão completa (ensaio do desafio)

```bash
curl -X POST http://<IP_DO_PI>:8000/maps/load/corredor_6tags_80x200
curl -X POST http://<IP_DO_PI>:8000/mission/start
```

Navega ao pick → para → operador usa o garfo → "continuar" → place → garfo →
"continuar" → home → `DONE`. **Mínimo 3× seguidas sem intervenção** (além do garfo).
Falhou → identificar a fase (`nav_phase`/estado missão) e voltar ao item
correspondente (3.2 navegação, 3.4 localização).

### 3.6 Checklist do dia do desafio
- [ ] Bateria cheia; tensão sob carga ok (Pi reiniciando ao acelerar = fonte/buck)
- [ ] Wi-Fi do local testado; IP do Pi fixo (anotar!); celular abre `http://<IP>:8000/`
- [ ] `frontend/dist/` atualizado no Pi (build do Mac + rsync) — log do backend
      mostra `Frontend estático montado`
- [ ] Backend (`run_pi.sh`) sobe por SSH — ou configurar systemd/tmux para
      subir sozinho no boot do Pi
- [ ] `GET /maps/current` = `corredor_6tags_80x200`
- [ ] Tags fixadas nas posições do mapa (L* a x=0,05 m; R* a x=0,75 m;
      y = 0,40/1,00/1,60 m) — **remedir com fita no local**
- [ ] Iluminação testada com `teste_cam` (reflexo na tag = reposicionar/foscar)
- [ ] 1 volta manual + 1 missão completa de aquecimento antes da valendo
- [ ] Plano B ensaiado: missão inteira em MANUAL se a autonomia falhar
