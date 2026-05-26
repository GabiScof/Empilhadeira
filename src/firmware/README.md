# Firmware do ESP32 (baixo nível, tempo real)

Firmware em **C++ (framework Arduino)**, build com **PlatformIO**. Roda o controle
de tempo real: PID por roda a ~100 Hz, leitura de encoders/MPU e acionamento dos
motores via PWM (LEDC) → driver L298n.

> ⚠️ **Fase de scaffolding.** Toda a lógica está marcada com `// TODO`. Nada de
> PID/encoder/protocolo/CRC implementado ainda.

## Cadências

- **Serial @20 Hz** — recebe setpoint (contrato 3) do Pi, envia sensores (contrato 4),
  emoldurado em `<json>*<crc8hex>\n`.
- **PID @~100 Hz** — por roda, segue o último setpoint válido.
- **Estado seguro** — sem setpoint novo por `SETPOINT_TIMEOUT_MS`, zera os motores.

## Estrutura

```
src/
├── main.cpp        # loop: serial 20 Hz + PID 100 Hz
├── config.h        # pinos, baudrate, ganhos (placeholders TODO(equipe))
├── pid.h/.cpp      # PID por roda
├── motors.h/.cpp   # PWM (LEDC) -> L298n, garfo duty fixo
├── encoders.h/.cpp # leitura por interrupção
├── protocol.h/.cpp # espelho C++ dos contratos UART + CRC8
└── lib/            # libs locais (vazio)
platformio.ini      # board = esp32dev, framework = arduino, ArduinoJson
```

## Como compilar / gravar

```bash
# requer PlatformIO Core (pio)
cd firmware
pio run                 # compila (deve buildar mesmo com stubs)
pio run -t upload       # grava no ESP32
pio device monitor      # monitor serial @115200
# ou: ../scripts/flash_firmware.sh
```

Os contratos UART seguem `../docs/serial-protocol.md` (fonte de verdade) e devem
casar com `pi/app/models.py` e `pi/app/comms/protocol.py`.
