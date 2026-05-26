/**
 * encoders.h — Leitura dos encoders das rodas por interrupcao.
 *
 * Conta pulsos por interrupcao e converte para velocidade angular (rad/s) usando
 * ENCODER_PPR (config.h). A premissa de "sem escorregamento" da cinematica vive no
 * Pi; aqui so medimos a rotacao da roda. [ref: Secao 4]
 */
#pragma once

// Configura pinos e anexa as rotinas de interrupcao (ISR) dos encoders.
void encodersBegin();

// Velocidade angular medida de cada roda, em rad/s.
// `dt_s` = intervalo desde a ultima leitura (para derivar dos pulsos).
float encoderReadEsq(float dt_s);
float encoderReadDir(float dt_s);
