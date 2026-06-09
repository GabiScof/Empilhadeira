# Firmware do ESP32 — Guia Completo de Integração

Firmware em **C++ (framework Arduino)**, build com **PlatformIO**. Responsável
pelo controle de tempo real da empilhadeira: PID por roda a ~100 Hz, leitura de
encoders/MPU-6050, acionamento dos motores via PWM (LEDC) → driver L298n, e
proteção mecânica do garfo via chaves fim-de-curso.

> **Estado:** lógica implementada. Aguardando definição dos parâmetros `TODO(equipe)`
> em `config.h` (pinos, ganhos PID, duty do garfo, PPR do encoder, etc.) para
> testes reais no hardware.

---

## Estrutura de arquivos

```
firmware/
├── platformio.ini              # board = esp32dev, framework = arduino, ArduinoJson v7
├── README.md                   # este arquivo
├── .gitignore                  # artefatos PlatformIO (.pio, .vscode)
└── src/
    ├── main.cpp                # loop dual: PID 100Hz + serial 20Hz + watchdog + MPU
    ├── config.h                # TODOS os pinos, taxas, ganhos — placeholders TODO(equipe)
    ├── pid.h / pid.cpp         # PID por roda com anti-windup (clamping integral)
    ├── motors.h / motors.cpp   # PWM (LEDC) → L298n: rodas + garfo + fim-de-curso
    ├── encoders.h / encoders.cpp   # leitura por interrupção (ISR quadratura)
    ├── protocol.h / protocol.cpp   # espelho C++ dos contratos UART + CRC8-MAXIM
    └── lib/                    # libs locais (vazio)
```

---

## Fluxo de execução

```
setup()
  ├── Serial.begin(115200)
  ├── motorsBegin()
  │     ├── pinMode(IN1/IN2, OUTPUT)   × 3 motores
  │     ├── pinMode(LIMIT_TOP/BOTTOM, INPUT_PULLUP)  (se pino >= 0)
  │     ├── ledcSetup(canal, freq, bits)  × 3
  │     ├── ledcAttachPin(pino, canal)    × 3
  │     └── motorsStop()
  ├── encodersBegin()
  │     ├── pinMode(A/B, INPUT_PULLUP)  × 2 encoders
  │     └── attachInterrupt(A, ISR, RISING)  × 2
  ├── Wire.begin(SDA, SCL)
  ├── Wake MPU-6050 (clear SLEEP bit)
  └── delay(50)  ← estabilização do giroscópio

loop()  — não-bloqueante, cadenciado por millis()
  ├── [sempre]  Alimenta bytes UART ao SetpointFrameDecoder
  ├── [sempre]  Verifica watchdog (SETPOINT_TIMEOUT_MS)
  ├── [100 Hz]  Lê encoders → PID → PWM motores + garfo (com check de fim-de-curso)
  └── [20 Hz]   Lê MPU-6050 → monta Sensors → envia <json>*crc\n
```

---

## Contratos UART

Fonte de verdade: [`../docs/serial-protocol.md`](../docs/serial-protocol.md).
Devem casar com `pi/app/models.py` e `pi/app/comms/protocol.py`.

| Direção    | Contrato | Conteúdo                            |
|------------|----------|-------------------------------------|
| Pi → ESP32 | (3)      | `{w_esq, w_dir, garfo}` — setpoint  |
| ESP32 → Pi | (4)      | `{enc, mpu, bms}` — sensores crus   |

Framing: `<json compacto>*<CRC8 hex minúsculo>\n`  
CRC: CRC-8/MAXIM (polinômio refletido 0x8C, init 0x00).

---

## A. MAPA COMPLETO DE PINOS — O que ligar onde

**Todos os pinos estão em `config.h` com valor `-1` (placeholder).**  
A equipe precisa definir cada um com base na fiação real do circuito.

### A.1 Motores de tração (rodas) — via L298n

Cada roda usa 3 fios do ESP32 para 1 canal do L298n:

