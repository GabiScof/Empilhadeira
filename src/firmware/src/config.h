/**
 * config.h — Pinos, taxas e ganhos do firmware do ESP32.
 *
 * ╔═══════════════════════════════════════════════════════════════════════╗
 * ║  BRANCH: feat/firmware-production-ready                              ║
 * ║  Todos os placeholders foram substituidos por valores reais.         ║
 * ║  PRONTO PARA GRAVAR NO ESP32 e testar no hardware.                  ║
 * ╚═══════════════════════════════════════════════════════════════════════╝
 *
 * Mapa de GPIOs — FONTE DA VERDADE: Testes_eletronica.ino (bate com a placa real).
 * Este config.h foi realinhado para coincidir 1:1 com aquele firmware de teste:
 *   - Rodas:  ESQ(M2)=IN1 12 / IN2 14 / PWM 13   DIR(M3)=IN1 27 / IN2 26 / PWM 25
 *   - Garfo (M1): IN1 18 / IN2 19 / PWM 5
 *   - Inversao:   M2_INV=true (roda ESQ montada invertida) → MOTOR_ESQ_INV
 *   - Encoders:   ENC1(esq)=32/33   ENC2(dir)=34/35
 *   - I2C MPU-6050: SDA 21 / SCL 22
 *   - Fim-de-curso: DESABILITADOS por enquanto (sem chaves montadas → -1)
 *
 * Cuidados de hardware herdados desse mapa (nao sao "boas praticas", sao a placa real):
 *   - GPIO 12 (ESQ IN1) e strapping pin: PRECISA estar em LOW no boot, senao a
 *     seleccao de tensao da flash falha. Como IN1 idle = LOW, ok — mas nao ligar
 *     pull-up externo nele.
 *   - GPIO 34/35 (ENC2) sao input-only: exigem pull-up EXTERNO (ver secao encoders).
 *
 * Ganhos PID: valores iniciais conservadores para Lego NXT 53787.
 * Ajustar empiricamente com o procedimento Ziegler-Nichols (ver README).
 *
 * [ref: Secao 3 da AGENTS.md]
 */
#pragma once

#include <stdint.h>

// ---------------------------------------------------------------------------
// Serial (UART Pi <-> ESP32)
// ---------------------------------------------------------------------------
constexpr unsigned long SERIAL_BAUDRATE = 115200;  // decisao fechada (Secao 2)
constexpr float SERIAL_HZ = 20.0f;                 // taxa de troca de mensagens

// Timeout do setpoint: se nenhum setpoint novo chegar nesse intervalo, o ESP32
// entra em estado seguro (motores zerados, PID resetado).
// 200 ms = 4 mensagens perdidas a 20 Hz — margem suficiente para jitter da
// serial sem falsos positivos, mas rapido o bastante para parar o robo se
// o Pi realmente desconectar.
constexpr unsigned long SETPOINT_TIMEOUT_MS = 200;

// ---------------------------------------------------------------------------
// Malha de controle
// ---------------------------------------------------------------------------
constexpr float PID_HZ = 100.0f;  // PID por roda a ~100 Hz (decisao fechada)

// Ganhos PID por roda — valores iniciais para Lego NXT 53787 @ 12V via L298n.
//
// Logica dos valores:
//   Motor NXT 53787: ~117 RPM = ~12.25 rad/s no eixo de saida.
//   LEDC 8 bits: duty 0-255.
//   Para 1 rad/s de erro, queremos ~20 unidades de duty → Kp ≈ 20.
//   Ki baixo para correcao de regime sem overshoot: Ki ≈ 5.
//   Kd conservador para amortecer oscilacoes: Kd ≈ 1.
//
// Procedimento de ajuste (Ziegler-Nichols simplificado):
//   1. Zerar Ki e Kd.
//   2. Aumentar Kp ate o motor oscilar → esse Kp = Ku (ganho critico).
//   3. Medir o periodo da oscilacao → Tu.
//   4. Kp = 0.6*Ku, Ki = 2*Kp/Tu, Kd = Kp*Tu/8.
//   5. Ajustar empiricamente a partir dai.
constexpr float PID_KP_ESQ = 20.0f;
constexpr float PID_KI_ESQ = 5.0f;
constexpr float PID_KD_ESQ = 1.0f;
constexpr float PID_KP_DIR = 20.0f;
constexpr float PID_KI_DIR = 5.0f;
constexpr float PID_KD_DIR = 1.0f;

