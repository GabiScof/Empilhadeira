/**
 * config.h — Pinos, taxas e ganhos do firmware do ESP32.
 *
 * Centraliza todos os parâmetros de baixo nível. Os valores marcados com
 * TODO(equipe) são placeholders: a equipe ainda não fechou o número real
 * (Seção 3 da AGENTS.md). NÃO trate placeholder como verdade.
 *
 * [ref: Seção 3 da AGENTS.md]
 */
#pragma once

#include <stdint.h>

// ---------------------------------------------------------------------------
// Serial (UART Pi <-> ESP32)
// ---------------------------------------------------------------------------
constexpr unsigned long SERIAL_BAUDRATE = 115200;  // decisao fechada (Secao 2)
constexpr float SERIAL_HZ = 20.0f;                 // taxa de troca de mensagens

// Timeout "manter ultimo setpoint": se nao chegar setpoint novo nesse intervalo,
// o ESP32 entra em estado seguro (motores zerados). [ref: Secao 4 e 7]
constexpr unsigned long SETPOINT_TIMEOUT_MS = 500;  // TODO(equipe): definir.

// ---------------------------------------------------------------------------
// Malha de controle
// ---------------------------------------------------------------------------
constexpr float PID_HZ = 100.0f;  // PID por roda a ~100 Hz (decisao fechada)

// Ganhos PID por roda. Sintonia inicial por Ziegler-Nichols, depois empirica.
// TODO(equipe): confirmar todos os ganhos abaixo.
constexpr float PID_KP_ESQ = 0.0f;  // TODO(equipe)
constexpr float PID_KI_ESQ = 0.0f;  // TODO(equipe)
constexpr float PID_KD_ESQ = 0.0f;  // TODO(equipe)
constexpr float PID_KP_DIR = 0.0f;  // TODO(equipe)
constexpr float PID_KI_DIR = 0.0f;  // TODO(equipe)
constexpr float PID_KD_DIR = 0.0f;  // TODO(equipe)

// Limite do termo integral (anti-windup por clamping). Evita que a integral
// cresca indefinidamente quando o erro persiste e a saida ja esta saturada.
// TODO(equipe): ajustar conforme sintonia dos ganhos e resolucao LEDC.
constexpr float PID_INTEGRAL_LIMIT = 1000.0f;  // TODO(equipe)

// ---------------------------------------------------------------------------
// Pinos (motores via L298n, PWM por LEDC) — TODO(equipe): confirmar fiacao
// ---------------------------------------------------------------------------
constexpr int PIN_MOTOR_ESQ_IN1 = -1;  // TODO(equipe)
constexpr int PIN_MOTOR_ESQ_IN2 = -1;  // TODO(equipe)
constexpr int PIN_MOTOR_ESQ_PWM = -1;  // TODO(equipe)
constexpr int PIN_MOTOR_DIR_IN1 = -1;  // TODO(equipe)
constexpr int PIN_MOTOR_DIR_IN2 = -1;  // TODO(equipe)
constexpr int PIN_MOTOR_DIR_PWM = -1;  // TODO(equipe)

// Motor do garfo (PWM de duty fixo enquanto pressionado).
constexpr int PIN_FORK_IN1 = -1;  // TODO(equipe)
constexpr int PIN_FORK_IN2 = -1;  // TODO(equipe)
constexpr int PIN_FORK_PWM = -1;  // TODO(equipe)
constexpr int FORK_DUTY = 0;      // TODO(equipe): duty fixo do garfo (0-255 ou resolucao LEDC).

// Chaves fim-de-curso do garfo [ref: Secao 5.2 do relatorio].
// Micro switches instalados nas posicoes extremas (topo e base) do garfo.
// Quando o garfo atinge o limite, o switch correspondente e acionado e o
// firmware bloqueia o motor NAQUELE SENTIDO — localmente, sem depender do Pi.
// O sentido oposto continua liberado.
//
// Fiacao recomendada (NO = Normally Open):
//   ESP32_PIN --- [switch NO] --- GND
//   Pino configurado como INPUT_PULLUP.
//   - Garfo NAO no limite: pino le HIGH (pullup).
//   - Garfo NO limite (switch pressionado): pino le LOW (conectado a GND).
//
// Se usar switch NC (Normally Closed, mais seguro — fio rompido = bloqueio):
//   trocar FORK_LIMIT_ACTIVE_LEVEL para HIGH.
//
// Com pino = -1 (placeholder), o fim-de-curso fica DESABILITADO (como se nao
// estivesse instalado). O motor obedece so ao comando do operador.
constexpr int PIN_FORK_LIMIT_TOP    = -1;  // TODO(equipe): pino do fim-de-curso superior (garfo no topo)
constexpr int PIN_FORK_LIMIT_BOTTOM = -1;  // TODO(equipe): pino do fim-de-curso inferior (garfo embaixo)

// Nivel logico quando o fim-de-curso esta ACIONADO (garfo na posicao extrema).
// LOW = switch NO com INPUT_PULLUP (padrao). HIGH = switch NC com INPUT_PULLUP.
constexpr int FORK_LIMIT_ACTIVE_LEVEL = LOW;  // TODO(equipe): confirmar tipo do switch

// Encoders (leitura por interrupcao).
constexpr int PIN_ENC_ESQ_A = -1;  // TODO(equipe)
constexpr int PIN_ENC_ESQ_B = -1;  // TODO(equipe)
constexpr int PIN_ENC_DIR_A = -1;  // TODO(equipe)
constexpr int PIN_ENC_DIR_B = -1;  // TODO(equipe)
constexpr int ENCODER_PPR = 0;     // TODO(equipe): pulsos por revolucao (com reducao).

// MPU-6050 (I2C via Wire).
constexpr int PIN_I2C_SDA = -1;  // TODO(equipe)
constexpr int PIN_I2C_SCL = -1;  // TODO(equipe)

// Endereco I2C do MPU-6050. Padrao 0x68 (AD0=LOW). Se AD0=HIGH, usar 0x69.
constexpr uint8_t MPU6050_ADDR = 0x68;

// ---------------------------------------------------------------------------
// LEDC (PWM)
// ---------------------------------------------------------------------------
constexpr int LEDC_FREQ_HZ = 20000;     // TODO(equipe): confirmar frequencia PWM.
constexpr int LEDC_RESOLUTION_BITS = 8;  // TODO(equipe): confirmar resolucao.

// Canais LEDC do ESP32 (0-15). Cada motor usa um canal independente.
// ESP32 possui 2 grupos (alta/baixa velocidade) com 8 canais cada.
constexpr int LEDC_CH_ESQ  = 0;  // Canal para roda esquerda
constexpr int LEDC_CH_DIR  = 1;  // Canal para roda direita
constexpr int LEDC_CH_FORK = 2;  // Canal para motor do garfo