| Constante (`config.h`)  | Conecta em              | Função                        |
|--------------------------|-------------------------|-------------------------------|
| `PIN_MOTOR_ESQ_IN1`     | L298n IN1 (motor A)     | Sentido A roda esquerda       |
| `PIN_MOTOR_ESQ_IN2`     | L298n IN2 (motor A)     | Sentido B roda esquerda       |
| `PIN_MOTOR_ESQ_PWM`     | L298n ENA (motor A)     | Velocidade roda esquerda (PWM)|
| `PIN_MOTOR_DIR_IN1`     | L298n IN3 (motor B)     | Sentido A roda direita        |
| `PIN_MOTOR_DIR_IN2`     | L298n IN4 (motor B)     | Sentido B roda direita        |
| `PIN_MOTOR_DIR_PWM`     | L298n ENB (motor B)     | Velocidade roda direita (PWM) |

**Cuidado com os jumpers do L298n:** se os jumpers de 5V estiverem no lugar,
a lógica ENA/ENB é controlada pelo jumper (sempre HIGH). **Remova os jumpers**
e conecte os fios PWM do ESP32 diretamente nos pinos ENA/ENB.

**Sentido "frente" vs "ré":** depende de como os fios do motor estão
conectados nos bornes do L298n. Se a roda gira ao contrário, **inverta os
dois fios do motor no borne** (ou troque IN1↔IN2 em `config.h`).

### A.2 Motor do garfo — via L298n (segundo canal ou segundo módulo)

| Constante (`config.h`) | Conecta em             | Função                       |
|-------------------------|------------------------|------------------------------|
| `PIN_FORK_IN1`          | L298n INx              | Sentido A garfo (subir)      |
| `PIN_FORK_IN2`          | L298n INx              | Sentido B garfo (descer)     |
| `PIN_FORK_PWM`          | L298n ENx              | Velocidade garfo (PWM)       |

**DECISÃO NECESSÁRIA:** Um L298n tem **2 canais** (A e B). As 2 rodas já usam
os 2 canais do primeiro módulo. O garfo precisa de um **segundo L298n** ou de
um driver menor (ex: L9110S, TB6612). A equipe precisa decidir.

**Sentido "subir" vs "descer":** no código, SUBIR = IN1 HIGH / IN2 LOW.
Se o garfo desce quando deveria subir, **inverta os fios do motor no borne**
ou troque `PIN_FORK_IN1` ↔ `PIN_FORK_IN2` em `config.h`.

### A.3 Chaves fim-de-curso do garfo

| Constante (`config.h`)    | Conecta em                         | Função                      |
|----------------------------|------------------------------------|-----------------------------|
| `PIN_FORK_LIMIT_TOP`      | Micro switch no topo do curso      | Bloqueia SUBIR no extremo   |
| `PIN_FORK_LIMIT_BOTTOM`   | Micro switch na base do curso      | Bloqueia DESCER no extremo  |

**Fiação dos switches (NO — Normally Open, mais comum):**

```
  ESP32 GPIO ────── [micro switch COM] ──── [micro switch NO] ──── GND
                        (terminal central)    (terminal aberto)
```

O pino é configurado como `INPUT_PULLUP`:
- Switch **não** pressionado: pino lê **HIGH** (pullup interno).
- Switch pressionado (garfo no limite): pino lê **LOW** (curto para GND).

`FORK_LIMIT_ACTIVE_LEVEL = LOW` (padrão para NO).

**Alternativa mais segura (NC — Normally Closed):**
Se usar a conexão NC do switch (normalmente fechada), um fio rompido
simula "pressionado" → motor bloqueado → falha segura. Nesse caso,
trocar `FORK_LIMIT_ACTIVE_LEVEL` para `HIGH`.

**Com pinos = -1:** os fim-de-curso ficam **desabilitados**. O motor obedece
apenas ao comando do operador sem proteção mecânica. Funcional para testes
iniciais, mas **não recomendado para uso prolongado**.

### A.4 Encoders (quadratura)

