/**
 * protocol.cpp — Implementacao do framing JSON+CRC8+\n (stub).
 * [ref: Secao 6 e 7 da AGENTS.md]
 */
#include "protocol.h"

#include <ArduinoJson.h>

uint8_t crc8(const uint8_t* data, size_t len) {
  // TODO(equipe): implementar CRC-8 (polinomio/init identicos ao Pi).
  (void)data;
  (void)len;
  return 0;
}

bool decodeSetpoint(const char* frame, size_t len, Setpoint& out) {
  // TODO: separar payload e CRC pelo '*', validar CRC, parsear JSON (ArduinoJson)
  // e preencher `out`. Retornar false em CRC invalido / JSON malformado.
  (void)frame;
  (void)len;
  (void)out;
  return false;
}

size_t encodeSensors(const Sensors& sensors, char* out, size_t out_size) {
  // TODO: serializar `sensors` em JSON compacto, anexar '*' + crc8 hex + '\n'.
  (void)sensors;
  (void)out;
  (void)out_size;
  return 0;
}
