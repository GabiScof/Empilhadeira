/**
 * encoders.cpp — Leitura dos encoders de quadratura por interrupcao (ISR).
 *
 * Os motores Lego NXT (53787) possuem encoders de quadratura integrados com
 * duas fases (A e B). Estrategia de leitura — decodificacao COMPLETA (x4):
 *
 *   1. Attach de interrupcao em CHANGE nas DUAS fases (A e B) de cada encoder.
 *   2. A ISR le o estado atual (A<<1)|B e consulta uma tabela de transicao
 *      (estado anterior -> estado atual) que devolve -1, 0 ou +1:
 *      - Sequencia 00->10->11->01->00 (A adianta B) -> sentido positivo.
 *      - Sequencia inversa -> sentido negativo.
 *      - Transicao invalida (pulo de 2 estados, ruido) -> 0 (ignorada).
 *   3. Um contador volatile acumula os incrementos entre chamadas de leitura.
 *   4. A funcao de leitura (encoderReadEsq/Dir) calcula a velocidade angular
 *      em rad/s: omega = (pulsos / ENCODER_PPR) * 2*PI / dt_s.
 *
 * A decodificacao x4 conta as 4 bordas de cada ciclo de quadratura: 4x mais
 * resolucao que a leitura antiga (RISING-only em A) e rejeicao natural de
 * ruido — bounce numa fase gera transicoes que se cancelam (+1/-1) em vez de
 * acumular. ENCODER_PPR (config.h) = 1440 ja reflete o x4.
 *
 * CONVENCAO DE SINAL preservada da leitura antiga (validada na bancada em
 * 2026-07-06): "A subindo com B em LOW" conta POSITIVO. Os flags ENC_*_INV
 * validados continuam valendo.
 *
 * O acesso ao contador e feito em secao critica (noInterrupts/interrupts)
 * para atomicidade na leitura + reset do acumulador.
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

// Ultimo estado (A<<1)|B de cada encoder, para a tabela de transicao.
static volatile uint8_t state_esq = 0;
static volatile uint8_t state_dir = 0;

// Tabela de transicao de quadratura, indexada por (estado_anterior<<2)|estado_atual.
// Estados: (A<<1)|B. Sequencia positiva: 0->2->3->1->0 (A subindo com B LOW = +1,
// mesma convencao da leitura antiga). Transicoes invalidas valem 0.
// DRAM_ATTR: ISRs em IRAM nao podem depender de dados na flash (.rodata).
DRAM_ATTR static const int8_t QDEC_LUT[16] = {
    0, -1, +1, 0,   // de 00 para: 00, 01, 10, 11
    +1, 0,  0, -1,  // de 01 para: 00, 01, 10, 11
    -1, 0,  0, +1,  // de 10 para: 00, 01, 10, 11
    0, +1, -1, 0,   // de 11 para: 00, 01, 10, 11
};

/**
 * ISR compartilhada pelas fases A e B do encoder esquerdo (CHANGE em ambas).
 * IRAM_ATTR coloca a funcao na IRAM do ESP32 para execucao rapida em contexto
 * de interrupcao (requisito do framework Arduino-ESP32).
 */
static void IRAM_ATTR isrEncoderEsq() {
  const uint8_t s = (static_cast<uint8_t>(digitalRead(PIN_ENC_ESQ_A)) << 1) |
                    static_cast<uint8_t>(digitalRead(PIN_ENC_ESQ_B));
  pulses_esq += QDEC_LUT[(state_esq << 2) | s];
  state_esq = s;
}

/**
 * ISR compartilhada pelas fases A e B do encoder direito.
 */
static void IRAM_ATTR isrEncoderDir() {
  const uint8_t s = (static_cast<uint8_t>(digitalRead(PIN_ENC_DIR_A)) << 1) |
                    static_cast<uint8_t>(digitalRead(PIN_ENC_DIR_B));
  pulses_dir += QDEC_LUT[(state_dir << 2) | s];
  state_dir = s;
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

  // Semear o estado inicial com a posicao real das fases ANTES de anexar as
  // interrupcoes — senao a primeira transicao seria comparada contra 00
  // arbitrario e poderia contar um pulso invalido.
  state_esq = (static_cast<uint8_t>(digitalRead(PIN_ENC_ESQ_A)) << 1) |
              static_cast<uint8_t>(digitalRead(PIN_ENC_ESQ_B));
  state_dir = (static_cast<uint8_t>(digitalRead(PIN_ENC_DIR_A)) << 1) |
              static_cast<uint8_t>(digitalRead(PIN_ENC_DIR_B));

  attachInterrupt(digitalPinToInterrupt(PIN_ENC_ESQ_A), isrEncoderEsq, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_ESQ_B), isrEncoderEsq, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_DIR_A), isrEncoderDir, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_DIR_B), isrEncoderDir, CHANGE);

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
