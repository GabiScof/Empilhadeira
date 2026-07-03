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

---

## FASE 0 — Setup único do Raspberry Pi (TUDO roda no Pi)

> **Topologia adotada:** não há laptop no meio. O Pi grava o firmware do ESP32
> (USB), roda o backend, roda a câmera e serve o frontend para o celular.
> Você opera o Pi por SSH; o celular só abre o navegador.

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

# 4. Node/npm (para servir o frontend do Pi)
sudo apt install -y nodejs npm
cd frontend && npm install && cd ..

# 5. Permissões de serial e câmera
sudo usermod -aG dialout,video $USER
# DESLOGAR e logar de novo (grupo só vale em sessão nova de SSH)

# 6. Descobrir porta do ESP32 e IP do Pi (anote os dois)
ls /dev/ttyUSB* /dev/ttyACM*
hostname -I
```

**Regra de ouro da porta serial:** só UM programa pode usar a UART por vez.
`pio device monitor`, `bench_setpoint.py` e o backend brigam pela mesma porta —
**sempre feche um antes de abrir o outro** (erro típico: `Device or resource busy`).

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

### 1.5 Backend + frontend no Pi, celular só abre o navegador

`.env` no Pi (base no `.env.example`):

```bash
SIM=0
REQUIRE_CAMERA_CALIBRATION=1
CAMERA_FRAME_WIDTH=640
CAMERA_FRAME_HEIGHT=480
MAP=corredor_6tags_80x200
SERIAL_PORT=/dev/ttyUSB0        # a porta anotada na Fase 0
# VITE_PI_WS_URL: NÃO precisa no setup tudo-no-Pi (ver abaixo)
```

**Terminal 1 (SSH) — backend:**
```bash
cd ~/Empilhadeira/src && ./scripts/run_pi.sh
```

**Terminal 2 (SSH) — frontend servido pelo próprio Pi:**
```bash
cd ~/Empilhadeira/src/frontend
npm run build && npm run preview -- --host    # sobe em http://0.0.0.0:4173
```

> `preview` (build estático) em vez de `npm run dev`: gasta muito menos CPU/RAM
> do Pi, que já roda visão @20 Hz + backend. Use `dev -- --host` só se estiver
> iterando no código do frontend.

**Celular** (mesma rede Wi-Fi): abrir `http://<IP_DO_PI>:4173`.
Não precisa configurar `VITE_PI_WS_URL`: sem essa env o frontend conecta em
`ws://<host da página>:8000/ws` — e o host da página **é** o IP do Pi.

| Log esperado (ordem) | Se não aparecer |
|---|---|
| `Modo REAL (hardware)` | `.env` não carregou ou SIM≠0 |
| `Serial loop (REAL) iniciado` | porta errada/ocupada (fechou o monitor? bench?), ou grupo dialout sem relogar |
| `Detector criado com calibração` | JSON de calibração quebrado → refazer 1.4 |

No celular: telemetria ~20 Hz; girar roda na mão move `rodas`; inclinar move `imu`;
tag na frente da câmera → `visao.detectado=true`.
Celular não conecta → confirmar mesma rede, `hostname -I`, e porta 4173/8000
livres no firewall do Pi (`sudo ufw status`, se houver ufw).

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
- [ ] Wi-Fi do local testado; IP do Pi fixo (anotar!); celular abre `http://<IP>:4173`
- [ ] Backend (`run_pi.sh`) e frontend (`npm run preview -- --host`) sobem nos dois
      terminais SSH — ou configurar systemd/tmux para subirem no boot do Pi
- [ ] `GET /maps/current` = `corredor_6tags_80x200`
- [ ] Tags fixadas nas posições do mapa (L* a x=0,05 m; R* a x=0,75 m;
      y = 0,40/1,00/1,60 m) — **remedir com fita no local**
- [ ] Iluminação testada com `teste_cam` (reflexo na tag = reposicionar/foscar)
- [ ] 1 volta manual + 1 missão completa de aquecimento antes da valendo
- [ ] Plano B ensaiado: missão inteira em MANUAL se a autonomia falhar