| Constante (`config.h`) | Conecta em                | Função                        |
|-------------------------|---------------------------|-------------------------------|
| `PIN_ENC_ESQ_A`         | Encoder esquerdo, fase A  | Interrupção (contagem pulsos) |
| `PIN_ENC_ESQ_B`         | Encoder esquerdo, fase B  | Leitura de sentido na ISR     |
| `PIN_ENC_DIR_A`         | Encoder direito, fase A   | Interrupção (contagem pulsos) |
| `PIN_ENC_DIR_B`         | Encoder direito, fase B   | Leitura de sentido na ISR     |

Os pinos de fase A devem suportar interrupção externa. No ESP32, **todos os
GPIOs suportam interrupção**, então qualquer pino serve.

**Motor Lego NXT 53787:** tem encoder de quadratura integrado. Os fios do
encoder saem pelo mesmo conector do motor. Consultar pinout do conector NXT.

### A.5 MPU-6050 (I2C)

| Constante (`config.h`) | Conecta em         | Função    |
|-------------------------|--------------------|-----------|
| `PIN_I2C_SDA`          | MPU-6050 pino SDA  | Dados I2C |
| `PIN_I2C_SCL`          | MPU-6050 pino SCL  | Clock I2C |

O MPU-6050 precisa de alimentação 3.3V (ou 5V se o módulo tiver regulador).
`VCC` → 3.3V, `GND` → GND, `AD0` → GND (endereço 0x68) ou VCC (0x69).

### A.6 Resumo — Total de pinos necessários

| Categoria            | Quantidade | Pinos                                  |
|----------------------|------------|----------------------------------------|
| Rodas (L298n)        | 6          | IN1/IN2/PWM × 2                       |
| Garfo (L298n)        | 3          | IN1/IN2/PWM                            |
| Fim-de-curso         | 2          | TOP, BOTTOM                            |
| Encoders             | 4          | A/B × 2                               |
| I2C (MPU)            | 2          | SDA, SCL                               |
| **Total**            | **17**     | (de ~34 GPIOs disponíveis no ESP32)    |

**GPIOs a evitar no ESP32:** GPIO 0, 2, 5, 12, 15 (strapping pins — podem
interferir no boot). GPIO 6-11 (flash SPI interno — não usar). GPIO 34-39
(somente entrada — não servem para IN1/IN2/PWM).

---

## B. CONSTANTES A CALIBRAR — Valores que precisam ser definidos

Todas em `config.h`. **Nenhuma pode ficar com placeholder em produção.**

### B.1 Bloqueadores (sem estes, nada funciona)

| Constante               | O que é                                  | Como determinar                                                           | Placeholder |
|--------------------------|------------------------------------------|---------------------------------------------------------------------------|-------------|
| `PIN_MOTOR_ESQ_*`        | 3 pinos da roda esquerda                 | Esquema de fiação → qual GPIO vai em qual pino do L298n                   | -1          |
| `PIN_MOTOR_DIR_*`        | 3 pinos da roda direita                  | Idem                                                                      | -1          |
| `PIN_FORK_*`             | 3 pinos do garfo                         | Idem                                                                      | -1          |
| `PIN_ENC_ESQ_A/B`        | 2 pinos do encoder esquerdo              | Pinout do conector NXT do motor esquerdo                                  | -1          |
| `PIN_ENC_DIR_A/B`        | 2 pinos do encoder direito               | Pinout do conector NXT do motor direito                                   | -1          |
| `PIN_I2C_SDA/SCL`        | 2 pinos I2C do MPU-6050                  | Fiação do módulo MPU → ESP32                                              | -1          |
| `ENCODER_PPR`            | Pulsos por revolução do eixo de saída    | Lego NXT 53787: verificar se é 360. Girar 1 volta e contar pulsos no serial monitor. | 0  |
| `FORK_DUTY`              | Duty cycle fixo do motor do garfo        | Teste: começar com 128 (50%), aumentar se o garfo não sobe com carga.     | 0           |

### B.2 Segurança (sem estes, funciona mas é perigoso)

