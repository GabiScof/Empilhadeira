/**
 * main.cpp — Loop principal do ESP32 (baixo nivel, tempo real).
 *
 * O firmware opera em duas cadencias distintas controladas por millis():
 *
 *   1. PID a ~100 Hz (PID_HZ, config.h):
 *      - Le velocidade angular das rodas via encoders (ISR).
 *      - Calcula o esforco de controle PID para cada roda.
 *      - Aplica duty PWM nos motores via L298n.
 *      - Aplica comando do garfo (duty fixo enquanto pressionado).
 *
 *   2. Serial a ~20 Hz (SERIAL_HZ, config.h):
 *      - Le dados crus do MPU-6050 via I2C (acelerometro, giroscopio, temp).
 *      - Monta o pacote de sensores (contrato 4) e envia ao Pi via UART,
 *        emoldurado como <json>*<crc8hex>\n.
 *
 * Recepcao de setpoint:
 *   - Bytes da UART sao alimentados ao SetpointFrameDecoder (protocol.h) a
 *     cada iteracao do loop(), sem bloqueio.
 *   - Quando um quadro valido e decodificado (CRC + JSON + schema ok), o
 *     setpoint e armazenado e o timestamp e atualizado.
 *
 * Watchdog de setpoint [ref: Secao 4 e 7 da AGENTS.md]:
 *   - Se nenhum setpoint novo chegar em SETPOINT_TIMEOUT_MS (200 ms), o ESP32
 *     entra em estado seguro: motores zerados, PID resetado.
 *   - 200 ms = 4 mensagens perdidas a 20 Hz — margem suficiente para jitter
 *     sem falso positivo, rapido o bastante para parar se o Pi desconectar.
 *
 * MPU-6050 [ref: Secao 2.5 e 5.4 do relatorio]:
 *   - Lido via Wire (I2C) a cada ciclo serial (20 Hz).
 *   - Envia dados CRUS (acelerometro em m/s², giroscopio em graus/s).
 *   - A fusao Kalman (roll/pitch estavel) e feita no Pi, nao aqui.
 *   - Configuracao padrao: +-2g (acelerometro), +-250 graus/s (giroscopio).
 *
 * [ref: Secao 2, 5, 6 e 7 da AGENTS.md; Secoes 2, 5 e 6 do relatorio]
 */
#include <Arduino.h>
#include <Wire.h>

#include "config.h"
#include "encoders.h"
#include "motors.h"
#include "pid.h"
#include "protocol.h"

// ─── Constantes do MPU-6050 ────────────────────────────────────────────────
// Registradores relevantes do MPU-6050 (datasheet RM-MPU-6000A).
static constexpr uint8_t REG_PWR_MGMT_1    = 0x6B;
static constexpr uint8_t REG_ACCEL_XOUT_H  = 0x3B;

// Fator de escala: acelerometro na faixa +-2g (sensibilidade 16384 LSB/g).
static constexpr float ACCEL_SCALE = 9.81f / 16384.0f;   // LSB -> m/s²

// Fator de escala: giroscopio na faixa +-250 graus/s (sensibilidade 131 LSB/(graus/s)).
static constexpr float GYRO_SCALE  = 1.0f / 131.0f;      // LSB -> graus/s

// Temperatura: T(°C) = raw / 340 + 36.53 (formula do datasheet).
static constexpr float TEMP_SCALE  = 1.0f / 340.0f;
static constexpr float TEMP_OFFSET = 36.53f;

// Numero de bytes lidos de uma vez: AX,AY,AZ (6) + TEMP (2) + GX,GY,GZ (6) = 14.
static constexpr uint8_t MPU_READ_LEN = 14;

// ─── Controladores PID ─────────────────────────────────────────────────────
static Pid pidEsq(PID_KP_ESQ, PID_KI_ESQ, PID_KD_ESQ);
static Pid pidDir(PID_KP_DIR, PID_KI_DIR, PID_KD_DIR);

// ─── Estado do setpoint ────────────────────────────────────────────────────
static Setpoint lastSetpoint;
static unsigned long lastSetpointMs = 0;
static bool setpointValid = false;

// ─── Medicoes de encoder (atualizadas a cada ciclo PID) ────────────────────
static float measuredEsq = 0.0f;
static float measuredDir = 0.0f;

// ─── Controle de cadencia ──────────────────────────────────────────────────
static unsigned long lastPidMs    = 0;
static unsigned long lastSerialMs = 0;

