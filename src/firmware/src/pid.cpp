/**
 * pid.cpp — Implementacao do controlador PID por roda.
 *
 * Formula classica: u = Kp*e + Ki*integral(e) + Kd*de/dt
 * onde e(t) = setpoint - medido.
 *
 * A malha roda a ~100 Hz (PID_HZ em config.h) no loop principal (main.cpp).
 * O setpoint vem do Pi via UART a 20 Hz (contrato 3). Entre setpoints
 * consecutivos, o ultimo valor valido e mantido.
 *
 * Anti-windup: o termo integral e limitado (clamping) por PID_INTEGRAL_LIMIT
 * (config.h) para evitar saturacao acumulada quando o erro persiste e a saida
 * ja esta no limite do atuador (duty maximo do LEDC).
 *
 * A saida `u` e um valor em unidades arbitrarias (determinadas pelos ganhos):
 *   - Sinal: sentido de rotacao (positivo = frente, negativo = re).
 *   - Modulo: mapeado para duty PWM em motors.cpp (clamped a MAX_DUTY).
 *
 * Os ganhos (Kp, Ki, Kd) sao placeholder (0.0) ate a sintonia empirica pela
 * equipe (Ziegler-Nichols inicial, depois ajuste manual). Com ganhos zerados,
 * a saida e sempre 0 — o que e o comportamento seguro esperado antes da
 * calibracao.
 *
 * [ref: Secao 5.2 e 7 da AGENTS.md; Secao 5.2 do relatorio]
 */
#include "pid.h"

#include "config.h"

Pid::Pid(float kp, float ki, float kd)
    : kp_(kp), ki_(ki), kd_(kd), setpoint_(0.0f), integral_(0.0f), prev_error_(0.0f) {}

void Pid::setSetpoint(float setpoint) {
  setpoint_ = setpoint;
}

float Pid::update(float measured, float dt_s) {
  if (dt_s <= 0.0f) {
    return 0.0f;
  }

  const float error = setpoint_ - measured;

  integral_ += error * dt_s;

  if (integral_ > PID_INTEGRAL_LIMIT) {
    integral_ = PID_INTEGRAL_LIMIT;
  } else if (integral_ < -PID_INTEGRAL_LIMIT) {
    integral_ = -PID_INTEGRAL_LIMIT;
  }

  const float derivative = (error - prev_error_) / dt_s;
  prev_error_ = error;

  return kp_ * error + ki_ * integral_ + kd_ * derivative;
}

void Pid::reset() {
  setpoint_ = 0.0f;
  integral_ = 0.0f;
  prev_error_ = 0.0f;
}
