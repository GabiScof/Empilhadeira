
// ======================
// BIBLIOTECAS MPU6050
// ======================
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

Adafruit_MPU6050 mpu;

// ======================
// MOTORES
// ======================

// Motor 1 (garfo)
#define M1_EN   5
#define M1_IN1  18
#define M1_IN2  19

// Motor 2 (esquerda)
#define M2_IN1  12
#define M2_EN   13
#define M2_IN2  14

// Motor 3 (direita)
#define M3_IN1  27
#define M3_IN2  26
#define M3_EN   25

// ======================
// INVERSÃO DOS MOTORES
// ======================
#define M1_INV false
#define M2_INV true
#define M3_INV false

// ======================
// ENCODERS
// ======================
#define ENC1_A 32
#define ENC1_B 33

#define ENC2_A 34
#define ENC2_B 35

unsigned long encoder1Count = 0;
unsigned long encoder2Count = 0;

#define ENC1_INV false
#define ENC2_INV false

// ======================
// MPU6050 VARIÁVEIS
// ======================
float ax, ay, az;
float gx, gy, gz;

// ======================
// INTERRUPÇÕES
// ======================
void IRAM_ATTR encoder1ISR()
{
  encoder1Count++;
}

void IRAM_ATTR encoder2ISR()
{
  encoder2Count++;
}

// ======================
// CONTROLE DE MOTOR
// ======================
void motor(uint8_t m, bool frente, uint8_t vel)
{
  bool inv = false;

  switch (m)
  {
    case 1: inv = M1_INV; break;
    case 2: inv = M2_INV; break;
    case 3: inv = M3_INV; break;
  }

  bool in1, in2;

  if (frente ^ inv)
  {
    in1 = HIGH;
    in2 = LOW;
  }
  else
  {
    in1 = LOW;
    in2 = HIGH;
  }

  switch (m)
  {
    case 1:
      digitalWrite(M1_IN1, in1);
      digitalWrite(M1_IN2, in2);
      ledcWrite(M1_EN, vel);
      break;

    case 2:
      digitalWrite(M2_IN1, in1);
      digitalWrite(M2_IN2, in2);
      ledcWrite(M2_EN, vel);
      break;

    case 3:
      digitalWrite(M3_IN1, in1);
      digitalWrite(M3_IN2, in2);
      ledcWrite(M3_EN, vel);
      break;
  }
}

// ======================
// PARAR
// ======================
void pararTodos()
{
  ledcWrite(M1_EN, 0);
  ledcWrite(M2_EN, 0);
  ledcWrite(M3_EN, 0);

  digitalWrite(M1_IN1, LOW);
  digitalWrite(M1_IN2, LOW);

  digitalWrite(M2_IN1, LOW);
  digitalWrite(M2_IN2, LOW);

  digitalWrite(M3_IN1, LOW);
  digitalWrite(M3_IN2, LOW);
}

// ======================
// SETUP
// ======================
void setup()
{
  Serial.begin(115200);
  Serial.println("Teste Eletronica");

  while (!Serial)
    delay(10);

  // ======================
  // MPU6050
  // ======================
  Wire.begin(21, 22);

  if (!mpu.begin())
  {
    
    while (1){
      Serial.println("MPU6050 não encontrado!");
      delay(10);
    }
  }

  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

  // ======================
  // MOTORES
  // ======================
  pinMode(M1_IN1, OUTPUT);
  pinMode(M1_IN2, OUTPUT);

  pinMode(M2_IN1, OUTPUT);
  pinMode(M2_IN2, OUTPUT);

  pinMode(M3_IN1, OUTPUT);
  pinMode(M3_IN2, OUTPUT);

  ledcAttach(M1_EN, 5000, 8);
  ledcAttach(M2_EN, 5000, 8);
  ledcAttach(M3_EN, 5000, 8);

  // ======================
  // ENCODERS
  // ======================
  pinMode(ENC1_A, INPUT);
  pinMode(ENC1_B, INPUT);

  pinMode(ENC2_A, INPUT);
  pinMode(ENC2_B, INPUT);

  attachInterrupt(digitalPinToInterrupt(ENC1_A), encoder1ISR, RISING);
  attachInterrupt(digitalPinToInterrupt(ENC2_A), encoder2ISR, RISING);

  pararTodos();
}

// ======================
// LOOP
// ======================
void loop()
{
  static unsigned long t = 0;

  // FRENTE
  motor(1, true, 180);
  motor(2, true, 180);
  motor(3, true, 180);

  delay(2000);

  pararTodos();
  delay(500);

  // RÉ
  motor(1, false, 180);
  motor(2, false, 180);
  motor(3, false, 180);

  delay(2000);

  pararTodos();
  delay(500);

  // ======================
  // ENCODERS
  // ======================
  noInterrupts();
  long e1 = encoder1Count;
  long e2 = encoder2Count;
  interrupts();

  // ======================
  // MPU6050
  // ======================
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

  ax = a.acceleration.x;
  ay = a.acceleration.y;
  az = a.acceleration.z;

  gx = g.gyro.x;
  gy = g.gyro.y;
  gz = g.gyro.z;

  // ======================
  // PRINT COMPLETO
  // ======================
  if (millis() - t > 200)
  {
    Serial.print("E1: ");
    Serial.print(e1);

    Serial.print(" | E2: ");
    Serial.print(e2);

    Serial.print(" || Acc: ");
    Serial.print(ax); Serial.print(",");
    Serial.print(ay); Serial.print(",");
    Serial.print(az);

    Serial.print(" || Gyro: ");
    Serial.print(gx); Serial.print(",");
    Serial.print(gy); Serial.print(",");
    Serial.println(gz);

    t = millis();
  }
}