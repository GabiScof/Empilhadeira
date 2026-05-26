/**
 * encoders.cpp — Implementacao da leitura de encoders (stub).
 * [ref: Secao 4 da AGENTS.md]
 */
#include "encoders.h"

#include "config.h"

void encodersBegin() {
  // TODO: pinMode + attachInterrupt nas fases A/B de cada encoder; zerar contadores.
}

float encoderReadEsq(float dt_s) {
  // TODO: converter pulsos acumulados em rad/s usando ENCODER_PPR e dt_s.
  (void)dt_s;
  return 0.0f;
}

float encoderReadDir(float dt_s) {
  // TODO: idem para a roda direita.
  (void)dt_s;
  return 0.0f;
}
