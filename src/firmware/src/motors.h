/**
 * motors.h — Acionamento dos motores (PWM via LEDC -> driver L298n).
 *
 * Rodas: PWM proporcional ao esforco do PID (com sinal -> sentido).
 * Garfo: PWM de duty fixo (FORK_DUTY) enquanto o botao estiver pressionado; ao
 * soltar, duty 0 (a reducao do motor segura a carga). [ref: Secao 7]
 */
#pragma once

#include "protocol.h"

// Inicializa os canais LEDC e os pinos de direcao (ver config.h).
void motorsBegin();

// Aplica esforco de controle a uma roda. `u` normalizado (sinal = sentido).
void motorSetWheelEsq(float u);
void motorSetWheelDir(float u);

// Aciona o motor do garfo conforme o comando (duty fixo ou parado).
void motorSetFork(ForkCommand cmd);

// Estado seguro: zera as rodas (garfo permanece como esta / parado).
void motorsStop();