| Constante                 | O que é                             | Como determinar                                                    | Placeholder |
|---------------------------|-------------------------------------|--------------------------------------------------------------------|-------------|
| `SETPOINT_TIMEOUT_MS`     | Tempo sem setpoint → estado seguro  | Serial a 20 Hz = 50 ms/msg. Sugestão: **200 ms** (4 msgs perdidos).| 0 (desabilitado) |
| `PIN_FORK_LIMIT_TOP`      | Pino do fim-de-curso superior       | Qual GPIO está conectado ao switch do topo                         | -1 (desabilitado) |
| `PIN_FORK_LIMIT_BOTTOM`   | Pino do fim-de-curso inferior       | Qual GPIO está conectado ao switch da base                         | -1 (desabilitado) |
| `FORK_LIMIT_ACTIVE_LEVEL` | Nível quando switch está pressionado| `LOW` para NO + pullup (padrão), `HIGH` para NC + pullup           | LOW         |

### B.3 Sintonia (sem estes, o robô não se move de forma controlada)

| Constante                     | O que é                         | Como determinar                                                     | Placeholder |
|-------------------------------|---------------------------------|---------------------------------------------------------------------|-------------|
| `PID_KP_ESQ` / `PID_KP_DIR`  | Ganho proporcional por roda     | Ziegler-Nichols: aumentar Kp até oscilar, Ku = Kp. Kp = 0.6×Ku.    | 0.0         |
| `PID_KI_ESQ` / `PID_KI_DIR`  | Ganho integral por roda         | Ki = 2×Kp/Tu (Tu = período de oscilação no ponto crítico).          | 0.0         |
| `PID_KD_ESQ` / `PID_KD_DIR`  | Ganho derivativo por roda       | Kd = Kp×Tu/8. Começar com 0, adicionar se houver overshoot.         | 0.0         |
| `PID_INTEGRAL_LIMIT`          | Clamp do termo integral         | Manter em 1-2× o MAX_DUTY (255 para 8 bits). Ex: 500-1000.         | 1000.0      |

### B.4 Ajuste fino (defaults razoáveis, mas confirmar)

| Constante              | O que é                    | Default  | Quando mudar                                                      |
|------------------------|----------------------------|----------|-------------------------------------------------------------------|
| `LEDC_FREQ_HZ`        | Frequência PWM             | 20000    | Se os motores fizerem ruído audível, subir para 25000+. Se o driver não aguentar, baixar. |
| `LEDC_RESOLUTION_BITS` | Resolução do duty cycle   | 8        | 8 bits = 256 níveis. Suficiente para este projeto. 10 bits = 1024, se precisar mais granularidade. |
| `MPU6050_ADDR`         | Endereço I2C do MPU        | 0x68     | Mudar para 0x69 se AD0 estiver conectado a VCC.                   |

---

## C. O QUE VAI ACONTECER — Comportamento esperado

### C.1 Boot (power on)

1. ESP32 inicia, `setup()` roda.
2. Todos os motores são zerados (`motorsStop()`).
3. MPU-6050 acorda e estabiliza (50 ms).
4. O ESP32 começa a enviar pacotes de sensores a 20 Hz pela serial,
   **mesmo sem receber setpoint**. O Pi recebe `enc: {esq:0, dir:0}`,
   dados do MPU, e `bms: null`.
5. Os motores ficam parados — `setpointValid = false`.

### C.2 Pi conecta e envia primeiro setpoint

1. O SetpointFrameDecoder decodifica o quadro.
2. `setpointValid` vira `true`.
3. No próximo tick do PID (≤ 10 ms), os motores começam a se mover
   conforme o setpoint (se os ganhos PID forem > 0).
4. O garfo responde ao campo `garfo` do setpoint.

### C.3 Operador pressiona "subir" no frontend

1. Frontend envia `garfo: "subir"` via WebSocket.
2. Pi repassa no setpoint serial: `{"w_esq":..., "w_dir":..., "garfo":"subir"}`.
3. ESP32 decodifica → `lastSetpoint.garfo = SUBIR`.
4. No tick do PID, `motorSetFork(SUBIR)` é chamado.
5. **Antes de ligar o motor:** `forkAtTopLimit()` lê o switch do topo.
   - Se **não** no limite → motor liga com FORK_DUTY no sentido "subir".
   - Se **no limite** → motor fica parado (duty 0). O garfo não se move.