// ─── Buffers de comunicacao serial ─────────────────────────────────────────
static char rxBuffer[256];
static SetpointFrameDecoder decoder(rxBuffer, sizeof(rxBuffer));
static char txBuffer[512];

// ─── Helpers ───────────────────────────────────────────────────────────────

/**
 * Le um valor raw de 16 bits (big-endian) do barramento I2C.
 * O MPU-6050 transmite MSB primeiro.
 */
static inline int16_t readRaw16() {
  const uint8_t hi = static_cast<uint8_t>(Wire.read());
  const uint8_t lo = static_cast<uint8_t>(Wire.read());
  return static_cast<int16_t>((hi << 8) | lo);
}

/**
 * Acorda o MPU-6050: limpa o bit SLEEP no registrador PWR_MGMT_1.
 * Chamado no setup() e re-chamado pelo loop() se o sensor aparentar morto
 * (auto-recuperacao: um write de wake que falha por mau contato no boot
 * deixaria o MPU dormindo e reportando zeros para sempre).
 */
static void mpuWake() {
  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(REG_PWR_MGMT_1);
  Wire.write(0x00);
  Wire.endTransmission();
}

/**
 * Le todos os sensores do MPU-6050 (burst read de 14 bytes a partir de 0x3B)
 * e preenche os campos correspondentes na struct Sensors.
 *
 * Ordem dos registradores no burst:
 *   ACCEL_XOUT_H/L, ACCEL_YOUT_H/L, ACCEL_ZOUT_H/L,
 *   TEMP_OUT_H/L,
 *   GYRO_XOUT_H/L, GYRO_YOUT_H/L, GYRO_ZOUT_H/L
 *
 * @return true se a leitura veio completa e com dados vivos; false em duas
 *         falhas observadas na bancada (2026-07-06, modo display), com
 *         assinaturas DISTINTAS no stream:
 *           - Barramento I2C caiu: requestFrom nao entrega 14 bytes
 *             ([E][Wire.cpp] Error 263). Retorna false ANTES de tocar os
 *             campos → frame sai com o default da struct, inclusive temp_c=0.
 *           - Sensor dormindo: I2C entrega 14 bytes TODOS zero (fisicamente
 *             impossivel com o acelerometro ligado, que sempre mostra
 *             gravidade + ruido). Os campos ja foram escritos como 0 e
 *             temp_c = 0/340 + 36.53 = 36.53 → essa e a assinatura no stream.
 *         Em ambos o loop() auto-recupera via mpuWake() (ver abaixo).
 */
static bool readMpu(Sensors& s) {
  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(REG_ACCEL_XOUT_H);
  Wire.endTransmission(false);
  Wire.requestFrom(MPU6050_ADDR, MPU_READ_LEN, static_cast<uint8_t>(true));

  if (Wire.available() < MPU_READ_LEN) {
    return false;
  }

  const int16_t raw_ax   = readRaw16();
  const int16_t raw_ay   = readRaw16();
  const int16_t raw_az   = readRaw16();
  const int16_t raw_temp = readRaw16();
  const int16_t raw_gx   = readRaw16();
  const int16_t raw_gy   = readRaw16();
  const int16_t raw_gz   = readRaw16();

  s.ax = static_cast<float>(raw_ax) * ACCEL_SCALE;
  s.ay = static_cast<float>(raw_ay) * ACCEL_SCALE;
  s.az = static_cast<float>(raw_az) * ACCEL_SCALE;
  s.gx = static_cast<float>(raw_gx) * GYRO_SCALE;
  s.gy = static_cast<float>(raw_gy) * GYRO_SCALE;
  s.gz = static_cast<float>(raw_gz) * GYRO_SCALE;
  s.mpu_temp_c = static_cast<float>(raw_temp) * TEMP_SCALE + TEMP_OFFSET;

  const bool all_zero = raw_ax == 0 && raw_ay == 0 && raw_az == 0 &&
                        raw_gx == 0 && raw_gy == 0 && raw_gz == 0 &&
                        raw_temp == 0;
  return !all_zero;
}

