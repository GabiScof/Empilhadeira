/**
 * encoders.h — Leitura dos encoders das rodas por interrupcao.
 *
 * Conta pulsos por ISR e converte para rad/s via ENCODER_PPR (config.h).
 */
#pragma once

void encodersBegin();

float encoderReadEsq(float dt_s);
float encoderReadDir(float dt_s);
