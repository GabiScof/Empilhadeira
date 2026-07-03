# Hardware Bring-Up

[ref: `firmware/src/config.h`, `firmware/README.md`, `pi/app/config.py`]

Guia de montagem, energização e calibração do hardware físico da empilhadeira.
Siga a ordem das seções — energizar motores antes de validar níveis lógicos
pode danificar GPIOs ou drivers.

## Checklist Rápido

- [ ] Fonte 12 V dimensionada para 3 motores + ESP32/Pi
- [ ] GND comum entre fonte, L298n, ESP32 e Pi
- [ ] Jumpers ENA/ENB **removidos** nos dois L298n
- [ ] Level shifter nos encoders NXT (se saída 5 V)
- [ ] Pull-up externo 10 kΩ → 3V3 nas fases do encoder direito (GPIO 34/35)
- [ ] Sem pull-up externo no GPIO 12 (strapping — ESQ IN1)
- [ ] MPU-6050 em 3.3 V (I2C)
- [ ] Fim-de-curso: desabilitados (-1) — operador solta o botão do garfo antes do fim do curso
- [ ] Firmware gravado e frames de sensor a 20 Hz no monitor serial
- [ ] Backend Pi com `SIM=0` recebendo telemetria
- [ ] Mapa JSON medido na arena real

---

## Mapa de Pinos do ESP32

Fonte: `firmware/src/config.h` (ESP32 DevKit V1, 30 pinos).

> **Alinhado 1:1 com `Testes_eletronica.ino` (fonte da verdade da placa real).**
> Os nomes entre colchetes são os defines equivalentes naquele firmware de teste.

### Motores de Tração — L298n #1

| Função | GPIO | Destino |
|--------|------|---------|
| Motor Esq IN1 | 12 | L298n IN1 (canal A) [M2_IN1] |
| Motor Esq IN2 | 14 | L298n IN2 (canal A) [M2_IN2] |
| Motor Esq PWM | 13 | L298n ENA (canal A) — LEDC ch0 [M2_EN] |
| Motor Dir IN1 | 27 | L298n IN3 (canal B) [M3_IN1] |
| Motor Dir IN2 | 26 | L298n IN4 (canal B) [M3_IN2] |
| Motor Dir PWM | 25 | L298n ENB (canal B) — LEDC ch1 [M3_EN] |

### Motor do Garfo — L298n #2

| Função | GPIO | Destino |
|--------|------|---------|
| Fork IN1 | 18 | L298n #2 IN1 [M1_IN1] |
| Fork IN2 | 19 | L298n #2 IN2 [M1_IN2] |
| Fork PWM | 5 | L298n #2 ENA — LEDC ch2 [M1_EN] |

### Encoders (Lego NXT 53787)

| Função | GPIO | Observação |
|--------|------|------------|
| Encoder Esq A | 32 | Interrupção RISING [ENC1_A] |
| Encoder Esq B | 33 | Leitura de sentido [ENC1_B] |
| Encoder Dir A | 34 | Interrupção RISING — **input-only, pull-up externo obrigatório** [ENC2_A] |
| Encoder Dir B | 35 | Leitura de sentido — **input-only, pull-up externo obrigatório** [ENC2_B] |

### Fim-de-Curso do Garfo

| Função | GPIO | Observação |
|--------|------|------------|
| Limite superior | -1 | **Desabilitado** — chave não montada; `forkAtTopLimit()` retorna sempre `false` |
| Limite inferior | -1 | **Desabilitado** — chave não montada; `forkAtBottomLimit()` retorna sempre `false` |

Quando as chaves forem instaladas, definir os GPIOs em `config.h` — **GPIO 5
agora é o PWM do garfo**, então escolher outros pinos livres (ex.: 15, 4, 16, 17).

### I2C — MPU-6050

| Função | GPIO |
|--------|------|
| SDA | 21 |
| SCL | 22 |

Endereço I2C: `0x68` (AD0 = GND).

---

## Avisos sobre Strapping Pins

GPIOs que **não devem ser usados** ou exigem cuidado especial:

