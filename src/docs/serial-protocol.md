# Protocolo de comunicação — FONTE ÚNICA DE VERDADE

> Este documento define os **4 contratos** que ligam as três camadas do sistema.
> As cinco frentes de trabalho só integram se estes contratos forem respeitados ao
> pé da letra. Qualquer mudança aqui exige espelhar simultaneamente em:
> - `pi/app/models.py` (Pydantic)
> - `firmware/src/protocol.h` / `protocol.cpp` (struct + ArduinoJson)
> - `frontend/src/types/contracts.ts` (tipos TypeScript)
>
> [ref: Seção 6 da AGENTS.md]

---

## Convenções fixas (valem para todos os contratos)

| Grandeza            | Unidade        | Observação                                   |
|---------------------|----------------|----------------------------------------------|
| Velocidade angular  | **rad/s**      | Nunca rpm. Vale para rodas (`w_esq`, `w_dir`).|
| Ângulo              | **graus (°)**  | roll, pitch, yaw.                            |
| Distância           | **cm**         | `z_cm`, `x_cm`, `Zref`.                       |
| Corrente            | **A** (ampère) | `i_a`.                                        |
| Temperatura         | **°C**         | `temp_c`.                                     |
| Timestamp           | **ms** (int)   | `ts_ms`, relógio do emissor.                 |

### Camadas e transporte

```
Frontend (celular)  --(1) comando-------->  Raspberry Pi
Frontend (celular)  <--(2) telemetria-----  Raspberry Pi      [WebSocket / Wi-Fi]
Raspberry Pi        --(3) setpoint-------->  ESP32
Raspberry Pi        <--(4) sensores-------  ESP32             [UART USB, 115200, 20 Hz]
```

- **Frontend ↔ Pi:** WebSocket full-duplex sobre Wi-Fi local. Payload = JSON puro
  (sem CRC; o WebSocket já garante integridade).
- **Pi ↔ ESP32:** UART em USB, **115200 baud**, taxa de troca **20 Hz**. Cada
  mensagem é emoldurada (ver framing abaixo).

---

## Framing serial (somente UART, contratos 3 e 4)

```
<json compacto>*<CRC8 em 2 dígitos hex><\n>
```

- `<json compacto>`: JSON sem espaços supérfluos.
- `*`: separador literal entre payload e checksum.
- `<CRC8>`: CRC-8 do payload JSON (bytes UTF-8 antes do `*`), 2 dígitos hex minúsculos.
- `\n`: terminador de quadro; o receptor **ressincroniza no `\n`** e descarta o
  quadro inteiro se o CRC não bater.

Exemplo (ilustrativo, CRC fictício):

```
{"w_esq":1.5,"w_dir":1.5,"garfo":"parar"}*a3\n
```

> O algoritmo de CRC8 deve ser idêntico nos dois lados: CRC-8/MAXIM
> (Dallas/1-Wire), polinômio normal `0x31` / refletido `0x8C`, init `0x00`,
> RefIn/RefOut true e XorOut `0x00`.

---

## Contrato (1) — Frontend → Pi · comando (WebSocket)

```jsonc
{
  "modo": "MANUAL",                   // "MANUAL" | "AUTOMATICO" | "PARADO"
  "joystick": { "x": 0.0, "y": 0.0 }, // float [-1, 1]; só vale em MANUAL
  "garfo": "parar",                   // "subir" | "descer" | "parar"
  "ts_ms": 0                          // int, timestamp do cliente
}
```

| Campo         | Tipo   | Unidade | Faixa        | Obrig. | Notas                                  |
|---------------|--------|---------|--------------|--------|----------------------------------------|
| `modo`        | enum   | —       | ver acima    | sim    | Estado desejado pelo operador.         |
| `joystick.x`  | float  | —       | [-1, 1]      | sim    | Giro (ω). Ignorado fora de MANUAL.     |
| `joystick.y`  | float  | —       | [-1, 1]      | sim    | Avanço (v). Ignorado fora de MANUAL.   |
| `garfo`       | enum   | —       | subir/descer/parar | sim | Canal independente; vale nos dois modos. **Sempre manual** — ver nota abaixo.|
| `ts_ms`       | int    | ms      | ≥ 0          | sim    | Usado para watchdog de comando no Pi.  |

> **Garfo:** o campo `garfo` é o **único** canal de comando do garfo em todo o
> sistema. Não existe variante autônoma no WebSocket nem extensão prevista no
> protocolo. Em missão pick-and-place, o operador usa este mesmo campo durante
> AT_PICK / AT_PLACE.

---

## Contrato (2) — Pi → Frontend · telemetria @20 Hz (WebSocket)

```jsonc
{
  "estado": "MANUAL",                 // estado atual da máquina de estados
  "rodas": { "esq": 0.0, "dir": 0.0 },             // rad/s (medido)
  "imu":   { "roll": 0.0, "pitch": 0.0 },          // graus (filtrado por Kalman)
  "visao": {
    "detectado": false,               // bool
    "id": null,                       // int | null
    "z_cm": null,                     // float | null
    "x_cm": null,                     // float | null
    "pitch_deg": null                 // float | null
  },
  "bateria": { "cel": null, "i_a": null, "temp_c": null }, // null se BMS sem leitura digital
  "ts_ms": 0
}
```