// ─── Setup ─────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(SERIAL_BAUDRATE);

  motorsBegin();
  encodersBegin();

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);

  // Acorda o MPU-6050 (config padrao: acelerometro +-2g, giroscopio +-250 o/s).
  mpuWake();

  // O datasheet do MPU-6050 (RM-MPU-6000A, secao 4.1) especifica que o
  // giroscopio precisa de ate 30 ms para estabilizar apos sair do modo SLEEP.
  // Aguardamos 50 ms por margem para garantir que a primeira leitura ja seja
  // valida. Sem esse delay, as primeiras amostras de gyro podem ser lixo.
  delay(50);

  const unsigned long now = millis();
  lastPidMs    = now;
  lastSerialMs = now;
}

// ─── Loop principal ────────────────────────────────────────────────────────

void loop() {
  const unsigned long now = millis();

  // ── 1. Receber bytes da UART (nao-bloqueante) ──────────────────────────
  // Alimenta cada byte ao decoder incremental. Quando um '\n' fecha um
  // quadro valido (CRC ok + JSON ok + campos obrigatorios presentes), o
  // setpoint e atualizado.
  while (Serial.available() > 0) {
    Setpoint sp;
    if (decoder.push(static_cast<uint8_t>(Serial.read()), sp)) {
      lastSetpoint   = sp;
      lastSetpointMs = now;
      setpointValid  = true;
    }
  }

  // ── 2. Watchdog do setpoint ────────────────────────────────────────────
  // Se nenhum setpoint novo chegar dentro de 200 ms, entra em estado seguro.
  if (setpointValid && SETPOINT_TIMEOUT_MS > 0 &&
      (now - lastSetpointMs) > SETPOINT_TIMEOUT_MS) {
    motorsStop();
    pidEsq.reset();
    pidDir.reset();
    setpointValid = false;
  }

  // ── 3. Malha PID a ~100 Hz ─────────────────────────────────────────────
  const unsigned long pidIntervalMs = static_cast<unsigned long>(1000.0f / PID_HZ);
  if (now - lastPidMs >= pidIntervalMs) {
    const float dt_s = static_cast<float>(now - lastPidMs) / 1000.0f;
    lastPidMs = now;

    measuredEsq = encoderReadEsq(dt_s);
    measuredDir = encoderReadDir(dt_s);

    if (setpointValid) {
      // Setpoint ZERO = parada comandada INCONDICIONAL: nao passa pelo PID.
      // Com encoder morto (medido=0), o erro de um setpoint 0 seria 0 e o
      // integral acumulado na conducao seguraria duty maximo para sempre
      // (u = Ki*integral) — o robo ignoraria o PARADO. Bug visto na bancada
      // em 2026-07-06 (roda direita sem pull-up nao parava).
      if (lastSetpoint.w_esq == 0.0f) {
        pidEsq.reset();
        motorSetWheelEsq(0.0f);
      } else {
        pidEsq.setSetpoint(lastSetpoint.w_esq);
        motorSetWheelEsq(pidEsq.update(measuredEsq, dt_s));
      }

      if (lastSetpoint.w_dir == 0.0f) {
        pidDir.reset();
        motorSetWheelDir(0.0f);
      } else {
        pidDir.setSetpoint(lastSetpoint.w_dir);
        motorSetWheelDir(pidDir.update(measuredDir, dt_s));
      }

      motorSetFork(lastSetpoint.garfo);
    }
  }

  // ── 4. Troca serial a ~20 Hz: enviar sensores ao Pi ────────────────────
  const unsigned long serialIntervalMs = static_cast<unsigned long>(1000.0f / SERIAL_HZ);
  if (now - lastSerialMs >= serialIntervalMs) {
    lastSerialMs = now;

    Sensors sensors;
    sensors.enc_esq = measuredEsq;
    sensors.enc_dir = measuredDir;

    // Auto-recuperacao do MPU: se ~1 s de leituras mortas (I2C falhou ou
    // sensor dormindo apos wake perdido no boot), re-envia o comando de wake.
    static uint8_t mpuDeadReads = 0;
    if (readMpu(sensors)) {
      mpuDeadReads = 0;
    } else if (++mpuDeadReads >= 20) {  // 20 ciclos @ 20 Hz = 1 s
      mpuWake();
      mpuDeadReads = 0;
    }

    // TODO(equipe): integrar BMS se a versao escolhida suportar leitura digital.
    // Caso contrario, has_bms permanece false e o campo "bms" sera null no JSON.
    sensors.has_bms = false;

    const size_t len = encodeSensors(sensors, txBuffer, sizeof(txBuffer));
    if (len > 0) {
      Serial.write(txBuffer, len);
    }
  }
}