6. Quando o operador solta o botão → Pi envia `garfo: "parar"` → duty 0.

### C.4 Garfo atinge o fim-de-curso durante subida

1. O garfo está subindo (FORK_DUTY no sentido "subir").
2. O garfo atinge o topo e pressiona o micro switch superior.
3. No próximo tick (~10 ms), `forkAtTopLimit()` retorna `true`.
4. `motorSetFork(SUBIR)` vê o limite → para o motor imediatamente.
5. O operador ainda está segurando "subir" no celular, mas o motor não liga.
6. O operador pode pressionar "descer" → funciona normalmente (bottom limit
   não está acionado).

### C.5 Serial com o Pi cai

1. O último setpoint fica congelado.
2. Com `SETPOINT_TIMEOUT_MS > 0`: após o timeout, `motorsStop()` é chamado.
   Todos os motores param, PID é resetado.
3. Com `SETPOINT_TIMEOUT_MS = 0` (placeholder): watchdog **desabilitado**.
   Os motores continuam com o último setpoint **para sempre**. **PERIGOSO.**
4. Para retomar: o Pi reconecta e envia um novo setpoint.

### C.6 ESP32 reinicia (reset/brown-out)

1. `setup()` roda novamente — todos os motores partem zerados.
2. Os pacotes de sensor recomeçam em 20 Hz.
3. O Pi precisa re-enviar setpoint para os motores voltarem a se mover.
4. Do lado do Pi, o `serial_loop` detecta a queda (timeout de leitura ou
   CRC inválido nos primeiros bytes de lixo do boot do ESP32) e aguarda
   a ressincronização no próximo `\n`.

---

## D. PROCEDIMENTO DE TESTES — Passo a passo

### D.1 Pré-requisito

- PlatformIO Core instalado (`pip install platformio`).
- ESP32 conectado via USB.
- Todos os pinos definidos em `config.h` (substituir -1 pelos GPIOs reais).

### D.2 Teste 0: Compilação

```bash
cd firmware
pio run
```

**Esperado:** compila sem erros. Se der erro de LEDC API (`ledcSetup` não
existe), a versão do Arduino Core é 3.x. Ver seção F.1.

### D.3 Teste 1: Serial + MPU-6050

1. Gravar no ESP32: `pio run -t upload`.
2. Abrir monitor: `pio device monitor`.
3. **Esperado:** a cada ~50 ms, aparece um quadro como:

```
{"enc":{"esq":0,"dir":0},"mpu":{"ax":0.12,"ay":-0.03,"az":9.78,"gx":0.5,"gy":-0.2,"gz":0.1,"temp_c":27.5},"bms":null}*a3
```

4. **Verificar:**
   - `az` deve ser ~9.8 m/s² (gravidade) com o MPU na horizontal.
   - `gx/gy/gz` devem ser próximos de 0 com o sensor parado.
   - Se tudo for zero: verificar fiação I2C (SDA/SCL) e endereço.
   - Se nenhum quadro aparecer: verificar baudrate (deve ser 115200).

### D.4 Teste 2: Encoders

1. Com o monitor serial aberto, girar **manualmente** a roda esquerda.
2. **Esperado:** `enc.esq` mostra um valor != 0 enquanto a roda gira.
   Positivo para um sentido, negativo para o outro.
3. Repetir com a roda direita → `enc.dir` muda.
4. **Se sempre 0:** verificar pinos A/B, ENCODER_PPR (não pode ser 0),
   e se os fios do encoder estão conectados.
5. **Se o sinal é invertido** (positivo quando deveria ser negativo):
   trocar `PIN_ENC_*_A` ↔ `PIN_ENC_*_B` em `config.h`.

### D.5 Teste 3: Fim-de-curso do garfo

1. Enviar setpoint com `garfo: "subir"` pelo Pi (ou um script de teste).
2. **Com o garfo livre (longe dos limites):** o motor deve girar.
3. **Pressionar manualmente o switch do topo:** o motor deve parar
   instantaneamente (em ≤ 10 ms, imperceptível).