| Campo               | Tipo        | Unidade | Faixa     | Obrig. | Notas                                  |
|---------------------|-------------|---------|-----------|--------|----------------------------------------|
| `estado`            | enum        | —       | MANUAL/AUTOMATICO/PARADO | sim | Estado real, não o pedido.   |
| `rodas.esq`         | float       | rad/s   | —         | sim    | Velocidade medida da roda esquerda.    |
| `rodas.dir`         | float       | rad/s   | —         | sim    | Velocidade medida da roda direita.     |
| `imu.roll`          | float       | graus   | —         | sim    | Saída do Kalman (no Pi).               |
| `imu.pitch`         | float       | graus   | —         | sim    | Saída do Kalman (no Pi).               |
| `visao.detectado`   | bool        | —       | —         | sim    | Há tag no FOV?                         |
| `visao.id`          | int \| null | —       | —         | sim    | ID da AprilTag ou null.                |
| `visao.z_cm`        | float\|null | cm      | —         | sim    | Distância ao alvo ou null.             |
| `visao.x_cm`        | float\|null | cm      | —         | sim    | Deslocamento lateral ou null.          |
| `visao.pitch_deg`   | float\|null | graus   | —         | sim    | Orientação relativa da tag ou null.    |
| `bateria.cel`       | float\|null | V?      | —         | sim    | Tensão de célula; null sem leitura.    |
| `bateria.i_a`       | float\|null | A       | —         | sim    | Corrente; null sem leitura.            |
| `bateria.temp_c`    | float\|null | °C      | —         | sim    | Temperatura; null sem leitura.         |
| `ts_ms`             | int         | ms      | ≥ 0       | sim    | Relógio do Pi.                         |

> `TODO(equipe)`: confirmar a unidade de `bateria.cel` (tensão de célula em V?).

---

## Contrato (3) — Pi → ESP32 · setpoint (UART, emoldurado)

```jsonc
{
  "w_esq": 0.0,        // rad/s (alvo)
  "w_dir": 0.0,        // rad/s (alvo)
  "garfo": "parar"     // "subir" | "descer" | "parar"
}
```

| Campo    | Tipo  | Unidade | Faixa | Obrig. | Notas                                |
|----------|-------|---------|-------|--------|--------------------------------------|
| `w_esq`  | float | rad/s   | —     | sim    | Setpoint da roda esquerda (alvo PID).|
| `w_dir`  | float | rad/s   | —     | sim    | Setpoint da roda direita (alvo PID). |
| `garfo`  | enum  | —       | subir/descer/parar | sim | Repassado direto ao motor do garfo.|

> **Garfo manual — sem atuação autônoma.** O campo `garfo` permanece no canal
> manual existente (`subir` / `descer` / `parar`), repassado do frontend ao Pi
> e do Pi ao ESP32 sem transformação. **Não há campo adicional** no protocolo
> serial para controle autônomo do garfo — nem em missão pick-and-place, nem em
> modo AUTOMATICO. Nos estados AT_PICK e AT_PLACE da missão, o operador aciona
> a garra pelo mesmo botão da UI; a missão só retoma via `POST /mission/continue`
> (WebSocket/API), não por comando serial dedicado. O fim-de-curso é tratado
> localmente no ESP32 (~100 Hz) e não altera o framing JSON.

> Se o ESP32 não receber setpoint novo, mantém o último válido por um intervalo
> curto (`SETPOINT_TIMEOUT_MS`, `TODO(equipe)`) e depois entra em estado seguro
> (motores zerados).

---

## Contrato (4) — ESP32 → Pi · sensores (UART, emoldurado)

```jsonc
{
  "enc": { "esq": 0.0, "dir": 0.0 },        // rad/s (medido)
  "mpu": {
    "ax": 0.0, "ay": 0.0, "az": 0.0,        // m/s² (cru)
    "gx": 0.0, "gy": 0.0, "gz": 0.0,        // graus/s (cru)
    "temp_c": 0.0                           // °C
  },
  "bms": null                               // mesmo formato de "bateria", ou null
}
```

| Campo        | Tipo        | Unidade | Obrig. | Notas                                       |
|--------------|-------------|---------|--------|---------------------------------------------|
| `enc.esq`    | float       | rad/s   | sim    | Velocidade medida pelo encoder esquerdo.    |
| `enc.dir`    | float       | rad/s   | sim    | Velocidade medida pelo encoder direito.     |
| `mpu.ax/ay/az` | float     | m/s²    | sim    | Aceleração **crua** (filtragem é no Pi).    |
| `mpu.gx/gy/gz` | float     | graus/s | sim    | Velocidade angular **crua**.                |
| `mpu.temp_c` | float       | °C      | sim    | Temperatura do MPU-6050.                    |
| `bms`        | obj \| null | —       | sim    | `{cel, i_a, temp_c}` como em `bateria`, ou null.|

> O ESP32 envia **dados crus** do MPU-6050. A fusão (Kalman → roll/pitch) acontece
> no Pi (`pi/app/control/kalman.py`). [ref: Seção 7]
