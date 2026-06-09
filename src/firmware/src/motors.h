/**
 * motors.h — Acionamento dos motores (PWM via LEDC -> driver L298n).
 *
 * Rodas: PWM proporcional ao esforco do PID (com sinal -> sentido).
 * Garfo: PWM de duty fixo (FORK_DUTY) enquanto o botao estiver pressionado; ao
 * soltar, duty 0 (a reducao do motor segura a carga). [ref: Secao 7]
 *
 * Fim-de-curso do garfo [ref: Secao 5.2 do relatorio]:
 *   Duas chaves (topo e base) impedem o motor de forcar a estrutura nos
 *   extremos. O corte e LOCAL (nao depende do Pi) — resposta imediata.
 *   Se o garfo esta no topo e o comando e SUBIR, o motor nao liga.
 *   Se o garfo esta na base e o comando e DESCER, o motor nao liga.
 *   O sentido oposto continua liberado normalmente.
 *   Pinos configurados: GPIO 5 (topo), GPIO 15 (base). Setar -1 para desabilitar.
 */
#pragma once

#include "protocol.h"

// Inicializa os canais LEDC, pinos de direcao e fim-de-curso (ver config.h).
void motorsBegin();

// Aplica esforco de controle a uma roda. `u` normalizado (sinal = sentido).
void motorSetWheelEsq(float u);
void motorSetWheelDir(float u);

// Aciona o motor do garfo conforme o comando (duty fixo ou parado).
// Respeita os fim-de-curso: bloqueia SUBIR se no topo, DESCER se na base.
void motorSetFork(ForkCommand cmd);

// Estado seguro: zera as rodas e para o garfo.
void motorsStop();

// Consulta o estado dos fim-de-curso do garfo.
// Retorna true se o switch esta acionado (garfo na posicao extrema).
// Retorna false se o pino e -1 (desabilitado) ou se o switch nao esta acionado.
bool forkAtTopLimit();
bool forkAtBottomLimit();
