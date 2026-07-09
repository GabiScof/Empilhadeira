/**
 * motors.h — Acionamento dos motores (PWM via LEDC -> driver L298n).
 *
 * Rodas: PWM proporcional ao esforco do PID.
 * Garfo: duty fixo (FORK_DUTY) enquanto pressionado; duty 0 ao soltar
 * (worm gear impede backdrive).
 *
 * Fim-de-curso do garfo: corte local nos extremos (nao depende do Pi).
 * Pinos em config.h; atualmente desabilitados (-1).
 */
#pragma once

#include "protocol.h"

void motorsBegin();

void motorSetWheelEsq(float u);
void motorSetWheelDir(float u);

void motorSetFork(ForkCommand cmd);

void motorsStop();

bool forkAtTopLimit();
bool forkAtBottomLimit();
