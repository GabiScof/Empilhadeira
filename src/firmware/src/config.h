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

// Encoders (leitura por interrupcao).
constexpr int PIN_ENC_ESQ_A = -1;  // TODO(equipe)
constexpr int PIN_ENC_ESQ_B = -1;  // TODO(equipe)
constexpr int PIN_ENC_DIR_A = -1;  // TODO(equipe)
constexpr int PIN_ENC_DIR_B = -1;  // TODO(equipe)
constexpr int ENCODER_PPR = 0;     // TODO(equipe): pulsos por revolucao (com reducao).

// MPU-6050 (I2C via Wire).
constexpr int PIN_I2C_SDA = -1;  // TODO(equipe)
constexpr int PIN_I2C_SCL = -1;  // TODO(equipe)

// ---------------------------------------------------------------------------
// LEDC (PWM)
// ---------------------------------------------------------------------------
constexpr int LEDC_FREQ_HZ = 20000;     // TODO(equipe): confirmar frequencia PWM.
constexpr int LEDC_RESOLUTION_BITS = 8;  // TODO(equipe): confirmar resolucao.
