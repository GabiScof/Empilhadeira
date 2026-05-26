/**
 * main.cpp — Loop principal do ESP32 (baixo nivel, tempo real).
 *
 * Duas cadencias:
 *  - Serial a 20 Hz: recebe setpoint (contrato 3) do Pi, envia sensores (contrato 4).
 *  - PID a ~100 Hz: por roda, segue o ultimo setpoint valido.
 *
 * Estado seguro: se nenhum setpoint chegar em SETPOINT_TIMEOUT_MS, zera os motores.
 * [ref: Secao 2 e 7 da AGENTS.md]
 */
#include <Arduino.h>

#include "config.h"
#include "encoders.h"
#include "motors.h"
#include "pid.h"
#include "protocol.h"

// PID por roda (ganhos em config.h).
static Pid pidEsq(PID_KP_ESQ, PID_KI_ESQ, PID_KD_ESQ);
static Pid pidDir(PID_KP_DIR, PID_KI_DIR, PID_KD_DIR);

void setup() {
  // TODO: Serial.begin(SERIAL_BAUDRATE); motorsBegin(); encodersBegin(); init MPU (Wire).
}

void loop() {
  // TODO: cadenciar PID (~100 Hz) e troca serial (20 Hz) com millis();
  //       ler setpoint -> aplicar; ler encoders/MPU -> enviar sensores;
  //       watchdog SETPOINT_TIMEOUT_MS -> motorsStop().
}