4. Soltar o switch → motor retoma (se o comando ainda for "subir").
5. Repetir com "descer" e o switch da base.
6. **Se não funcionar:**
   - Verificar pinos em `config.h`.
   - Verificar `FORK_LIMIT_ACTIVE_LEVEL` (LOW vs HIGH).
   - Usar `Serial.println(digitalRead(PIN_FORK_LIMIT_TOP))` temporário
     para ver o nível lógico com e sem o switch pressionado.

### D.6 Teste 4: Direção dos motores

1. Enviar setpoint: `w_esq: 1.0, w_dir: 0.0, garfo: "parar"`.
2. **Com ganhos PID > 0**: a roda esquerda deve girar "para frente".
3. Se girar para trás: inverter IN1↔IN2 da roda esquerda em `config.h`
   (ou inverter os fios do motor no borne do L298n).
4. Repetir para roda direita e para o garfo.

### D.7 Teste 5: Sintonia do PID

1. Definir `PID_KI_ESQ = 0`, `PID_KD_ESQ = 0`.
2. Começar com `PID_KP_ESQ` baixo (ex: 10.0).
3. Enviar setpoint constante (ex: `w_esq: 3.0` rad/s).
4. Observar `enc.esq` na telemetria. Deve se aproximar de 3.0.
5. Se oscila pouco → aumentar Kp.
6. Se oscila muito → diminuir Kp. O ponto onde começa a oscilar = Ku.
7. Aplicar Ziegler-Nichols: Kp = 0.6×Ku, Ki = 2×Kp/Tu, Kd = Kp×Tu/8.
8. **Repetir para a roda direita** (os motores podem ter características
   mecânicas diferentes — ganhos independentes).

### D.8 Teste 6: Garfo com carga

1. Colocar o pallet (~100g? ~1kg? **massa em aberto**) nos garfos.
2. Enviar `garfo: "subir"`.
3. Se o garfo não sobe: **aumentar FORK_DUTY** (ex: de 128 para 200).
4. Se sobe rápido demais: diminuir FORK_DUTY.
5. Verificar que o worm gear segura a carga quando duty = 0 (parar).

### D.9 Teste 7: Integração completa com Pi

1. Subir o backend do Pi (`./scripts/run_pi.sh`).
2. Conectar o frontend no celular.
3. Modo manual: joystick → rodas se movem, garfo sobe/desce.
4. Verificar telemetria no painel.
5. Testar: desconectar o Pi (puxar USB). Com `SETPOINT_TIMEOUT_MS` > 0,
   os motores devem parar sozinhos após o timeout.

---

## E. DECISÕES PENDENTES DA EQUIPE

| #  | Decisão                                   | Impacto                                    | Sugestão                          |
|----|-------------------------------------------|--------------------------------------------|-----------------------------------|
| 1  | Quantos L298n? (1 vs 2)                   | 1 L298n = 2 canais, mas são 3 motores      | 2 módulos (rodas + garfo)         |
| 2  | Switch NO ou NC para fim-de-curso?        | NC é mais seguro (fio rompido = bloqueio)   | NC se disponível, NO se não       |
| 3  | Massa real do pallet                      | Afeta FORK_DUTY e possível subdimensionamento do motor 40rpm | Pesar e testar |
| 4  | ENCODER_PPR do Lego NXT 53787             | Sem PPR correto, a velocidade medida é errada e o PID não funciona | Medir empiricamente (ver teste D.4) |
| 5  | Faixa do giroscópio (±250 vs ±500°/s)    | ±250 pode clipar em giros rápidos do diferencial | Testar com ±250 primeiro, subir se clipar |
| 6  | Versão do platformio (pinning)            | Sem pin, uma atualização pode quebrar a API LEDC | Pinar `platform = espressif32@6.9.0` |
| 7  | BMS com saída digital?                    | Sem: `bms: null` na telemetria. Com: precisa de código de leitura | Confirmar modelo do BMS |
| 8  | SETPOINT_TIMEOUT_MS                       | 0 = watchdog desabilitado = perigoso       | 200 ms (4 mensagens a 20 Hz)     |