| GPIO | Risco |
|------|-------|
| **0** | Strapping — LOW no boot entra em flash mode |
| **2** | Strapping — pode afetar boot |
| **6–11** | Flash SPI interno — **nunca usar** |
| **12** | Strapping — altera tensão do flash. **USADO como ESQ IN1 [M2_IN1]**: precisa estar LOW no boot. Como IN1 fica LOW em repouso, funciona — mas **não colocar pull-up externo** nele |
| **34–39** | Input-only, **sem pullup interno**. **34/35 usados no encoder direito** → pull-up externo 10 kΩ → 3V3 obrigatório |
| **5** | Strapping (HIGH no boot). **USADO como PWM do garfo [M1_EN]** — LEDC só ativa depois do boot, ok |

Herdamos esses dois cuidados da placa real (`Testes_eletronica.ino`):

1. **GPIO 12 (roda ESQ IN1)** é strapping pin — precisa estar LOW no boot ou a
   seleção de tensão da flash falha. IN1 idle = LOW, então funciona; apenas
   **nunca** adicionar pull-up externo nesse fio.
2. **GPIO 34/35 (encoder direito)** são input-only sem pull-up interno. O
   `pinMode(INPUT_PULLUP)` neles é silenciosamente ignorado pelo hardware —
   **sem pull-up externo (10 kΩ → 3V3) o encoder direito não lê nada**. O
   `Testes_eletronica.ino` usa `INPUT` puro nesses pinos, confirmando que a
   placa depende de pull-up externo.

---

## Level Shifter — Encoders NXT

Os encoders Lego NXT operam tipicamente a **5 V** na saída. O ESP32 aceita
no máximo **3,3 V** nos GPIOs.

**Antes de conectar**, medir com multímetro a tensão nos pinos amarelo/azul
do conector NXT com o motor girando.

| Situação | Solução |
|----------|---------|
| Saída ≤ 3,3 V | Conexão direta (raro) |
| Saída 5 V push-pull | Level shifter bidirecional (TXS0108E, 74LVC245) **ou** divisor resistivo 1kΩ + 2kΩ |
| Saída open-drain fraca | Pullup externo a 3,3 V pode ser suficiente — **validar** |

Fiação encoder (conector 6 pinos NXT):

```
Pin 5 (amarelo) → fase A → GPIO 32 (esq) / GPIO 34 (dir) (via level shifter se necessário)
Pin 6 (azul)    → fase B → GPIO 33 (esq) / GPIO 35 (dir)
Pin 1 (branco)  → 5 V ou 3,3 V (conforme motor)
Pin 2 (preto)   → GND
```

> **Encoder direito (GPIO 34/35):** além do level shifter, esses pinos são
> input-only sem pull-up interno — instalar pull-up externo 10 kΩ → 3V3 em
> cada fase, senão a leitura fica sempre zero.

---

## Trilhas de Alimentação

### Fonte Principal — 12 V

Alimenta os dois módulos L298n (motores de tração + garfo). Dimensionar
corrente para pico dos três motores simultâneos (~2–3 A por canal, dependendo
da carga).

```
Fonte 12 V ──┬── L298n #1 (VCC motores)
             ├── L298n #2 (VCC garfo)
             └── Entrada do regulador buck (Pi + lógica)
GND comum ────┴── ESP32 GND, L298n GND, Pi GND, MPU GND
```

### Buck MP2307 — 5 V para Raspberry Pi

O Raspberry Pi precisa de **5 V estável @ ≥ 2,5 A**. Recomenda-se um módulo
**buck MP2307** (ou equivalente) a partir dos 12 V da bateria/fonte:

- Eficiência ~90% (vs. dissipação térmica de reguladores lineares)
- Ajustar trimpot para **5,0–5,1 V** medidos sob carga
- Adicionar capacitor eletrolítico 470–1000 µF na saída

### AMS1117-3,3 V — ESP32 e Lógica

O ESP32 opera a **3,3 V**. Módulos AMS1117-3.3 são comuns, mas têm limitações:

| Problema | Detalhe |
|----------|---------|
| Regulador **linear** | Dissipa `(Vin − 3,3 V) × I` como calor |
| Dropout ~1,1 V | A partir de 5 V USB funciona; a partir de 12 V **não use AMS1117 direto** |
| Corrente máxima ~800 mA | Insuficiente se alimentar ESP32 + MPU + pullups de encoder |

**Recomendação:**

