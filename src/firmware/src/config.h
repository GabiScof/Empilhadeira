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
 *   - Encoders:   ESQ=23/15 (refiado em 2026-07-06; era 34/35)   DIR=32/33
 *   - I2C MPU-6050: SDA 21 / SCL 22
 *   - Fim-de-curso: DESABILITADOS por enquanto (sem chaves montadas → -1)
 *
 * Cuidados de hardware herdados desse mapa (nao sao "boas praticas", sao a placa real):
 *   - GPIO 12 (ESQ IN1) e strapping pin: PRECISA estar em LOW no boot, senao a
 *     seleccao de tensao da flash falha. Como IN1 idle = LOW, ok — mas nao ligar
 *     pull-up externo nele.
 *   - GPIO 34/35 ficaram LIVRES (input-only, sem pull-up interno — se reutilizar,
 *     lembrar do pull-up externo).
 *
 * Ganhos PID: valores iniciais conservadores para Lego NXT 53787.
 * Ajustar empiricamente com o procedimento Ziegler-Nichols (ver README).
 *
 * [ref: Secao 3 da AGENTS.md]
 */
#pragma once

#include <stdint.h>

// ═══════════════════════════════════════════════════════════════════════════
// MEDIÇÕES PENDENTES NO ROBÔ REAL — calibrar antes de confiar na navegação
// ═══════════════════════════════════════════════════════════════════════════
// O firmware GRAVA e RODA com os valores atuais, mas os de baixo ainda são
// estimativas/ganhos iniciais. Cada item diz O QUE medir, COMO medir, a UNIDADE
// e ONDE gravar.  [F] = aqui no config.h (firmware).  [P] = no lado Pi, em
// app/config.py (geometria/óptica não moram no firmware).
//
// ── Firmware (este arquivo) ────────────────────────────────────────────────
//  1. [F] ENCODER_PPR .......... (atual 1440 = 360 ciclos x4 da quadratura)
//         COMO: gire a roda à mão EXATAMENTE 10 voltas completas e leia o total
//         de pulsos contados; PPR = pulsos / 10. Com a decodificação x4
//         (encoders.cpp) o esperado é ~14400 em 10 voltas. Atualizar aqui E o
//         EMU_ENCODER_PPR no config.py.
//
//  2. [F] MOTOR_ESQ_INV / MOTOR_DIR_INV ... (sentido dos motores)
//         COMO: enviar setpoint linear POSITIVO. As DUAS rodas devem girar para
//         FRENTE. Se uma girar ao contrário, inverter o *_INV dela.
//
//  3. [F] ENC_ESQ_INV / ENC_DIR_INV ....... (sentido dos encoders)
//         COMO: empurrar a roda para FRENTE; o omega reportado deve ser
//         POSITIVO. Se vier negativo, inverter o *_INV dela.
//
//  4. [F] FORK_INV ............. (sentido do garfo)
//         COMO: comando "subir" deve SUBIR o garfo. Se descer, trocar para true.
//
//  5. [F] FORK_DUTY ............ (atual 180, escala 0-255)
//         COMO: com a carga MÁXIMA prevista, achar o menor duty que ainda
//         levanta o garfo com folga. Subir se patinar; descer se for brusco.
//
//  6. [F] PID_K{P,I,D}_{ESQ,DIR} .. (atuais 20 / 5 / 1)
//         COMO: Ziegler-Nichols. Zerar Ki e Kd; subir Kp até oscilação
//         sustentada → Ku; medir o período dessa oscilação → Tu (s). Então
//         Kp=0.6*Ku, Ki=2*Kp/Tu, Kd=Kp*Tu/8. Repetir por roda.
//
//  7. [F] PIN_FORK_LIMIT_TOP / _BOTTOM ... (atuais -1 = sem chave)
//         COMO: quando as chaves de fim-de-curso forem montadas, definir os
//         GPIOs livres reais (lembrar que o GPIO 5 agora é o PWM do garfo).
//
// ── Lado Pi (app/config.py) — geometria/óptica ─────────────────────────────
//  8. [P] WHEEL_BASE_L_CM ...... (atual 15.0 cm) — BITOLA: distância entre os
//         pontos de contato das DUAS rodas no chão. Paquímetro/régua, em cm.
//  9. [P] WHEEL_RADIUS_R_CM .... (atual 2.8 cm) — meça o DIÂMETRO externo da
//         roda (com o peso do robô sobre ela) e divida por 2, em cm.
// 10. [P] MAX_LINEAR_SPEED / MAX_ANGULAR_SPEED — v (cm/s) e ω (rad/s) MÁXIMOS
//         reais: cronometre o robô a duty máximo por distância/ângulo conhecidos.
// 11. [P] APRILTAG_SIZE_CM ..... (atual 5.0 cm) — meça o lado do quadrado PRETO
//         da tag impressa (sem a borda branca), em cm.
// 12. [P] CAMERA_TO_FORK_OFFSET_CM ... (atual 0,0,0) — (x, y, z) em cm do centro
//         óptico da câmera até o ponto de referência do garfo.
//         (Intrínsecos fx/fy/cx/cy da câmera: JÁ calibrados em
//          calibracao/camera_intrinsics.json.)
// ═══════════════════════════════════════════════════════════════════════════

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
// LADOS CONFERIDOS NA BANCADA (2026-07-06): teste fisico com
// `bench_setpoint --w-esq 8 --w-dir 0` girou a roda DIREITA → na fiacao real
// o canal A (12/14/13) aciona a roda DIREITA e o canal B (27/26/25) a
// ESQUERDA, o inverso do rotulo M2/M3 do Testes_eletronica.ino. Mapeado aqui
// por software (mesma solucao dos encoders); encoders conferidos separados e
// estao corretos. Se um dia refizerem os fios dos motores, trocar de volta.
constexpr int PIN_MOTOR_ESQ_IN1 = 27;  // L298n IN3 (canal B)  [era M3_IN1]
constexpr int PIN_MOTOR_ESQ_IN2 = 26;  // L298n IN4 (canal B)  [era M3_IN2]
constexpr int PIN_MOTOR_ESQ_PWM = 25;  // L298n ENB (canal B) — PWM  [era M3_EN]
constexpr int PIN_MOTOR_DIR_IN1 = 12;  // L298n IN1 (canal A)  [era M2_IN1]
constexpr int PIN_MOTOR_DIR_IN2 = 14;  // L298n IN2 (canal A)  [era M2_IN2]
constexpr int PIN_MOTOR_DIR_PWM = 13;  // L298n ENA (canal A) — PWM  [era M2_EN]

