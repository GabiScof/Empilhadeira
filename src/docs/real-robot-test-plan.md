# Plano de Testes no Robô Real — 3 Fases com Portões

> **Regra:** só avance de fase com a anterior 100% verde. Se algo quebrar numa
> fase, a causa está quase sempre na própria fase — as de baixo já foram validadas.
>
> - **Fase 1** isola problemas de **fio e configuração** (baratos na bancada, caros no chão)
> - **Fase 2** isola **dinâmica e segurança** com o operador no controle (só MANUAL)
> - **Fase 3** liga a **autonomia** quando tudo abaixo já foi provado

Docs relacionados: [`hardware-bring-up.md`](./hardware-bring-up.md) (fiação/pinos),
[`hardware-deployment.md`](./hardware-deployment.md), [`camera-calibration.md`](./camera-calibration.md).

Estado consolidado (atualizado 2026-07-06):
- Mapa real: `pi/maps/corredor_6tags_80x200.json` ✅ (valida no schema)
- **2026-07-06: dock-to-tag (opt-in) + vista de cima no robô real** — novo modo
  que estaciona em frente a UMA tag por segmentos (testado no 3.4b) e endpoint
  `GET /world-state` que faz a tela `/demo` desenhar o Arena no hardware
  (pose do EKF + mapa). Desligado por padrão; ver `docs/dock-to-tag.md`.
- Calibração: `pi/calibracao/camera_intrinsics.json` ✅ — OpenCV, **640×480**,
  erro de reprojeção 0,144 px (fotos em `roboticaMengo/imagens/`)
- Captura deve rodar em **640×480** (`CAMERA_FRAME_WIDTH/HEIGHT` no `.env`)
- Pinagem firmware conferida na bancada; fim-de-curso desabilitado (-1)
- **2026-07-06: canais dos MOTORES estavam trocados na fiação** (canal A
  12/14/13 aciona a roda DIREITA; canal B 27/26/25 a ESQUERDA — o inverso do
  rótulo M2/M3 do `Testes_eletronica.ino`). Remapeado por software no
  `config.h`: `PIN_MOTOR_ESQ_*`=27/26/25 (`MOTOR_ESQ_INV=false`),
  `PIN_MOTOR_DIR_*`=12/14/13 (`MOTOR_DIR_INV=true`). Sintoma que isso causava:
  com as malhas PID cruzadas (cada PID lia uma roda e acionava a outra), uma
  roda saturava no máximo e a outra morria, alternando aleatoriamente o lado
  entre testes. **Lição: sempre testar um lado por vez** (`--w-esq X --w-dir 0`)
  — o teste com as duas rodas juntas NÃO detecta canais trocados.
- **2026-07-06: dois bugs de SINAL corrigidos no Pi** — (a) modo manual:
  `joystick_to_twist` gerava ω invertido (joystick à direita virava à
  esquerda); (b) visão real: o x do frame óptico OpenCV (positivo = direita) é
  o OPOSTO da convenção do projeto (positivo = esquerda, a do simulador/nav) —
  negado na fronteira em `pose.py`. Sem o fix (b), a autonomia viraria PARA
  LONGE da tag. Validar (b) no 1.4 com a tag deslocada.
- **2026-07-06: encoders FUNCIONANDO** (alimentação via GPIO 2 = VCC / GPIO 4 =
  GND, dirigidos pelo `encodersBegin()`; lados esq↔dir corrigidos no `config.h`:
  ESQ=23/15, DIR=32/33 — o esquerdo foi refiado no mesmo dia de 34/35 para
  23/15, pois 34/35 são input-only sem pull-up interno e sobrecontavam ~420
  pulsos/volta por ruído). Decodificação agora é a COMPLETA x4 (CHANGE nas
  duas fases, tabela de transição em `encoders.cpp`) → `ENCODER_PPR=1440`;
  sinais validados na bancada (`ENC_ESQ_INV=true`, `ENC_DIR_INV=true`).
  O firmware é **sempre malha fechada** (PID ativo; a antiga flag `OPEN_LOOP`
  não existe mais no código).

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

