/**
 * pid.h — Controlador PID por roda.
 *
 * Especificacao [ref: Secao 7 da AGENTS.md]:
 *   u = Kp*e + Ki*integral(e) + Kd*de/dt
 * Malha a ~100 Hz (PID_HZ); o setpoint vem do Pi a 20 Hz. Se o setpoint nao
 * chegar, mantem o ultimo valido por SETPOINT_TIMEOUT_MS e depois entra em
 * estado seguro (motores zerados).
 */
#pragma once

class Pid {
 public:
  // Cria um PID com os ganhos da roda (ver config.h).
  Pid(float kp, float ki, float kd);

  // Define o setpoint alvo (rad/s).
  void setSetpoint(float setpoint);

  // Avanca a malha um passo. `measured` em rad/s, `dt_s` em segundos.
  // Retorna o esforco de controle u (mapeado para PWM em motors.*).
  float update(float measured, float dt_s);

  // Zera o estado interno (integral, erro anterior).
  void reset();

 private:
  float kp_, ki_, kd_;
  float setpoint_;
  float integral_;
  float prev_error_;
};