// Inversao de sentido por motor — o flag acompanha o CANAL (a inversao vem da
// montagem do motor ligado naquele canal, nao do rotulo esq/dir): nos benches
// de 2026-07-06 as duas rodas giraram para FRENTE com setpoint positivo e os
// flags abaixo, entao a polaridade de cada canal esta correta.
// Validar na bancada: setpoint positivo deve mover as DUAS rodas para frente.
constexpr bool MOTOR_ESQ_INV = false;  // canal B (27/26/25)
constexpr bool MOTOR_DIR_INV = true;   // canal A (12/14/13)

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
// 0 (= LOW) para switch NO com INPUT_PULLUP (ESP32_PIN --- [switch NO] --- GND).
// Valor literal em vez do macro LOW: config.h e incluido por arquivos que nao
// puxam Arduino.h (ex.: pid.cpp), onde LOW/HIGH nao existem.
constexpr int FORK_LIMIT_ACTIVE_LEVEL = 0;  // 0 = LOW; usar 1 (HIGH) p/ switch NC

// ---------------------------------------------------------------------------
// Alimentacao do encoder por GPIO (fiacao real da equipe)
// ---------------------------------------------------------------------------
// Os fios de alimentacao do encoder foram ligados em GPIOs em vez dos pinos
// de energia da placa: GPIO 2 faz papel de VCC (OUTPUT HIGH = 3,3 V) e
// GPIO 4 faz papel de GND (OUTPUT LOW). encodersBegin() os inicializa ANTES
// de configurar as interrupcoes, para o encoder ja nascer energizado.
//
// LIMITES (importante):
//   - Um GPIO do ESP32 fornece ~40 mA absolutos (~12 mA recomendado). Serve
//     para encoder de baixo consumo; se alimentar OS DOIS encoders por aqui
//     e a leitura ficar instavel/fraca, mover os fios para os pinos reais
//     3V3/GND da placa e setar estes dois como -1.
//   - GPIO 2 e strapping pin e aciona o LED onboard do DevKit V1: o LED vai
//     acender junto (normal). Na GRAVACAO o pino precisa estar LOW/solto —
//     a carga do encoder puxa para baixo, entao normalmente ok; se a gravacao
//     falhar, desconectar temporariamente o fio do GPIO 2.
// -1 = desabilitado (alimentacao vinda dos pinos de energia da placa).
constexpr int PIN_ENC_POWER_VCC = 2;  // OUTPUT HIGH -> "VCC" do encoder
constexpr int PIN_ENC_POWER_GND = 4;  // OUTPUT LOW  -> "GND" do encoder

