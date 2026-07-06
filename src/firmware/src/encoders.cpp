/**
 * encoders.cpp — Leitura dos encoders de quadratura por interrupcao (ISR).
 *
 * Os motores Lego NXT (53787) possuem encoders de quadratura integrados com
 * duas fases (A e B). A estrategia de leitura:
 *
 *   1. Attach de interrupcao em RISING na fase A de cada encoder.
 *   2. Na ISR, leitura da fase B para determinar o sentido de rotacao:
 *      - B == LOW na borda de subida de A -> sentido positivo (frente).
 *      - B == HIGH na borda de subida de A -> sentido negativo (re).
 *   3. Um contador volatile acumula pulsos entre chamadas de leitura.
 *   4. A funcao de leitura (encoderReadEsq/Dir) calcula a velocidade angular
 *      em rad/s: omega = (pulsos / ENCODER_PPR) * 2*PI / dt_s.
 *
 * O acesso ao contador e feito em secao critica (noInterrupts/interrupts)
 * para atomicidade na leitura + reset do acumulador.
 *
 * ENCODER_PPR (config.h) = 360 pulsos por revolucao completa do eixo de saida
 * do Lego NXT 53787 (ja considerando a reducao interna). Confirmar com o
 * motor real — se o valor medido for diferente, ajustar em config.h.
 *
 * Nota de engenharia [ref: Secao 4 da AGENTS.md]:
 *   A cinematica diferencial assume rodas sem escorregamento. Se a roda
 *   patinar, a odometria por encoder degrada. Essa limitacao e tratada
 *   no nivel do Pi, nao aqui.
 *
 * [ref: Secao 7 e 8 da AGENTS.md; Secao 2.5 e 5.2 do relatorio]
 */
#include "encoders.h"

#include <Arduino.h>

#include "config.h"

// Contadores de pulso — acessados tanto pela ISR quanto pelo loop principal.
// `volatile` garante que o compilador nao otimiza leituras em registrador.
static volatile long pulses_esq = 0;
static volatile long pulses_dir = 0;

/**
 * ISR da fase A do encoder esquerdo.
 * IRAM_ATTR coloca a funcao na IRAM do ESP32 para execucao rapida em contexto
 * de interrupcao (requisito do framework Arduino-ESP32).
 */
static void IRAM_ATTR isrEncoderEsqA() {
  if (digitalRead(PIN_ENC_ESQ_B) == LOW) {
    ++pulses_esq;
  } else {
    --pulses_esq;
  }
}

/**
 * ISR da fase A do encoder direito.
 */
static void IRAM_ATTR isrEncoderDirA() {
  if (digitalRead(PIN_ENC_DIR_B) == LOW) {
    ++pulses_dir;
  } else {
    --pulses_dir;
  }
}

void encodersBegin() {
  // Alimentacao do encoder via GPIO (fiacao da equipe): GPIO como "VCC"/"GND".
  // Energizar ANTES de configurar entradas/interrupcoes, para as fases ja
  // nascerem dirigidas pelo encoder (evita contagem fantasma no boot).
  if (PIN_ENC_POWER_GND >= 0) {
    pinMode(PIN_ENC_POWER_GND, OUTPUT);
    digitalWrite(PIN_ENC_POWER_GND, LOW);   // faz papel de GND
  }
  if (PIN_ENC_POWER_VCC >= 0) {
    pinMode(PIN_ENC_POWER_VCC, OUTPUT);
    digitalWrite(PIN_ENC_POWER_VCC, HIGH);  // faz papel de 3,3 V
  }

  pinMode(PIN_ENC_ESQ_A, INPUT_PULLUP);
  pinMode(PIN_ENC_ESQ_B, INPUT_PULLUP);
  pinMode(PIN_ENC_DIR_A, INPUT_PULLUP);
  pinMode(PIN_ENC_DIR_B, INPUT_PULLUP);

  attachInterrupt(digitalPinToInterrupt(PIN_ENC_ESQ_A), isrEncoderEsqA, RISING);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_DIR_A), isrEncoderDirA, RISING);

  pulses_esq = 0;
  pulses_dir = 0;
}

float encoderReadEsq(float dt_s) {
  if (dt_s <= 0.0f || ENCODER_PPR == 0) {
    return 0.0f;
  }

  noInterrupts();
  const long captured = pulses_esq;
  pulses_esq = 0;
  interrupts();

  const float revolutions = static_cast<float>(captured) / static_cast<float>(ENCODER_PPR);
  const float omega = (revolutions * 2.0f * PI) / dt_s;
  return ENC_ESQ_INV ? -omega : omega;
}

float encoderReadDir(float dt_s) {
  if (dt_s <= 0.0f || ENCODER_PPR == 0) {
    return 0.0f;
  }

  noInterrupts();
  const long captured = pulses_dir;
  pulses_dir = 0;
  interrupts();

  const float revolutions = static_cast<float>(captured) / static_cast<float>(ENCODER_PPR);
  const float omega = (revolutions * 2.0f * PI) / dt_s;
  return ENC_DIR_INV ? -omega : omega;
}