# 6. Criar o .env do backend (uma vez; precisa existir ANTES da câmera, item 1.4)
cp .env.example .env
# edite o .env:  SIM=0 · REQUIRE_CAMERA_CALIBRATION=1
#   CAMERA_FRAME_WIDTH=640 · CAMERA_FRAME_HEIGHT=480  (TEM que bater com a calibração)
#   MAP=corredor_6tags_80x200 · SERIAL_PORT=<a porta do passo 5>
```

**Regra de ouro da porta serial:** só UM programa pode usar a UART por vez.
`pio device monitor`, `bench_setpoint.py` e o backend brigam pela mesma porta —
**sempre feche um antes de abrir o outro** (erro típico: `Device or resource busy`).

---

## FASE 1 — Check completo: tudo conectado e conversando (robô suspenso, nada anda)

### 1.1 Fiação (fonte DESLIGADA)

Pinos (config.h, conferidos 2026-07-06): ESQ 27/26/25 (canal B) · DIR 12/14/13 (canal A) · Garfo 18/19/5 · ENC-E 23/15 (refiado, era 34/35) · ENC-D 32/33 · I2C 21/22.

- [ ] **Sem pull-up externo nos encoders** — 23/15 e 32/33 têm pull-up interno (`INPUT_PULLUP`); 34/35 ficaram livres (se reutilizados, aí sim exigem 10 kΩ → 3V3)
- [ ] **Nenhum pull-up no GPIO 12** (strapping — ESP32 não sobe/não grava se HIGH no boot)
- [ ] Jumpers ENA/ENB removidos dos dois L298n
- [ ] GND comum em estrela (fonte, 2× L298n, ESP32, Pi, MPU)
- [ ] Multímetro na saída dos encoders NXT: > 3,3 V → level shifter/divisor
- [ ] Fim-de-curso: **nada ligado** (desabilitado com -1 — esperado)
- [ ] **Recomendado (quando der):** migrar a alimentação dos encoders dos GPIOs
      2/4 para os pinos 3V3/GND reais da placa e setar `PIN_ENC_POWER_VCC/GND
      = -1` no config.h — GPIO fornece pouca corrente E o GPIO 2 é strapping de
      boot (atrapalha a gravação; ver troubleshooting do 1.2)

### 1.2 Firmware: compilar, gravar, ver sensores (no Pi, ESP32 no USB do Pi)

```bash
cd ~/Empilhadeira/src/firmware
source ../.venv/bin/activate          # pio foi instalado no venv (Fase 0)
pio run                              # 1ª vez demora (baixa toolchain) — tem que dar SUCCESS
pio run -t upload                     # se travar em "Connecting...", segurar o botão BOOT
pio device monitor -b 115200
```

**Esperado:** JSON @ ~20 Hz com `|az|≈9.8–11` no MPU (no nosso chassi o z
aponta para baixo → `az` NEGATIVO ~-11, normal).

Checks de sensor (na mão, sem motor):
1. Girar cada roda **para frente** → `enc.esq`/`enc.dir` **positivos**.
   Negativo → inverter o `ENC_*_INV` em `config.h`, regravar (validado
   2026-07-06: `ENC_ESQ_INV=true`, `ENC_DIR_INV=true`).
   Esquerdo sempre zero → fiação do 1.1.
2. 1 volta exata → ~1440 contagens (x4; senão ajustar `ENCODER_PPR` nos dois configs).
3. **Isolamento entre encoders:** girar SÓ uma roda → o `enc` da outra fica
   **cravado em 0** (contar junto = cross-talk/fio trocado entre encoders).
4. **Simetria esq/dir:** empurrar o robô ~1 m em linha reta no chão → as duas
   colunas positivas e parecidas (±5%). Diferença sistemática = raio/PPR
   desigual → vai aparecer como curva suave no 2.1; anotar para o 3.1.
5. **Cadeia de yaw (encoders × gyro):** girar o robô no lugar, à mão,
   ANTI-horário (visto de cima) → `enc.esq` negativo, `enc.dir` positivo, e
   `gz` com sinal consistente durante o giro — **anotar o sinal do gz** (com o
   MPU de z para baixo, espere gz NEGATIVO no anti-horário). Valida a coerência
   encoder↔gyro antes do EKF, sem backend.
6. Inclinar o chassi → `ax/ay/az` mudam; deitar de lado → |g|≈10–11 migra de
   eixo (cada eixo vivo).

Erros: lixo no monitor = baudrate; nada = TX/RX invertidos ou cabo só-carga.
**Gravação falhando** (visto 2026-07-06: `Serial data stream stopped` /
`chip stopped responding`), na ordem: (a) repetir segurando o botão BOOT no
"Connecting..."; (b) **desconectar o fio do GPIO 2** (VCC dos encoders —
strapping de boot) e regravar; (c) desligar a fonte 12 V/L298n durante a
gravação (GPIO 12 no IN do driver + ruído na USB); (d) `upload_speed = 115200`
no platformio.ini; (e) trocar o cabo USB / plugar direto no Pi.

**Feche o `pio device monitor` (Ctrl-C) antes do próximo passo** — a porta é uma só.

#### Resultados — modo display (robô ~fixo, sem motor), 2026-07-06

Caracterização do stream cru (`enc`/`mpu`) em 4 poses. **Todas as convenções
de sinal do firmware/Pi foram CONFIRMADAS** — nenhum ajuste de sinal foi
necessário; valida os fixes de giro de `a4bffcf`.

- **Repouso, chassi nivelado (Z p/ baixo):** `az ≈ -10.7` domina (faixa
  -9.5…-12.2 com ruído/vibração), `ax`/`ay ≈ 0`. `|g| ≈ 10.7` — ~9% acima de
  9.81. Como roll/pitch e a auto-orientação usam RAZÕES de eixos (`atan2`), essa
  escala alta é **cosmética**, não afeta heading nem tilt; fica anotada mas não
  recalibrada (uma pose limpa só não fecha calibração de 6 pontos).
- **Bias de taxa-zero do giroscópio (parado):** `gz ≈ 0` (±0.5 °/s) → bias de
  **yaw desprezível**, o `GyroCalibrator` o absorve. `gx ≈ -2.7`, `gy ≈ -1.0`
  °/s têm bias fixo, mas só entram no Kalman de roll/pitch (corrigido pelo
  acelerômetro, sem drift acumulado). Ver nota de melhoria abaixo.
- **Giro no lugar HORÁRIO (visto de cima):** `enc.esq` **+**, `enc.dir` **−**,
  `gz` **POSITIVO** (~+45…+64 °/s no pico).
- **Giro no lugar ANTI-HORÁRIO:** `enc.esq` **−**, `enc.dir` **+**, `gz`
  **NEGATIVO** (~-50…-65 °/s). Bate com §1.2.5 (“gz NEGATIVO no anti-horário”)
  e com a convenção do EKF: `up = -Z` ⇒ `yaw = -gz`, logo anti-horário ⇒ `yaw`
  positivo = θ crescente. ✅
- **Deitado de lado p/ a DIREITA:** a gravidade migra p/ o eixo **−Y**
  (`ay ≈ -9` domina). Cada eixo “vivo” conforme §1.2.6. ✅
- **Tombo p/ TRÁS:** a gravidade migra p/ o eixo **+X** (`ax ≈ +9…+10.7`
  domina, `az → ~-2`). ✅

**Falhas do MPU observadas durante o teste** (duas assinaturas DISTINTAS no
stream — úteis p/ diagnóstico futuro):
- `mpu` tudo-zero com **`temp_c` = 36.53** (bursts durante os giros): o sensor
  DORMIU (I2C respondeu 14 bytes zerados; `temp = 0/340 + 36.53`). `readMpu`
  retorna false e o firmware **auto-recupera** re-enviando `mpuWake()` após ~1 s
  (20 leituras mortas @20 Hz).
- `mpu` tudo-zero com **`temp_c` = 0** + `[E][Wire.cpp:499] requestFrom():
  i2cWriteReadNonStop returned Error 263` (no fim, após o tombo): o BARRAMENTO
  I2C caiu (0 bytes; struct `Sensors` fica no default, `temp_c=0`). Recupera
  igual, mas é sintoma de contato/EMI — reassentar o MPU e afastar do L298n.
  Se persistir, considerar `Wire.setTimeout()`/reinício do barramento.

**Melhoria pendente (não-bloqueante):** o Kalman (`pi/app/control/kalman.py`)
alimenta `u = [gx, gy]` CRUS; com bias ~-2.7/-1.0 °/s o acelerômetro corrige em
regime, mas seria mais limpo remover o bias por-eixo (o `GyroCalibrator` já mede
`g_mean` parado — expor `gx/gy` bias). Requer teste próprio; deixado como TODO.

### 1.3 Motores em bancada (RODAS NO AR — fonte 12 V ligada)

```bash
cd ~/Empilhadeira/src && source .venv/bin/activate
python3 scripts/bench_setpoint.py                               # 2 rad/s frente, 5 s
python3 scripts/bench_setpoint.py --garfo subir --seconds 2     # garfo
```

(`--port /dev/ttyACM0` se for a porta anotada na Fase 0.)

1. **UM LADO POR VEZ primeiro** (lição de 2026-07-06 — o teste conjunto não
   detecta canais trocados): `--w-esq 2 --w-dir 0` → SÓ a roda **esquerda**
   gira, para **frente**; depois `--w-esq 0 --w-dir 2` → só a **direita**.
   Roda do lado errado girar = canais do L298n trocados → remapear
   `PIN_MOTOR_*` no `config.h` (já mapeado; regressão só se refizerem fios).
   Girar para trás = ajustar o `MOTOR_*_INV` daquele canal.
2. Juntas: as duas para FRENTE e `enc.*` impresso ≈ +2.0 rad/s, subindo em
   degraus de ~0.44 (resolução x4 a 100 Hz) — fecha o ciclo
   comando→motor→encoder. **Sintoma de canais cruzados:** uma roda satura e a
   outra morre, alternando o lado entre execuções → voltar ao item 1.
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
4. Tamanho da tag = **4 cm** (0,04 m), agora consistente nos três lugares:
   `config.APRILTAG_SIZE_CM = 4.0`, `tag_size_m: 0.04` nos mapas e o default de
   `vision/detector.py`. Conferir com paquímetro: se a tag impressa NÃO for
   4 cm, o `z` sai proporcionalmente errado — reimprimir a 4 cm, ou atualizar os
   TRÊS ao valor real antes do 3.2.
5. **Sinal do x_cm** (convenção do projeto = a do simulador): tag deslocada à
   **ESQUERDA** do centro da imagem → `x_cm` **POSITIVO** (o `pose.py` nega o
   x do frame OpenCV desde 2026-07-06; se vier negativo, a negação se perdeu —
   sem ela a autonomia vira PARA LONGE da tag).
6. **Sinal do pitch_deg**: girar a tag no eixo vertical (borda esquerda para
   perto da câmera, depois a direita) → o `pitch_deg` deve trocar de sinal de
   forma consistente. Anotar a convenção observada e conferir contra o FACE no
   3.2 — a extração de Euler da câmera real ainda não foi validada contra o
   simulador.

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
Frames 20 Hz · encoders positivos p/ frente (~1440/volta) · motores no LADO e
sentido certos (um por vez) · watchdog < 200 ms · câmera com z correto na fita
e sinais de x_cm/pitch validados · telemetria no celular.

---

## FASE 2 — Só MODO MANUAL (robô no chão, área livre, mão no PARADO)

**Não clicar em AUTOMATICO nesta fase.**

### 2.0 Ritual de boot (gyro)
Subir o backend e **deixar o robô imóvel ~3 s**. O GyroCalibrator usa a gravidade
para detectar o eixo vertical, o sinal do yaw e o bias (a posição do MPU no chassi
não importa, desde que um eixo fique vertical; > 10° de inclinação gera aviso no log).
Robô mexendo no boot = calibração adiada até a primeira parada.
**Chão firme e ninguém tocando no robô nesses 3 s** — os pneus macios deixam o
chassi balançando (visto no monitor em 2026-07-06: accel/gyro ondulando ~1 Hz
com o robô "parado"); calibrar balançando = bias ruim = heading derivando.

### 2.1 Joystick

| Teste | Esperado | Se falhar |
|---|---|---|
| Frente devagar | Anda **reto** | Vira no lugar = inversão de um lado (voltar ao 1.3); curva suave = PPR/raio desigual — anotar p/ Fase 3 |
| Ré | Reto para trás | idem |
| Joystick à **direita** | Gira à **DIREITA** (e à esquerda p/ esquerda) | Invertido = regressão do sinal do ω em `joystick_to_twist` (corrigido 2026-07-06: ω = -x; convenção ω positivo = anti-horário) |
| Giro no lugar | Gira sem transladar | cinemática/wheelbase — anotar |
| Giro anti-horário | Heading da telemetria **aumenta** (θ anti-horário positivo) | sinal do gyro/odometria — conferir GyroCalibrator e convenção antes do EKF (3.4) |
| Parado | Heading da telemetria **estável** | gyro não calibrou (2.0) |
| Talo baixo (~20%) | Pode demorar ~1–2 s para partir ou nem partir | **Esperado, não é bug**: duty baixo não vence o atrito estático; o integral do PID acumula devagar. Anotar o menor talo que anda → informa a sintonia do 3.1 (subir Ki ajuda a partida) |

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
Como medir cada um (todos vão em `config.py`; os `_M`/SI derivam sozinhos):
1. `WHEEL_RADIUS_R_CM` — **teste de rolagem**, não paquímetro: marca no pneu,
   empurrar reto até EXATAS 5 voltas da roda, medir a distância →
   `r = dist / (5·2π)`. Com o peso do robô (pneu esmaga). Medir as DUAS rodas;
   >2% de diferença explica curva suave — usar a média.
2. `WHEEL_BASE_L_CM` — vão INTERNO entre pneus + UMA largura de pneu (= centro
   a centro). Refinar com o 2.4: girou 360° físicos e o heading reportou X° →
   `L_real = L_config · X/360`.
3. `APRILTAG_SIZE_CM` — paquímetro no quadrado PRETO da tag impressa (sem a
   borda branca); igual nos três lugares (config, mapa, detector — hoje 4 cm).
4. `CAMERA_TO_FORK_OFFSET_CM` — calibrar pelo resultado: tag exatamente
   centrada a 15,0 cm da ponta do GARFO → offset é o que falta para
   `z_cm=15.0` e `x_cm=0.0`; conferir sinal movendo a tag 5 cm à esquerda
   (`x_cm ≈ +5`).
5. `MAX_LINEAR_SPEED` / `MAX_ANGULAR_SPEED` — talo cheio: cronometrar 2 m
   retos (`v = 200/t`) e 1 volta no lugar (`ω = 2π/t`); gravar ~80% do medido
   (folga para o PID). Sanidade: teto físico ≈ 12.25·r ≈ 34 cm/s.
6. PID se necessário (se 2.1 oscilou/mole): Ziegler-Nichols em `config.h` —
   Ki=Kd=0; subir Kp até oscilar (Ku); medir período Tu; Kp=0.6·Ku, Ki=2·Kp/Tu,
   Kd=Kp·Tu/8; regravar. Lembrete: os ganhos foram acertados na BANCADA (roda
   no ar); no chão a carga muda a dinâmica — overshoot de ~10% já visto a
   8 rad/s deve piorar com carga.

### 3.2 Primeira autonomia: aproximação reativa (1 tag, arena aberta)
Robô a ~60 cm da tag, alinhado, fora do corredor. 1 clique em AUTOMATICO:
- `nav_phase` percorre APPROACH→FACE→RETREAT; para a **15 ± 2 cm** (fita).
- **Vira PARA LONGE da tag** = sinal do `x_cm` (check 5 do 1.4 — negação do x
  do OpenCV em `pose.py`) ou do `pitch_deg` (check 6). Interromper e conferir
  os sinais antes de mexer em ganho.
- Sistematicamente longe/perto = escala da calibração (1.4) ou `TAG_STANDOFF_M`.
- Oscila/serpenteia = reduzir `NAV_K_HEADING`; lento demais = subir `NAV_K_DIST`.
Repetir com offset lateral 10–20 cm e heading ±15° (cenários que o sim passou 9/9).

### 3.3 Segurança em autonomia (obrigatório antes do corredor)
1. **Cobrir a tag** durante AUTOMATICO → `PARADO` latched + `parado_reason`;
   só novo comando reativa. **Exceção por design:** com missão ativa OU dock
   em DOCKING (3.4b) o tag-loss NÃO trava — a tag sai do FOV em curvas
   normais e a execução segue por odometria/EKF. Nesses modos a parada de
   emergência é: modo PARADO na UI, ou os watchdogs abaixo.
2. Desplugar serial durante AUTOMATICO → para < 200 ms.
3. Matar Wi-Fi durante AUTOMATICO → control loop continua a manobra sozinho
   com segurança (1 clique basta).

### 3.4 EKF no corredor real
Dirigir MANUAL pelo corredor 80×200 olhando a pose no painel:
- Pose "teleporta" ao ver tag = subir `EKF_Q_*` (odometria superestimada).
- Pose ignora tags = descer `EKF_R_*`.
- Entre tags a pose deriva pouco e corrige suave a cada tag nova.

### 3.4b Dock-to-tag — ensaio da maquinaria da missão com UMA tag
> É o degrau entre a aproximação reativa (3.2) e a missão (3.5): usa o MESMO
> `SegmentExecutor` + EKF da missão, mas disparado por uma tag avulsa, sem
> pick/place. Se o dock funciona, a parte de navegação da missão funciona.
> [ref: docs/dock-to-tag.md]

Pré-requisitos: Portão 2 (odometria provada) e 3.4 razoável (o dock executa
pela pose do EKF). Robô a ~50–80 cm de UMA tag, arena aberta, mapa carregado
(para a vista de cima em `/demo`).

1. [CEL] Painel "Aproximar de uma tag" → **Ligar** (ou `POST /dock/enable`) →
   selecionar AUTOMATICO → mostrar a tag.
   - **Esperado:** estado Procurando → Aproximando (rota de segmentos aparece
     na vista de cima) → Estacionado a `DOCK_STANDOFF_M` (~15 cm, fita) DE
     FRENTE para a tag.
2. Repetir com a tag deslocada lateralmente e o robô torto (±30°) — o
   planejamento é feito UMA vez ao ver a tag; perder a tag na curva de 90° é
   normal e não pode travar (execução por odometria).
3. **Use o modo default `line_of_sight`** — não depende da convenção de yaw
   da tag. O modo `tag_normal` (quadrar com a face) SÓ depois de validar o
   sinal do `pitch_deg` (check 6 do 1.4) e o
   `DOCK_PITCH_TO_TAG_YAW_OFFSET_RAD` (default **0.0** = convenção do robô REAL;
   o SIMULADOR usa π. Se a aproximação chegar espelhada, inverta no config).
4. Segurança: cobrir a tag durante o DOCKING **não** para (ver 3.3 item 1) —
   validar que PARADO na UI e os dois watchdogs interrompem o dock.
5. Erro sistemático de posição final = odometria (voltar ao 2.4/3.1) — o dock
   herda a qualidade dela; não mexa em parâmetro do dock antes de fechar a
   odometria.

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

---

## PRONTUÁRIO — problemas prováveis e como reconhecê-los

Previsões baseadas no que já vimos na bancada (2026-07-06). Quando algo der
errado, procure o sintoma aqui ANTES de debugar do zero.

| Sintoma | Causa provável | Ação |
|---|---|---|
| Robô não parte com talo baixo, ou dá tranco ao partir | Atrito estático + duty baixo; integral lento | Esperado. Anotar limiar; sintonia 3.1 (Ki) |
| Anda reto na bancada, curva no chão | Raio efetivo desigual entre pneus (carga esmaga diferente) | Teste de rolagem por roda (3.1 item 1), usar média; persistindo, anotar |
| Overshoot/oscilação de velocidade no chão | Ganhos PID acertados com roda no ar | Ziegler-Nichols (3.1 item 6) |
| Robô "amolece" ao longo da sessão; missão mais lenta | Bateria caindo (PID satura antes) | Medir tensão sob carga; recarregar; 3.6 |
| Heading deriva parado, ou giro conta errado | Gyro calibrado com robô balançando no boot | Reboot do backend com robô em chão firme (2.0) |
| Para sozinho no meio da demo e volta | Wi-Fi com RTT > 400 ms → `COMMAND_WATCHDOG` | Testar rede do local; IP fixo; ficar perto do AP (3.6) |
| FACE gira para o lado errado / dock `tag_normal` espelhado | Convenção do `pitch_deg` da câmera real nunca validada | Check 6 do 1.4; `DOCK_PITCH_TO_TAG_YAW_OFFSET_RAD` |
| `z_cm` sistematicamente proporcional ao errado | Tag impressa ≠ 4 cm, ou captura ≠ 640×480 da calibração | Checks 1 e 4 do 1.4 |
| Dock/missão param fora do lugar, pior a cada curva | Escorregamento nas curvas de 90° (odometria degrada) | Piso menos liso / curvas mais lentas; fechar 2.4 antes de culpar o dock |
| Gravação do firmware falha (`chip stopped responding`) | GPIO 2 (VCC encoder) / 12 V ligado / cabo | Sequência (a)–(e) no troubleshooting do 1.2 |
| Encoder falha só com motores ligados | Alimentação por GPIO 2/4 no limite de corrente + ruído | Migrar para 3V3/GND reais (checklist 1.1) |
| `Device or resource busy` na serial | Monitor, bench e backend disputando a UART | Fechar um antes de abrir o outro (regra de ouro) |
| Uma roda satura e a outra morre, alternando | Canais de motor trocados (malhas PID cruzadas) | Um lado por vez (1.3 item 1); remapear `PIN_MOTOR_*` |