---

## F. PROBLEMAS CONHECIDOS E SOLUÇÕES

### F.1 Erro de compilação: `ledcSetup` não encontrado

A API LEDC mudou no Arduino-ESP32 Core 3.x (baseado em IDF 5):
- **Core 2.x:** `ledcSetup(ch, freq, bits)` + `ledcAttachPin(pin, ch)` + `ledcWrite(ch, duty)`
- **Core 3.x:** `ledcAttach(pin, freq, bits)` + `ledcWrite(pin, duty)`

**Solução:** pinar a versão do platform no `platformio.ini`:
```ini
platform = espressif32@6.9.0
```
Ou migrar o código em `motors.cpp` para a API 3.x.

### F.2 MPU-6050 retorna tudo zero

- Verificar VCC do módulo (3.3V ou 5V conforme o módulo).
- Verificar SDA/SCL nos pinos corretos.
- Verificar AD0 (GND = 0x68, VCC = 0x69). Ajustar `MPU6050_ADDR` se necessário.
- Rodar I2C scanner para confirmar que o MPU responde.

### F.3 Motor gira na direção errada

- Inverter os 2 fios do motor no borne do L298n, **ou**
- Trocar `PIN_*_IN1` ↔ `PIN_*_IN2` em `config.h`.

### F.4 Encoder sempre lê 0 mesmo com ENCODER_PPR definido

- Fase A pode não estar gerando interrupção. Testar com `digitalRead` direto.
- Verificar que os pinos não são GPIO 6-11 (flash SPI, inutilizáveis).
- Verificar se o encoder precisa de alimentação separada (5V no NXT).

### F.5 PID oscila sem convergir

- Ki muito alto → reduzir.
- Kd muito alto → reduzir ou remover.
- Tentar PID "P-only" primeiro (Ki=0, Kd=0) e ir adicionando.
- Verificar se ENCODER_PPR está correto (PPR errado = medição errada = ganhos efetivos errados).

### F.6 Garfo não segura a carga ao parar

- O motor JGY-370-12V com worm gear deveria travar mecanicamente.
- Se a carga desce: o torque do motor pode ser insuficiente (versão 40rpm com carga real pesada).
- Testar com a versão de 23rpm (mais torque) se necessário.

---

## G. DÚVIDAS EM ABERTO (equipe precisa investigar)

1. **O encoder do NXT 53787 precisa de 5V?** O ESP32 opera em 3.3V.
   Se o encoder gera sinais de 5V, precisa de divisor de tensão ou
   level shifter nos pinos A/B (3.3V tolerante no ESP32 = depende do módulo).

2. **O MPU-6050 está bem fixo no chassi?** Vibração excessiva gera ruído
   no acelerômetro que o Kalman do Pi terá dificuldade em filtrar.

3. **A câmera e o garfo estão alinhados?** O offset câmera→garfo
   (parâmetro do Pi, não do firmware) afeta a precisão do modo autônomo.
   Documentar a distância X/Y/Z entre o centro óptico da câmera e a
   ponta dos garfos.

4. **Corrente de pico dos motores NXT sob carga?** O L298n aguenta
   2A por canal (3A pico). Se os motores puxarem mais que isso ao
   arrancar com carga, o L298n pode entrar em proteção térmica.

5. **Debouncing dos fim-de-curso:** micro switches podem gerar bounce
   de ~1-5 ms. No contexto atual (motor worm gear lento, check a 100 Hz),
   o bounce é irrelevante. Se houver problemas, adicionar debounce por
   software (filtro de N leituras consecutivas).

---

## Como compilar / gravar

```bash
cd firmware
pio run                 # compila
pio run -t upload       # grava no ESP32
pio device monitor      # monitor serial @115200
# ou: ../scripts/flash_firmware.sh
```

## Dependências

- **ArduinoJson v7** — serialização/deserialização dos contratos JSON.
- **Wire** (builtin) — comunicação I2C com MPU-6050.
- Nenhuma dependência externa fora do especificado na Seção 8 da AGENTS.md.