// Limite do termo integral (anti-windup por clamping).
// Com Ki=5 e MAX_DUTY=255, limitamos a integral a ~2x MAX_DUTY para que o
// termo integral sozinho nao sature o atuador indefinidamente.
constexpr float PID_INTEGRAL_LIMIT = 500.0f;

// ---------------------------------------------------------------------------
// Pinos — Motores de tracao (rodas) via L298n #1
// ---------------------------------------------------------------------------
// L298n modulo #1: canal A = roda esquerda, canal B = roda direita.
// Remover os jumpers de ENA/ENB do L298n e conectar os fios PWM do ESP32.
constexpr int PIN_MOTOR_ESQ_IN1 = 12;  // L298n IN1 (canal A)  [M2_IN1]
constexpr int PIN_MOTOR_ESQ_IN2 = 14;  // L298n IN2 (canal A)  [M2_IN2]
constexpr int PIN_MOTOR_ESQ_PWM = 13;  // L298n ENA (canal A) — PWM  [M2_EN]
constexpr int PIN_MOTOR_DIR_IN1 = 27;  // L298n IN3 (canal B)  [M3_IN1]
constexpr int PIN_MOTOR_DIR_IN2 = 26;  // L298n IN4 (canal B)  [M3_IN2]
constexpr int PIN_MOTOR_DIR_PWM = 25;  // L298n ENB (canal B) — PWM  [M3_EN]

// Inversao de sentido por motor — herdada do Testes_eletronica.ino (fonte da
// verdade): na placa real o motor da roda ESQ (M2) e montado invertido, entao
// "frente" fisica = IN1 LOW / IN2 HIGH. true = inverte a logica de sentido.
// Validar na bancada: setpoint positivo deve mover as DUAS rodas para frente.
constexpr bool MOTOR_ESQ_INV = true;   // [M2_INV true]
constexpr bool MOTOR_DIR_INV = false;  // [M3_INV false]

// ---------------------------------------------------------------------------
// Pinos — Motor do garfo via L298n #2 (ou driver separado)
// ---------------------------------------------------------------------------
// O garfo usa um segundo L298n (ou driver menor tipo L9110S / TB6612),
// pois o primeiro L298n ja usa os 2 canais para as rodas.
constexpr int PIN_FORK_IN1 = 18;  // L298n #2 IN1  [M1_IN1]
constexpr int PIN_FORK_IN2 = 19;  // L298n #2 IN2  [M1_IN2]
constexpr int PIN_FORK_PWM = 5;   // L298n #2 ENA — PWM  [M1_EN]

// Inversao do garfo — [M1_INV false] no Testes_eletronica.ino. Se na bancada
// "subir" descer o garfo, trocar para true (ou inverter os fios OUT1/OUT2).
constexpr bool FORK_INV = false;

// Duty fixo do garfo (0-255 para resolucao 8 bits).
// 180 ≈ 70% duty. Suficiente para o worm gear JGY-370-12V subir o garfo
// com carga leve (~100-200g). Aumentar se nao subir; diminuir se for rapido demais.
constexpr int FORK_DUTY = 180;

