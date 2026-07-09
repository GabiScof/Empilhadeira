/**
 * motors.cpp — Acionamento dos motores via PWM (LEDC) -> driver L298n.
 *
 * Tres motores: rodas esq/dir (Lego NXT 53787) e garfo (JGY-370-12V).
 * Cada motor usa IN1/IN2 (sentido) + ENA (PWM via LEDC).
 *
 * Rodas: |u| -> duty clamped; sinal -> IN1/IN2.
 * Garfo: SUBIR/DESCER em FORK_DUTY; PARAR em duty 0 (worm gear segura carga).
 * Fim-de-curso bloqueia SUBIR no topo e DESCER na base (local, ~100 Hz).
 * Desabilitados enquanto PIN_FORK_LIMIT_* = -1.
 *
 * LEDC: ESP32 Arduino Core 2.x (ledcSetup + ledcAttachPin + ledcWrite).
 */
#include "motors.h"

#include <Arduino.h>

#include "config.h"

static const int MAX_DUTY = (1 << LEDC_RESOLUTION_BITS) - 1;

/**
 * Aplica sentido e duty a um motor via L298n.
 *
 * @param pin_in1   Pino IN1 do L298n (sentido A)
 * @param pin_in2   Pino IN2 do L298n (sentido B)
 * @param ledc_ch   Canal LEDC associado ao pino ENA/PWM
 * @param u         Esforco de controle: sinal = sentido, |u| = duty
 * @param inv       Motor montado invertido (M*_INV do Testes_eletronica.ino):
 *                  troca a logica IN1/IN2 para que u>0 seja "frente" fisica.
 */
static void applyMotor(int pin_in1, int pin_in2, int ledc_ch, float u, bool inv) {
  int duty = static_cast<int>(fabsf(u));
  if (duty > MAX_DUTY) {
    duty = MAX_DUTY;
  }

  if (inv) {
    u = -u;
  }

  if (u > 0.0f) {
    digitalWrite(pin_in1, HIGH);
    digitalWrite(pin_in2, LOW);
  } else if (u < 0.0f) {
    digitalWrite(pin_in1, LOW);
    digitalWrite(pin_in2, HIGH);
  } else {
    digitalWrite(pin_in1, LOW);
    digitalWrite(pin_in2, LOW);
  }

  ledcWrite(ledc_ch, duty);
}

/**
 * Para o motor do garfo: IN1=LOW, IN2=LOW, duty=0.
 * Usado quando um fim-de-curso bloqueia o sentido solicitado.
 */
static void forkStop() {
  digitalWrite(PIN_FORK_IN1, LOW);
  digitalWrite(PIN_FORK_IN2, LOW);
  ledcWrite(LEDC_CH_FORK, 0);
}

void motorsBegin() {
  pinMode(PIN_MOTOR_ESQ_IN1, OUTPUT);
  pinMode(PIN_MOTOR_ESQ_IN2, OUTPUT);
  pinMode(PIN_MOTOR_DIR_IN1, OUTPUT);
  pinMode(PIN_MOTOR_DIR_IN2, OUTPUT);
  pinMode(PIN_FORK_IN1, OUTPUT);
  pinMode(PIN_FORK_IN2, OUTPUT);

  // So configura se o pino e valido (>= 0). Com -1, fica desabilitado.
  if (PIN_FORK_LIMIT_TOP >= 0) {
    pinMode(PIN_FORK_LIMIT_TOP, INPUT_PULLUP);
  }
  if (PIN_FORK_LIMIT_BOTTOM >= 0) {
    pinMode(PIN_FORK_LIMIT_BOTTOM, INPUT_PULLUP);
  }

  ledcSetup(LEDC_CH_ESQ,  LEDC_FREQ_HZ, LEDC_RESOLUTION_BITS);
  ledcSetup(LEDC_CH_DIR,  LEDC_FREQ_HZ, LEDC_RESOLUTION_BITS);
  ledcSetup(LEDC_CH_FORK, LEDC_FREQ_HZ, LEDC_RESOLUTION_BITS);

  ledcAttachPin(PIN_MOTOR_ESQ_PWM, LEDC_CH_ESQ);
  ledcAttachPin(PIN_MOTOR_DIR_PWM, LEDC_CH_DIR);
  ledcAttachPin(PIN_FORK_PWM,      LEDC_CH_FORK);

  motorsStop();
}

void motorSetWheelEsq(float u) {
  applyMotor(PIN_MOTOR_ESQ_IN1, PIN_MOTOR_ESQ_IN2, LEDC_CH_ESQ, u, MOTOR_ESQ_INV);
}

void motorSetWheelDir(float u) {
  applyMotor(PIN_MOTOR_DIR_IN1, PIN_MOTOR_DIR_IN2, LEDC_CH_DIR, u, MOTOR_DIR_INV);
}

bool forkAtTopLimit() {
  if (PIN_FORK_LIMIT_TOP < 0) {
    return false;
  }
  return digitalRead(PIN_FORK_LIMIT_TOP) == FORK_LIMIT_ACTIVE_LEVEL;
}

bool forkAtBottomLimit() {
  if (PIN_FORK_LIMIT_BOTTOM < 0) {
    return false;
  }
  return digitalRead(PIN_FORK_LIMIT_BOTTOM) == FORK_LIMIT_ACTIVE_LEVEL;
}

void motorSetFork(ForkCommand cmd) {
  switch (cmd) {
    case ForkCommand::SUBIR:
      if (forkAtTopLimit()) {
        forkStop();
      } else {
        digitalWrite(PIN_FORK_IN1, FORK_INV ? LOW : HIGH);
        digitalWrite(PIN_FORK_IN2, FORK_INV ? HIGH : LOW);
        ledcWrite(LEDC_CH_FORK, FORK_DUTY);
      }
      break;

    case ForkCommand::DESCER:
      if (forkAtBottomLimit()) {
        forkStop();
      } else {
        digitalWrite(PIN_FORK_IN1, FORK_INV ? HIGH : LOW);
        digitalWrite(PIN_FORK_IN2, FORK_INV ? LOW : HIGH);
        ledcWrite(LEDC_CH_FORK, FORK_DUTY);
      }
      break;

    case ForkCommand::PARAR:
    default:
      forkStop();
      break;
  }
}

void motorsStop() {
  motorSetWheelEsq(0.0f);
  motorSetWheelDir(0.0f);
  forkStop();
}
