/**
 * protocol.h - Espelho C++ dos contratos UART Pi <-> ESP32.
 *
 * Fonte unica de verdade: docs/serial-protocol.md. Este arquivo cobre:
 *  - Contrato (3): setpoint recebido do Pi.
 *  - Contrato (4): sensores enviados ao Pi.
 *
 * Framing serial:
 *   <json compacto>*<CRC8 em 2 digitos hex minusculos>\n
 *
 * CRC-8/MAXIM (Dallas/1-Wire):
 *  - Polinomio normal 0x31, refletido 0x8C
 *  - Init 0x00, RefIn true, RefOut true, XorOut 0x00
 *
 * Na recepcao, o decoder ressincroniza no '\n' e descarta o quadro inteiro em
 * caso de CRC, JSON ou schema invalido.
 */
#pragma once

#include <Arduino.h>

enum class ForkCommand { SUBIR, DESCER, PARAR };

// Contrato (3) - Pi -> ESP32. Velocidades sempre em rad/s, nunca rpm.
struct Setpoint {
  float w_esq = 0.0f;              // rad/s (alvo roda esquerda)
  float w_dir = 0.0f;              // rad/s (alvo roda direita)
  ForkCommand garfo = ForkCommand::PARAR;
};

// Contrato (4) - ESP32 -> Pi. O MPU envia dados crus; Kalman roda no Pi.
struct Sensors {
  float enc_esq = 0.0f;     // rad/s (medido)
  float enc_dir = 0.0f;     // rad/s (medido)
  float ax = 0.0f;          // m/s^2 (cru)
  float ay = 0.0f;          // m/s^2 (cru)
  float az = 0.0f;          // m/s^2 (cru)
  float gx = 0.0f;          // graus/s (cru)
  float gy = 0.0f;          // graus/s (cru)
  float gz = 0.0f;          // graus/s (cru)
  float mpu_temp_c = 0.0f;  // graus C

  bool has_bms = false;       // false -> "bms": null
  float bms_cel = 0.0f;       // TODO(equipe): confirmar unidade de cel (V?)
  float bms_i_a = 0.0f;       // A
  float bms_temp_c = 0.0f;    // graus C
};

const char* forkCommandToString(ForkCommand command);
bool forkCommandFromString(const char* value, ForkCommand& out);

uint8_t crc8(const uint8_t* data, size_t len);

/**
 * Valida e desserializa um quadro de setpoint ja separado por '\n'.
 *
 * Args:
 *   frame: bytes no formato <json>*<crc8hex>, com ou sem '\n'/'\r' final.
 *   len: numero de bytes em frame.
 *   out: setpoint preenchido apenas quando a funcao retorna true.
 *
 * Returns:
 *   true se CRC, JSON e campos obrigatorios forem validos; false se o quadro
 *   deve ser descartado.
 */
bool decodeSetpoint(const char* frame, size_t len, Setpoint& out);

/**
 * Serializa sensores no quadro <json>*<crc8hex>\n.
 *
 * Args:
 *   sensors: contrato (4), com rodas em rad/s, MPU cru e BMS opcional.
 *   out: buffer do chamador.
 *   out_size: tamanho do buffer.
 *
 * Returns:
 *   Numero de bytes escritos, incluindo '\n'. Retorna 0 se o buffer nao couber.
 */
size_t encodeSensors(const Sensors& sensors, char* out, size_t out_size);

/**
 * Decoder incremental para a UART.
 *
 * O chamador fornece o buffer para nao fixar aqui um tamanho arbitrario de
 * quadro. Quando um '\n' fecha o quadro, push() valida o CRC e preenche `out`
 * somente se o setpoint for valido. Quadros invalidos e bytes apos overflow sao
 * descartados ate a ressincronizacao no proximo '\n'.
 */
class SetpointFrameDecoder {
 public:
  SetpointFrameDecoder(char* buffer, size_t capacity);

  bool push(uint8_t byte, Setpoint& out);
  void reset();
  size_t pending() const;
  bool dropping() const;

 private:
  char* buffer_;
  size_t capacity_;
  size_t len_;
  bool dropping_;
};
