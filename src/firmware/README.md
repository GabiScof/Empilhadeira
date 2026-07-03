# Firmware ESP32 — Empilhadeira Robótica

> **Branch `feat/firmware-production-ready`: todos os pinos e constantes estão definidos.
> Pronto para gravar no ESP32 e testar no hardware.**

Controle de baixo nível em tempo real: PID por roda, acionamento PWM/L298n, leitura de
encoders por interrupção, MPU-6050, garfo com fim-de-curso e protocolo serial JSON+CRC8.

---

## Sumário

1. [Arquitetura do Firmware](#1-arquitetura-do-firmware)
2. [Mapa de Pinos (GPIO)](#2-mapa-de-pinos-gpio)
3. [Fiação Detalhada](#3-fiação-detalhada)
4. [Constantes e Calibração](#4-constantes-e-calibração)
5. [Comportamento Esperado](#5-comportamento-esperado)
6. [Como Compilar e Gravar](#6-como-compilar-e-gravar)
7. [Procedimentos de Teste](#7-procedimentos-de-teste)
8. [Troubleshooting](#8-troubleshooting)
9. [Decisões Pendentes (TODO)](#9-decisões-pendentes-todo)

---

## 1. Arquitetura do Firmware

```
┌──────────────────────────────────────────────────────┐
│                    loop()                             │
│                                                      │
│  ┌─────────────────────┐  ┌────────────────────────┐ │
│  │  Serial RX (contínuo)│  │ Watchdog (200 ms)      │ │
│  │  SetpointFrameDecoder│  │ → motorsStop() se cair │ │
│  └─────────┬───────────┘  └───────────┬────────────┘ │
│            │                          │              │
│  ┌─────────▼──────────────────────────▼──────────┐   │
│  │  PID Loop ~100 Hz (cada 10 ms)                │   │
│  │  1. encoderReadEsq/Dir(dt) → ω medido         │   │
│  │  2. pid.update(medido, dt) → esforço u        │   │
│  │  3. motorSetWheel(u) → PWM/L298n              │   │
│  │  4. motorSetFork(cmd) → com fim-de-curso      │   │
│  └───────────────────────────────────────────────┘   │
│                                                      │
│  ┌───────────────────────────────────────────────┐   │
│  │  Serial TX ~20 Hz (cada 50 ms)                │   │
│  │  1. readMpu(sensors) → I2C burst read 14B     │   │
│  │  2. encodeSensors() → JSON+CRC8+\n            │   │
│  │  3. Serial.write(frame)                       │   │
│  └───────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

- **Dual-cadence non-blocking**: `millis()` controla os intervalos, sem `delay()`.
- **PID por roda**: Kp + Ki + Kd com anti-windup (clamping integral a ±500).
- **Watchdog de setpoint**: 200 ms sem mensagem do Pi → motores zerados.
- **Garfo com fim-de-curso**: corte local instantâneo (~100 Hz), sem depender do Pi.

---

## 2. Mapa de Pinos (GPIO)

### Tabela completa

Alinhado 1:1 com `Testes_eletronica.ino` (fonte da verdade da placa real).
Os nomes entre colchetes são os defines equivalentes naquele firmware de teste.

| Função              | GPIO | Dir     | Destino no Hardware          | Observação                     |
|---------------------|------|---------|------------------------------|--------------------------------|
| Motor Esq IN1       | 12   | OUTPUT  | L298n #1 IN1 (canal A)      | [M2_IN1] ⚠️ strapping — LOW no boot, sem pull-up externo |
| Motor Esq IN2       | 14   | OUTPUT  | L298n #1 IN2 (canal A)      | [M2_IN2]                       |
| Motor Esq PWM       | 13   | OUTPUT  | L298n #1 ENA (canal A)      | [M2_EN] LEDC ch0, 20 kHz, 8 bits |
| Motor Dir IN1       | 27   | OUTPUT  | L298n #1 IN3 (canal B)      | [M3_IN1]                       |
| Motor Dir IN2       | 26   | OUTPUT  | L298n #1 IN4 (canal B)      | [M3_IN2]                       |
| Motor Dir PWM       | 25   | OUTPUT  | L298n #1 ENB (canal B)      | [M3_EN] LEDC ch1, 20 kHz, 8 bits |
| Fork IN1            | 18   | OUTPUT  | L298n #2 IN1               | [M1_IN1]                       |
| Fork IN2            | 19   | OUTPUT  | L298n #2 IN2               | [M1_IN2]                       |
| Fork PWM            | 5    | OUTPUT  | L298n #2 ENA               | [M1_EN] LEDC ch2, 20 kHz, 8 bits |
| Encoder Esq A       | 32   | INPUT↑  | NXT 53787 encoder fase A    | [ENC1_A] Interrupção RISING    |
| Encoder Esq B       | 33   | INPUT↑  | NXT 53787 encoder fase B    | [ENC1_B] Leitura de sentido na ISR |
| Encoder Dir A       | 34   | INPUT   | NXT 53787 encoder fase A    | [ENC2_A] ⚠️ input-only — pull-up EXTERNO 10k→3V3 |
| Encoder Dir B       | 35   | INPUT   | NXT 53787 encoder fase B    | [ENC2_B] ⚠️ input-only — pull-up EXTERNO 10k→3V3 |
| Fork Limit Top      | -1   | —       | (chave não montada)         | **Desabilitado** — nunca bloqueia |
| Fork Limit Bottom   | -1   | —       | (chave não montada)         | **Desabilitado** — nunca bloqueia |
| I2C SDA             | 21   | I2C     | MPU-6050 SDA               | Padrão ESP32                   |
| I2C SCL             | 22   | I2C     | MPU-6050 SCL               | Padrão ESP32                   |

`INPUT↑` = INPUT_PULLUP (resistor interno de ~45 kΩ). Em GPIO 34/35 o
`pinMode(INPUT_PULLUP)` é ignorado pelo hardware — pull-up externo obrigatório.

### GPIOs com cuidado especial

| GPIO     | Motivo                                                   |
|----------|----------------------------------------------------------|
| 0        | Strapping pin (flash mode se LOW no boot) — não usado    |
| 2        | Strapping pin (pode entrar em flash mode) — não usado    |
| 6-11     | Conectados ao flash SPI interno — **nunca usar**         |
| 12       | Strapping (tensão do flash). **Usado como ESQ IN1** — funciona porque IN1 idle=LOW; **não** adicionar pull-up externo |
| 34-39    | Input-only **sem pullup interno**. **34/35 usados no ENC2** — pull-up externo obrigatório |

---

## 3. Fiação Detalhada

### 3.1 L298n #1 (rodas)

```
ESP32 GPIO 12 ──── L298n IN1 (canal A)   ← strapping: sem pull-up externo!
ESP32 GPIO 14 ──── L298n IN2 (canal A)
ESP32 GPIO 13 ──── L298n ENA (canal A)   ← Remover jumper ENA!
ESP32 GPIO 27 ──── L298n IN3 (canal B)
ESP32 GPIO 26 ──── L298n IN4 (canal B)
ESP32 GPIO 25 ──── L298n ENB (canal B)   ← Remover jumper ENB!

L298n VCC (12V)  ── Fonte 12V
L298n GND        ── GND comum (ESP32 + fonte)
L298n 5V out     ── NÃO usar para alimentar ESP32 (usar USB ou reg. externo)

Motor Esq (+/-) ─── L298n OUT1/OUT2
Motor Dir (+/-) ─── L298n OUT3/OUT4
```

**IMPORTANTE**: Remover os jumpers de ENA e ENB do módulo L298n! Esses jumpers
forçam 5V constante no enable, desabilitando o controle PWM. Com o jumper
removido, o pino ENA/ENB fica livre para receber o sinal PWM do ESP32.

### 3.2 L298n #2 (garfo)

```
ESP32 GPIO 18 ──── L298n #2 IN1
ESP32 GPIO 19 ──── L298n #2 IN2
ESP32 GPIO  5 ──── L298n #2 ENA          ← Remover jumper ENA!

Motor Garfo (+/-) ── L298n #2 OUT1/OUT2
```

Alternativa: driver menor (L9110S, TB6612) se o garfo precisar de menos corrente.

### 3.3 Encoders (Lego NXT 53787)

```
Motor NXT (conector 6 pinos):
  Pin 1 (branco) ─── 5V (ou 3.3V — verificar)
  Pin 2 (preto)  ─── GND
  Pin 5 (amarelo)─── ESP32 GPIO 32 (Esq A) / GPIO 34 (Dir A)
  Pin 6 (azul)   ─── ESP32 GPIO 33 (Esq B) / GPIO 35 (Dir B)
```

> **Encoder direito (GPIO 34/35)**: pinos input-only sem pull-up interno —
> instalar pull-up externo 10 kΩ → 3V3 em cada fase, senão a leitura fica
> sempre zero.

> **Nota**: o encoder do NXT opera a 5V pela especificação original. Se o sinal
> de saída for 5V (push-pull), pode ser necessário um divisor resistivo
> (1k + 2k) ou level shifter para proteger o ESP32 (máximo 3.3V nos GPIOs).
> Verificar com multímetro antes de conectar!

### 3.4 MPU-6050

```
MPU VCC ─── 3.3V do ESP32
MPU GND ─── GND
MPU SDA ─── ESP32 GPIO 21
MPU SCL ─── ESP32 GPIO 22
MPU AD0 ─── GND (endereço 0x68)
```

### 3.5 Fim-de-curso do garfo

**Estado atual: DESABILITADO** (`PIN_FORK_LIMIT_TOP/BOTTOM = -1` em `config.h`).
As chaves não estão montadas no robô. `motors.cpp` pula o `pinMode` e
`forkAtTopLimit()`/`forkAtBottomLimit()` retornam sempre `false` — o motor do
garfo nunca é bloqueado por limite. **O operador deve soltar o botão antes do
fim do curso mecânico** (o worm gear segura a posição).

Quando as chaves forem instaladas (fiação de referência):

```
Micro switch NO (topo):
  Terminal C (comum)  ─── GND
  Terminal NO         ─── ESP32 GPIO livre (ex.: 15)

Micro switch NO (base):
  Terminal C (comum)  ─── GND
  Terminal NO         ─── ESP32 GPIO livre (ex.: 4)
```

> GPIO 5 **não está mais disponível** para fim-de-curso — é o PWM do garfo.
> Definir os novos GPIOs em `config.h` e regravar.

Funcionamento: INPUT_PULLUP mantém o pino HIGH. Quando o garfo atinge o limite,
o switch fecha e puxa o pino para LOW. O firmware detecta LOW = acionado e bloqueia
o motor naquele sentido.

Se os switches forem NC (Normally Closed), trocar `FORK_LIMIT_ACTIVE_LEVEL` para
`HIGH` em `config.h`.

---

## 4. Constantes e Calibração

### 4.1 Valores definidos (prontos para uso)

| Constante              | Valor  | Unidade | Justificativa                                 |
|------------------------|--------|---------|-----------------------------------------------|
| `SERIAL_BAUDRATE`      | 115200 | baud    | Decisão fechada (AGENTS.md §2)                |
| `SERIAL_HZ`            | 20     | Hz      | Taxa de troca serial (AGENTS.md §2)           |
| `PID_HZ`               | 100    | Hz      | Malha de controle (AGENTS.md §7)              |
| `SETPOINT_TIMEOUT_MS`  | 200    | ms      | 4 mensagens perdidas @ 20 Hz                  |
| `LEDC_FREQ_HZ`         | 20000  | Hz      | Acima da faixa audível                        |
| `LEDC_RESOLUTION_BITS` | 8      | bits    | 256 níveis (0-255)                            |
| `ENCODER_PPR`          | 360    | pulsos  | Lego NXT 53787 (saída do redutor)             |
| `FORK_DUTY`            | 180    | 0-255   | ~70% — suficiente para worm gear              |
| `FORK_LIMIT_ACTIVE_LEVEL` | LOW | -       | Switch NO + pullup                            |
| `MPU6050_ADDR`         | 0x68   | -       | AD0=GND (padrão)                              |

### 4.2 Ganhos PID (requerem ajuste)

| Ganho       | Valor Inicial | Para que serve                          |
|-------------|---------------|-----------------------------------------|
| `PID_KP_*`  | 20.0          | Resposta proporcional ao erro           |
| `PID_KI_*`  | 5.0           | Elimina erro de regime permanente       |
| `PID_KD_*`  | 1.0           | Amortece oscilações                     |
| `PID_INTEGRAL_LIMIT` | 500.0 | Anti-windup: limita acúmulo integral  |

**Procedimento de sintonia (Ziegler-Nichols simplificado):**

1. Zerar Ki e Kd em `config.h`.
2. Subir Kp gradualmente (10 → 20 → 30 → ...) até o motor oscilar visivelmente
   em torno do setpoint. Esse valor é o **ganho crítico** Ku.
3. Medir o período da oscilação Tu (com cronômetro ou observando a telemetria).
4. Calcular: **Kp = 0.6 × Ku**, **Ki = 2 × Kp / Tu**, **Kd = Kp × Tu / 8**.
5. Gravar e testar. Ajustar empiricamente (±20%) até suave.

### 4.3 Coisas para verificar antes de ligar

- [ ] Tensão do encoder NXT (5V push-pull? → precisa divisor/level shifter)
- [ ] Sentido de rotação dos motores (se invertido, trocar IN1↔IN2 em `config.h`)
- [ ] ENCODER_PPR correto (girar eixo 1 volta completa → deve ler 360 pulsos)
- [ ] Switches de fim-de-curso: apertar manualmente e verificar no Serial Monitor
- [ ] MPU-6050 respondendo (I2C scan: `Wire.beginTransmission(0x68)`)
- [ ] Jumpers ENA/ENB do L298n **removidos**

---

## 5. Comportamento Esperado

### 5.1 Boot (power-on ou reset)

1. `Serial.begin(115200)` — UART pronta.
2. `motorsBegin()` — LEDC configurado, fim-de-curso inicializados, motores zerados.
3. `encodersBegin()` — ISRs ativadas, contadores zerados.
4. `Wire.begin(21, 22)` — I2C inicializado.
5. MPU-6050 acordado (PWR_MGMT_1 = 0x00), aguarda 50 ms para estabilização.
6. Loop principal inicia. `setpointValid = false` → motores parados.
7. ESP32 envia sensores a 20 Hz pela serial (encoders zerados, MPU lendo).

### 5.2 Pi conecta e envia setpoints

1. Frame JSON+CRC8+\n chega na UART → `SetpointFrameDecoder` decodifica.
2. `setpointValid = true`, PID ativado, motores respondem.
3. Telemetria (sensores) flui a 20 Hz de volta para o Pi.

### 5.3 Operação do garfo

- Operador pressiona "subir" no app → Pi envia `"garfo": "subir"` → motor do garfo
  aciona com duty 180 no sentido de subida.
- Garfo atinge o topo → switch fecha → `forkAtTopLimit()` retorna true → motor para
  **instantaneamente** (próximo ciclo PID, ~10 ms).
- Operador solta o botão → Pi envia `"garfo": "parar"` → motor fica parado.
  O worm gear impede que a carga desça por gravidade.

### 5.4 Perda de comunicação serial

- Pi desconecta (USB solto, crash, etc.).
- Nenhum setpoint novo por 200 ms.
- Watchdog dispara: `motorsStop()` + PID reset.
- ESP32 continua enviando sensores (para diagnóstico quando reconectar).
- Pi reconecta → envia setpoint → `setpointValid = true` → operação retoma.

### 5.5 Reset do ESP32

- Motores param imediatamente (LEDC reseta).
- Setup() roda novamente (sequência do §5.1).
- Sem setpoint → motores parados até o Pi enviar novo comando.

---

## 6. Como Compilar e Gravar

### Pré-requisitos

```bash
pip install platformio    # ou: brew install platformio
```

### Compilar

```bash
cd src/firmware
pio run
```

O PlatformIO baixa automaticamente o toolchain e as libs (ArduinoJson) na primeira vez.

### Gravar no ESP32

```bash
pio run --target upload
```

Se o ESP32 não for detectado, verificar:
- Cabo USB é de dados (não só carregamento).
- Driver CP2102/CH340 instalado.
- Porta correta: `pio device list` para ver portas disponíveis.

### Monitor Serial

```bash
pio device monitor
```

Mostra os frames de sensores que o ESP32 envia a 20 Hz. Exemplo:

```
{"enc":{"esq":0.00,"dir":0.00},"mpu":{"ax":0.12,"ay":-0.03,"az":9.78,"gx":0.01,"gy":-0.02,"gz":0.00,"temp_c":25.4},"bms":null}*a3
```

### Atalho: compilar + gravar + monitor

```bash
pio run --target upload && pio device monitor
```

Ou usar o script:

```bash
cd src && bash scripts/flash_firmware.sh
```

---

## 7. Procedimentos de Teste

### Teste 1: Compilação limpa

```bash
cd src/firmware && pio run
```

**Esperado**: `SUCCESS` sem warnings (exceto eventuais warnings do ArduinoJson).

### Teste 2: Serial + MPU-6050

1. Gravar firmware, abrir monitor serial.
2. **Sem nenhum motor ou encoder conectado.**
3. **Esperado**: frames JSON a 20 Hz com `enc.esq=0, enc.dir=0` e valores de MPU.
4. Inclinar o MPU-6050 → `ax/ay/az` mudam proporcionalmente.
5. `gx/gy/gz` devem estar próximos de zero quando parado.
6. Se tudo zero no MPU: verificar fiação I2C e endereço (ver §8).

### Teste 3: Encoders

1. Sem o Pi — enviar manualmente pelo monitor serial um setpoint:

   ```
   {"w_esq":0,"w_dir":0,"garfo":"parar"}*XX\n
   ```

   (Calcular o CRC correto ou desabilitar temporariamente a validação para teste.)

2. Girar o eixo do motor à mão → observar `enc.esq` ou `enc.dir` mudando.
3. Girar em ambos os sentidos → verificar que o sinal inverte.
4. Uma revolução completa = ~360 pulsos (verificar no monitor).

### Teste 4: Fim-de-curso do garfo

1. Abrir Serial Monitor.
2. Apertar manualmente o switch do topo → observar se o garfo para de subir.
3. Soltar → garfo pode subir novamente.
4. Repetir para o switch da base.
5. Se não funcionar: verificar fiação (C→GND, NO→GPIO) e `FORK_LIMIT_ACTIVE_LEVEL`.

### Teste 5: Direção dos motores

1. Enviar setpoint com `w_esq = 3.0, w_dir = 0.0` → roda esquerda gira para frente.
2. Se girar para trás: trocar `PIN_MOTOR_ESQ_IN1 ↔ PIN_MOTOR_ESQ_IN2` em `config.h`.
3. Repetir para roda direita.
4. Enviar `w_esq = 3.0, w_dir = 3.0` → robô anda para frente em linha reta.

### Teste 6: PID tuning

1. Definir Ki=0, Kd=0 em `config.h`. Compilar e gravar.
2. Enviar setpoint fixo (ex: `w_esq = 5.0`).
3. Observar a velocidade medida no monitor → aumentar Kp até oscilar.
4. Aplicar Ziegler-Nichols (§4.2).
5. Testar com rampas (0→5→0 rad/s) e observar overshoots.

### Teste 7: Garfo com carga

1. Colocar o pallet no garfo.
2. Comandar "subir" → garfo sobe com a carga?
   - Sim: `FORK_DUTY = 180` está adequado.
   - Não sobe: aumentar para 200 ou 220.
   - Sobe muito rápido: diminuir para 150.
3. Parar → a carga se mantém? (O worm gear deve segurar.)
4. Descer → desce suavemente?

### Teste 8: Integração com o Pi

1. Subir o backend do Pi (`python -m app.main`).
2. Pi começa a enviar setpoints a 20 Hz.
3. ESP32 responde com sensores a 20 Hz.
4. No app (frontend): mover o joystick → rodas respondem.
5. Comandar garfo subir/descer → garfo responde.
6. Puxar o cabo USB → watchdog para os motores em <200 ms.
7. Reconectar → operação retoma.

---

## 8. Troubleshooting

### Erro de compilação: `ledcSetup was not declared`

**Causa**: `espressif32` versão 7.x+ usa Arduino Core 3.x com API LEDC diferente.
**Solução**: O `platformio.ini` já está pinado em `espressif32@^6.0.0`. Se o erro
persistir, forçar:

```ini
platform = espressif32@6.9.0
```

### MPU-6050 retorna zeros

- Verificar fiação SDA (21) e SCL (22).
- Verificar se AD0 está em GND (endereço 0x68).
- Teste I2C:

```cpp
Wire.beginTransmission(0x68);
byte error = Wire.endTransmission();
Serial.println(error);  // 0 = OK, 2 = NACK
```

### Motor gira no sentido errado

Trocar IN1 ↔ IN2 em `config.h` para o motor afetado. Recompilar e gravar.

### Encoder lê zero mesmo com motor girando

- Verificar fiação dos pinos A e B.
- Verificar se o encoder opera a 3.3V ou precisa de level shifter.
- Testar com `digitalRead()` direto no pin do encoder.

### PID oscila/vibra

- Reduzir Kp em 30-50%.
- Aumentar Kd levemente.
- Verificar se ENCODER_PPR está correto (valor errado = velocidade medida errada).

### Garfo não segura a carga (desce sozinho)

- Se o motor NÃO é worm gear: a redução não é auto-travante, precisa de freio
  mecânico ou PWM de manutenção.
- Se é worm gear mas ainda desce: a carga pode exceder o torque de retenção.
  Considerar um motor com maior relação de redução.

### GPIO 15 imprime lixo no boot

Normal — GPIO 15 HIGH no boot habilita debug output na UART. São ~100 bytes de
lixo na primeira vez. O `SetpointFrameDecoder` descarta automaticamente (quadros
sem '\n' válido são ignorados). Não causa problemas operacionais.

### ESP32 não entra em modo de gravação

Verificar se nenhum switch de fim-de-curso está puxando GPIO 5 para LOW durante
o boot. GPIO 5 é strapping pin — se LOW, pode afetar o boot. Desconectar o switch
do GPIO 5 temporariamente para gravar, ou usar GPIO 5 apenas após o boot.

---

## 9. Decisões Pendentes (TODO)

Itens que podem precisar de ajuste após testes com o hardware real:

| Item | Onde | Status |
|------|------|--------|
| Tensão dos encoders NXT (3.3V ou 5V?) | Fiação / level shifter | **Verificar com multímetro** |
| ENCODER_PPR = 360 correto? | `config.h` | **Validar girando 1 volta** |
| Sentido dos motores (IN1/IN2) | `config.h` | **Definir no primeiro teste** |
| Ganhos PID (Kp=20, Ki=5, Kd=1) | `config.h` | **Sintonizar com Ziegler-Nichols** |
| FORK_DUTY = 180 adequado? | `config.h` | **Testar com carga real** |
| Tipo dos switches (NO ou NC?) | `config.h` (`FORK_LIMIT_ACTIVE_LEVEL`) | **Confirmar na montagem** |
| BMS digital? | `main.cpp` / `config.h` | `has_bms = false` até definir |
| Faixa do giroscópio (±250°/s suficiente?) | `main.cpp` (configurar REG do MPU) | Provavelmente sim |
| Necessidade de debounce nos switches | `motors.cpp` | Avaliar se há ruído |

---

## Estrutura de Arquivos

```
firmware/
├── platformio.ini      # Config PlatformIO (espressif32@^6, ArduinoJson@^7)
├── README.md           # Este arquivo
└── src/
    ├── main.cpp        # Loop principal (PID 100Hz + Serial 20Hz + watchdog)
    ├── config.h        # TODOS os pinos, ganhos, taxas e constantes
    ├── pid.h/cpp       # Controlador PID com anti-windup
    ├── motors.h/cpp    # PWM/LEDC → L298n + garfo com fim-de-curso
    ├── encoders.h/cpp  # Leitura de quadratura por ISR (IRAM_ATTR)
    ├── protocol.h/cpp  # JSON+CRC8+\n framing + SetpointFrameDecoder
    └── lib/            # (vazio — libs externas via lib_deps)
```
