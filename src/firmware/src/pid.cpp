/**
 * pid.cpp — Implementacao do PID por roda (stub).
 * [ref: Secao 7 da AGENTS.md]
 */
#include "pid.h"

Pid::Pid(float kp, float ki, float kd)
    : kp_(kp), ki_(ki), kd_(kd), setpoint_(0.0f), integral_(0.0f), prev_error_(0.0f) {}

void Pid::setSetpoint(float setpoint) {
  setpoint_ = setpoint;
}

float Pid::update(float measured, float dt_s) {
  // TODO: e = setpoint_ - measured; integral_ += e*dt_s; de = (e - prev_error_)/dt_s;
  //       u = kp_*e + ki_*integral_ + kd_*de; prev_error_ = e; tratar anti-windup.
  (void)measured;
  (void)dt_s;
  return 0.0f;
}

void Pid::reset() {
  // TODO: zerar integral_ e prev_error_.
  integral_ = 0.0f;
  prev_error_ = 0.0f;
}
