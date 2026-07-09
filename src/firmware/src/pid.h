/**
 * pid.h — Controlador PID por roda.
 *
 * u = Kp*e + Ki*integral(e) + Kd*de/dt
 * Malha ~100 Hz; setpoint do Pi a 20 Hz.
 */
#pragma once

class Pid {
 public:
  Pid(float kp, float ki, float kd);

  void setSetpoint(float setpoint);

  float update(float measured, float dt_s);

  void reset();

 private:
  float kp_, ki_, kd_;
  float setpoint_;
  float integral_;
  float prev_error_;
};