// ---------------------------------------------------------------------------
// Pinos — Chaves fim-de-curso do garfo
// ---------------------------------------------------------------------------
// Micro switches NO (Normally Open) entre o pino e GND.
// INPUT_PULLUP: HIGH = garfo livre, LOW = garfo no limite.
//
// DESABILITADOS por enquanto: o robo ainda nao tem as chaves de fim-de-curso
// montadas. Setar -1 faz motors.cpp pular o pinMode e nunca acusar limite
// (isFork*LimitReached() retorna sempre false). Quando as chaves forem
// instaladas, definir os GPIOs aqui — lembrando que GPIO 5 agora e o PWM do
// garfo, entao escolher outros pinos livres.
constexpr int PIN_FORK_LIMIT_TOP    = -1;  // Fim-de-curso superior — sem chave montada
constexpr int PIN_FORK_LIMIT_BOTTOM = -1;  // Fim-de-curso inferior — sem chave montada

// Nivel logico quando o fim-de-curso esta ACIONADO.
// LOW = switch NO com INPUT_PULLUP (fiacao: ESP32_PIN --- [switch NO] --- GND).
constexpr int FORK_LIMIT_ACTIVE_LEVEL = LOW;

// ---------------------------------------------------------------------------
// Pinos — Encoders de quadratura (Lego NXT 53787)
// ---------------------------------------------------------------------------
// GPIO 32/33: suportam interrupcao e INPUT_PULLUP interno.
// GPIO 34/35: input-only, SEM pull-up interno — exigem pull-up EXTERNO (10k para
//   3V3) para o encoder funcionar. O pinMode(INPUT_PULLUP) em 34/35 nao dá erro,
//   mas e ignorado pelo hardware. (Mapa alinhado ao Testes_eletronica.ino: ENC2 = 34/35.)
constexpr int PIN_ENC_ESQ_A = 32;  // Encoder esquerdo, fase A (interrupcao)  [ENC1_A]
constexpr int PIN_ENC_ESQ_B = 33;  // Encoder esquerdo, fase B (leitura sentido)  [ENC1_B]
constexpr int PIN_ENC_DIR_A = 34;  // Encoder direito, fase A (interrupcao)  [ENC2_A]
constexpr int PIN_ENC_DIR_B = 35;  // Encoder direito, fase B (leitura sentido)  [ENC2_B]

// Inversao de sinal dos encoders — [ENC1_INV/ENC2_INV false] no
// Testes_eletronica.ino (que so conta pulsos, sem sentido). Validar na
// bancada: roda girando para FRENTE deve reportar omega POSITIVO. Se vier
// negativo (motor montado espelhado), trocar para true aqui.
constexpr bool ENC_ESQ_INV = false;
constexpr bool ENC_DIR_INV = false;

// Pulsos por revolucao do eixo de saida do Lego NXT 53787.
// O motor NXT reporta 360 ticks/rev na saida (apos reducao interna).
// Com leitura RISING-only na fase A, equivale a 360 PPR.
// Se a equipe medir um valor diferente, ajustar aqui.
constexpr int ENCODER_PPR = 360;

// ---------------------------------------------------------------------------
// Pinos — MPU-6050 (I2C via Wire)
// ---------------------------------------------------------------------------
// GPIO 21 (SDA) e 22 (SCL) sao os pinos I2C padrao do ESP32.
constexpr int PIN_I2C_SDA = 21;
constexpr int PIN_I2C_SCL = 22;

// Endereco I2C do MPU-6050. 0x68 com AD0=GND (padrao).
constexpr uint8_t MPU6050_ADDR = 0x68;

// ---------------------------------------------------------------------------
// LEDC (PWM)
// ---------------------------------------------------------------------------
// 20 kHz: acima da faixa audivel humana, compativel com L298n.
constexpr int LEDC_FREQ_HZ = 20000;

// 8 bits = 256 niveis de duty (0-255). Resolucao suficiente para PID.
constexpr int LEDC_RESOLUTION_BITS = 8;

// Canais LEDC do ESP32 (0-15). Cada motor usa um canal independente.
constexpr int LEDC_CH_ESQ  = 0;  // Canal para roda esquerda
constexpr int LEDC_CH_DIR  = 1;  // Canal para roda direita
constexpr int LEDC_CH_FORK = 2;  // Canal para motor do garfo