// ---------------------------------------------------------------------------
// Pinos — Encoders de quadratura (Lego NXT 53787)
// ---------------------------------------------------------------------------
// GPIO 32/33: suportam interrupcao e INPUT_PULLUP interno.
// LADOS CONFERIDOS NA BANCADA (2026-07-06): encoder da roda DIREITA em 32/33.
// FIACAO REFEITA (2026-07-06): o encoder ESQUERDO estava nos GPIOs 34/35
// (input-only, sem pull-up interno) e sobrecontava ~420 pulsos/volta por ruido
// nas bordas. Foi movido para 23/15, que tem pull-up interno — o INPUT_PULLUP
// do encoders.cpp volta a valer e a contagem deve bater com ENCODER_PPR.
// ATENCAO: GPIO 15 e strapping pin (MTDO) — se estiver LOW no boot, apenas
// silencia as mensagens de boot da ROM; inofensivo, mas nao estranhar.
constexpr int PIN_ENC_ESQ_A = 23;  // Encoder esquerdo, fase A (interrupcao)  [era 34]
constexpr int PIN_ENC_ESQ_B = 15;  // Encoder esquerdo, fase B (leitura sentido)  [era 35]
constexpr int PIN_ENC_DIR_A = 32;  // Encoder direito, fase A (interrupcao)  [era ENC1_A]
constexpr int PIN_ENC_DIR_B = 33;  // Encoder direito, fase B (leitura sentido)  [era ENC1_B]

// Inversao de sinal dos encoders — VALIDADO NA BANCADA (2026-07-06) com a
// decodificacao x4: roda para FRENTE deve reportar omega POSITIVO.
//   ESQ: com o x4 conta invertido (fases A/B fisicamente trocadas em relacao
//        ao lado direito) → corrigido com true.
//   DIR: correto com true (ja validado).
// Se a fiacao mudar de novo, revalidar com o teste da mao.
constexpr bool ENC_ESQ_INV = true;
constexpr bool ENC_DIR_INV = true;

// Pulsos por revolucao do eixo de saida do Lego NXT 53787.
// O motor NXT reporta 360 ciclos de quadratura/rev na saida (apos reducao
// interna) — confirmado na bancada com a leitura RISING-only antiga (~360).
// Com a decodificacao COMPLETA x4 (CHANGE nas fases A e B, ver encoders.cpp),
// cada ciclo gera 4 contagens: 360 x 4 = 1440 PPR.
// Espelhar qualquer mudanca aqui no EMU_ENCODER_PPR do app/config.py (Pi).
constexpr int ENCODER_PPR = 1440;

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
