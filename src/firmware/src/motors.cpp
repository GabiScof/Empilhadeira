/**
 * motors.cpp — Acionamento dos motores via PWM (LEDC) -> driver L298n.
 *
 * O ESP32 controla tres motores atraves de driver(s) L298n (ponte H):
 *   - Roda esquerda (Lego NXT 53787)
 *   - Roda direita   (Lego NXT 53787)
 *   - Garfo           (JGY-370-12V, worm gear)
 *
 * NOTA: um unico L298n tem 2 canais H-bridge. Tres motores exigem 2 modulos
 * L298n (um para as rodas, outro para o garfo) ou um L298n + driver menor
 * para o garfo. TODO(equipe): definir a configuracao exata.
 *
 * Cada motor usa 3 pinos no L298n:
 *   - IN1 + IN2: sentido de rotacao (HIGH/LOW = frente, LOW/HIGH = re)
 *   - ENA (PWM): velocidade (duty cycle via periferico LEDC do ESP32)
 *
 * Para as rodas, o sinal `u` vem do PID (pid.cpp):
 *   - |u| -> duty PWM, clamped a [0, MAX_DUTY]
 *   - sinal de u -> sentido (IN1/IN2)
 *
 * Para o garfo [ref: Secao 7 da AGENTS.md; Secao 5.2 do relatorio]:
 *   - SUBIR/DESCER: PWM em duty fixo (FORK_DUTY, config.h) no sentido correto
 *   - PARAR: duty 0. A reducao worm gear do motor JGY-370-12V impede backdrive,
 *     segurando a carga na posicao atual sem manter corrente.
 *
 * Fim-de-curso do garfo [ref: Secao 5.2 do relatorio]:
 *   Duas chaves micro switch nos extremos do curso do garfo (topo e base).
 *   O check e feito localmente em motorSetFork() a cada chamada (~100 Hz):
 *     - Garfo no topo (switch superior acionado) + comando SUBIR -> bloqueado
 *     - Garfo na base (switch inferior acionado) + comando DESCER -> bloqueado
 *     - Sentido oposto -> liberado normalmente
 *     - PARAR -> sempre permitido (motor para, worm gear segura)
 *   Os fim-de-curso estao configurados em GPIO 5 (topo) e GPIO 15 (base).
 *   Para desabilitar, setar o pino como -1 em config.h.
 *
 * API LEDC usada: ESP32 Arduino Core 2.x (ledcSetup + ledcAttachPin + ledcWrite).
 * Se o projeto migrar para Arduino Core 3.x (IDF 5), usar ledcAttach(pin, freq, bits)
 * e ledcWrite(pin, duty) — API baseada em pino em vez de canal.
 *
 * Estado seguro (motorsStop): zera duty das rodas e para o garfo. Chamado pelo
 * watchdog de setpoint em main.cpp quando a serial com o Pi cai.
 * [ref: Secao 4 e 7 da AGENTS.md]
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
 */
static void applyMotor(int pin_in1, int pin_in2, int ledc_ch, float u) {
  int duty = static_cast<int>(fabsf(u));
  if (duty > MAX_DUTY) {
    duty = MAX_DUTY;
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
  // --- Pinos de direcao (IN1/IN2) como saida digital ---
  pinMode(PIN_MOTOR_ESQ_IN1, OUTPUT);
  pinMode(PIN_MOTOR_ESQ_IN2, OUTPUT);
  pinMode(PIN_MOTOR_DIR_IN1, OUTPUT);
  pinMode(PIN_MOTOR_DIR_IN2, OUTPUT);
  pinMode(PIN_FORK_IN1, OUTPUT);
  pinMode(PIN_FORK_IN2, OUTPUT);

  // --- Fim-de-curso do garfo (INPUT_PULLUP) ---
  // So configura se o pino e valido (>= 0). Com -1, fica desabilitado.
  if (PIN_FORK_LIMIT_TOP >= 0) {
    pinMode(PIN_FORK_LIMIT_TOP, INPUT_PULLUP);
  }
  if (PIN_FORK_LIMIT_BOTTOM >= 0) {
    pinMode(PIN_FORK_LIMIT_BOTTOM, INPUT_PULLUP);
  }

  // --- Configurar canais LEDC (frequencia + resolucao) ---
  ledcSetup(LEDC_CH_ESQ,  LEDC_FREQ_HZ, LEDC_RESOLUTION_BITS);
  ledcSetup(LEDC_CH_DIR,  LEDC_FREQ_HZ, LEDC_RESOLUTION_BITS);
  ledcSetup(LEDC_CH_FORK, LEDC_FREQ_HZ, LEDC_RESOLUTION_BITS);

  // --- Associar pino fisico ao canal LEDC ---
  ledcAttachPin(PIN_MOTOR_ESQ_PWM, LEDC_CH_ESQ);
  ledcAttachPin(PIN_MOTOR_DIR_PWM, LEDC_CH_DIR);
  ledcAttachPin(PIN_FORK_PWM,      LEDC_CH_FORK);

  motorsStop();
}

void motorSetWheelEsq(float u) {
  applyMotor(PIN_MOTOR_ESQ_IN1, PIN_MOTOR_ESQ_IN2, LEDC_CH_ESQ, u);
}

void motorSetWheelDir(float u) {
  applyMotor(PIN_MOTOR_DIR_IN1, PIN_MOTOR_DIR_IN2, LEDC_CH_DIR, u);
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
        digitalWrite(PIN_FORK_IN1, HIGH);
        digitalWrite(PIN_FORK_IN2, LOW);
        ledcWrite(LEDC_CH_FORK, FORK_DUTY);
      }
      break;

    case ForkCommand::DESCER:
      if (forkAtBottomLimit()) {
        forkStop();
      } else {
        digitalWrite(PIN_FORK_IN1, LOW);
        digitalWrite(PIN_FORK_IN2, HIGH);
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
