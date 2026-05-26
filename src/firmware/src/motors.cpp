/**
 * motors.cpp — Implementacao do acionamento dos motores (stub).
 * [ref: Secao 7 da AGENTS.md]
 */
#include "motors.h"

#include "config.h"

void motorsBegin() {
  // TODO: configurar LEDC (freq/resolucao), anexar pinos PWM, setar pinos de direcao.
}

void motorSetWheelEsq(float u) {
  // TODO: mapear u -> sentido (IN1/IN2) + duty (PWM) da roda esquerda.
  (void)u;
}

void motorSetWheelDir(float u) {
  // TODO: mapear u -> sentido (IN1/IN2) + duty (PWM) da roda direita.
  (void)u;
}

void motorSetFork(ForkCommand cmd) {
  // TODO: SUBIR/DESCER -> duty fixo FORK_DUTY no sentido correto; PARAR -> duty 0.
  (void)cmd;
}

void motorsStop() {
  // TODO: zerar duty das rodas (estado seguro).
}
