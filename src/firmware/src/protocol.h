/**
 * protocol.h — Espelho C++ dos contratos UART (Setpoint in / Sensors out).
 *
 * Fonte unica de verdade: docs/serial-protocol.md. Deve casar com
 * pi/app/models.py (Pydantic) e pi/app/comms/protocol.py.
 *
 * Framing: <json compacto>*<CRC8 em 2 digitos hex>\n
 * Na recepcao, ressincroniza no \n e descarta quadro com CRC invalido.
 *
 * [ref: Secao 6 e 7 da AGENTS.md]
 */
#pragma once

#include <Arduino.h>

// Comando do garfo (espelha ForkCommand do contrato).
enum class ForkCommand { SUBIR, DESCER, PARAR };

// Contrato (3) — Pi -> ESP32 · setpoint (recebido).
struct Setpoint {
  float w_esq;        // rad/s (alvo roda esquerda)
  float w_dir;        // rad/s (alvo roda direita)
  ForkCommand garfo;  // comando do garfo
};

// Contrato (4) — ESP32 -> Pi · sensores (enviado).
struct Sensors {
  float enc_esq;  // rad/s (medido)
  float enc_dir;  // rad/s (medido)
  float ax, ay, az;     // m/s^2 (cru)
  float gx, gy, gz;     // graus/s (cru)
  float mpu_temp_c;     // graus C
  bool has_bms;         // false -> bms = null no JSON
  float bms_cel, bms_i_a, bms_temp_c;  // validos se has_bms
};

// TODO(equipe): fixar polinomio e init do CRC-8 (identicos ao pi/app/comms/crc8.py).
uint8_t crc8(const uint8_t* data, size_t len);

/**
 * Desserializa um quadro de setpoint recebido (sem o \n terminador).
 * Valida o CRC; retorna false se o CRC nao bater ou o JSON for invalido.
 */
bool decodeSetpoint(const char* frame, size_t len, Setpoint& out);

/**
 * Serializa o pacote de sensores no quadro <json>*<crc8hex>\n.
 * Escreve em `out` (buffer do chamador) e retorna o numero de bytes escritos.
 */
size_t encodeSensors(const Sensors& sensors, char* out, size_t out_size);