- Alimentar ESP32 via **USB** (5 V do buck MP2307) durante bring-up, **ou**
- Usar buck 12 V → 3,3 V dedicado (ex.: LM2596 ajustado, ou AMS1117 **só**
  se a entrada for 5 V regulada)

> **Nunca** alimentar o ESP32 pelo pino 5V out do L298n — tensão instável e
> sem proteção.

### Separação de Massas

Manter **GND comum** entre fonte, drivers, ESP32 e Pi. Evitar loops de
corrente de motor passando pelo GND do Pi — usar ponto único de estrela
próximo à fonte.

---

## Dual L298N — Três Motores

| Módulo | Canais | Motores |
|--------|--------|---------|
| L298n #1 | A + B | Roda esquerda + roda direita |
| L298n #2 | A | Garfo (JGY-370 worm gear) |

**Obrigatório:** remover jumpers ENA/ENB em ambos os módulos para habilitar
controle PWM pelos GPIOs 13 (esq), 25 (dir) e 5 (garfo).

PWM: 20 kHz, 8 bits (0–255 duty). Ver `LEDC_FREQ_HZ` e `LEDC_RESOLUTION_BITS`
em `config.h`.

---

## Garfo Manual + Fim-de-Curso

O garfo é **sempre manual** — o operador comanda via WebSocket (`garfo:
subir/descer/parar`), repassado ao ESP32 no campo `garfo` do setpoint.

### Comportamento no Firmware

- Duty fixo `FORK_DUTY = 180` (~70%) enquanto o comando estiver ativo
- Fim-de-curso (quando instalado) corta o motor **localmente** em ~10 ms
  (próximo ciclo PID) — **hoje desabilitado com -1 em `config.h`**
- Worm gear retém carga sem PWM de manutenção
- Nenhum campo extra no protocolo serial para garfo autônomo

### Fiação dos Switches

**Estado atual: fim-de-curso DESABILITADO** (`PIN_FORK_LIMIT_TOP/BOTTOM = -1`
em `config.h`). O robô ainda não tem as chaves montadas; `motors.cpp` pula o
`pinMode` e `forkAt*Limit()` retorna sempre `false` — o garfo nunca é
bloqueado por limite. **O operador é o fim-de-curso**: soltar o botão antes
do fim do curso mecânico.

Quando as chaves forem instaladas:

```
Switch NO (topo):   COM → GND,  NO → GPIO livre (ex.: 15)
Switch NO (base):   COM → GND,  NO → GPIO livre (ex.: 4)
INPUT_PULLUP: HIGH = livre, LOW = no limite
```

> GPIO 5 **não está mais disponível** (é o PWM do garfo). Definir os novos
> GPIOs em `config.h` e regravar o firmware.

Se os switches forem NC, alterar `FORK_LIMIT_ACTIVE_LEVEL` para `HIGH` em
`config.h`.

---

## Transição SIM=1 → Hardware Real

### 1. Firmware

```bash
cd src/firmware
pio run --target upload
pio device monitor   # verificar frames @ 20 Hz
```

### 2. Configuração do Pi

```bash
# .env
SIM=0
SERIAL_PORT=/dev/ttyUSB0    # ou /dev/ttyACM0
SERIAL_BAUDRATE=115200
MAP=nome_do_mapa_medido
```

### 3. Validar Comunicação

```bash
cd src/pi
python -m app.main
# Telemetria deve fluir; encoders respondem ao girar rodas manualmente
```

### 4. Validar Frontend

- Joystick manual move as rodas
- Garfo sobe/desce com botões
- Watchdog: desconectar USB → motores param em < 200 ms

### 5. Calibrar e Testar Missão

- Medir arena → criar/atualizar mapa JSON
- Calibrar EKF com tags visíveis
- Rodar missão em arena aberta antes de corredores

---

## Checklist de Calibração

### Mecânica

| Parâmetro | Onde | Como medir |
|-----------|------|------------|
| Raio da roda `WHEEL_RADIUS_R_CM` | `pi/app/config.py` | Medir diâmetro ÷ 2 |
| Distância entre rodas `WHEEL_BASE_L_CM` | `pi/app/config.py` | Centro eixo a centro eixo |
| Massa do pallet `PALLET_MASS_KG` | `pi/app/config.py` | Balança — **TODO(equipe)** |
| Altura máxima garfo `EMU_FORK_MAX_HEIGHT` | `pi/app/config.py` | Medir curso vertical |

### Encoders

| Parâmetro | Onde | Como validar |
|-----------|------|--------------|
| `ENCODER_PPR = 360` | `firmware/config.h` | 1 volta manual → ~360 pulsos no monitor |
| Sentido dos motores | `config.h` (`MOTOR_ESQ_INV=true`, `MOTOR_DIR_INV`, `FORK_INV`) | Setpoint positivo → as DUAS rodas para frente; "subir" sobe o garfo. ESQ já vem invertida (herdado de `M2_INV` no Testes_eletronica.ino) |
| Sinal dos encoders | `config.h` (`ENC_ESQ_INV`, `ENC_DIR_INV`) | Roda para frente → ω positivo no monitor. Se negativo, inverter o flag (crítico: sinal errado faz o PID divergir) |
| Level shifter | Fiação | Osciloscópio/multímetro ≤ 3,3 V nos GPIOs |

### PID (Malha Interna)

| Parâmetro | Onde | Procedimento |
|-----------|------|--------------|
| Kp, Ki, Kd | `firmware/config.h` | Ziegler-Nichols (ver `firmware/README.md` §4.2) |
| `SETPOINT_TIMEOUT_MS = 200` | `firmware/config.h` | Validar watchdog desconectando USB |
| `FORK_DUTY = 180` | `firmware/config.h` | Testar com carga real no garfo |

### Visão / AprilTag

| Parâmetro | Onde | Procedimento |
|-----------|------|--------------|
| Intrínsecos `fx, fy, cx, cy` | `pi/calibracao/camera_intrinsics.json` | Calibração xadrez — ver [`camera-calibration.md`](./camera-calibration.md) |
| Tamanho da tag `APRILTAG_SIZE_CM` | `pi/app/config.py` | Medir tag impressa com paquímetro |
| Offset câmera→garfo | `pi/app/config.py` | Medir posição relativa — **TODO(equipe)** |
| Família `tag25h9` | fixo | Imprimir tags da família correta |

### Navegação (Malha Externa)

| Parâmetro | Onde | Procedimento |
|-----------|------|--------------|
| `NAV_K_DIST`, `NAV_K_HEADING` | `pi/app/config.py` | Sintonizar após PID interno estável |
| `NAV_POS_TOL_M`, `NAV_HEADING_TOL_RAD` | `pi/app/config.py` | Ajustar precisão de parada |
| `EKF_Q_*`, `EKF_R_*` | `pi/app/config.py` | Comparar odometria pura vs. com tag |
| `EKF_MAHALANOBIS_GATE` | `pi/app/config.py` | Testar com blur / detecções ruins |

### Mapa

| Item | Procedimento |
|------|--------------|
| Dimensões da arena | Fita métrica, canto inferior esquerdo = origem |
| Posição de cada tag | (x, y) em metros + `yaw_deg` |
| Waypoints (se corredor) | Pontos nos corredores + arestas sem cruzar paredes |
| Validar JSON | `python -c "from app.world.map_schema import load_map; load_map('maps/...')"` |

---

## Troubleshooting

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| ESP32 não grava / boot falha | GPIO 12 (ESQ IN1) puxado HIGH no boot | Remover pull-up externo do fio IN1 esq; desconectar driver ao gravar se preciso |
| Encoder sempre zero | Sem level shifter / fiação | Verificar tensão e ISR |
| Encoder **direito** sempre zero | GPIO 34/35 sem pull-up externo | Instalar 10 kΩ → 3V3 em cada fase (pull-up interno não existe nesses pinos) |
| Motor oscila | Kp alto ou PPR errado | Ziegler-Nichols; validar PPR |
| Garfo não segura carga | Duty baixo ou motor errado | Aumentar `FORK_DUTY`; confirmar worm gear |
| Pi reinicia ao acionar motor | Fonte subdimensionada | Buck MP2307 com margem; capacitor na saída |
| ESP32 reseta com motores | Queda de 3,3 V | Separar alimentação lógica da tracionária |
| MPU retorna zeros | I2C mal conectado | Verificar SDA/SCL, endereço 0x68 |
| Tag não detectada | Intrínsecos errados / tag pequena | Recalibrar câmera; aumentar tag |

Documentação complementar: [`firmware/README.md`](../firmware/README.md).
