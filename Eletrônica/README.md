# ⚡ Eletrônica — Empilhadeira Robótica Autônoma

> Extraído do Relatório Pré-Projeto — ENG4061 Projeto Robótica (PUC-Rio, Turma 3VB)

O cérebro da empilhadeira é a sua parte eletrônica. Esta seção documenta a alimentação, o
regulador de tensão, os motores/drivers, os microcontroladores e os sensores utilizados no
projeto, além do fluxo geral de energia e informação do sistema.

---

## 📑 Sumário

- [2.1 Bateria e BMS](#21-bateria-e-bms)
- [2.2 Regulador de tensão](#22-regulador-de-tensão)
- [2.3 Motores e drivers](#23-motores-e-drivers)
- [2.4 Microcontroladores](#24-microcontroladores)
- [2.5 Sensores](#25-sensores)
- [2.6 Fluxo do projeto](#26-fluxo-do-projeto)
- [Resumo de componentes](#-resumo-de-componentes)

---

## 2.1 Bateria e BMS

O sistema é alimentado por **3 baterias 18650 de íon-lítio em série**, cada uma com 4,2 V,
totalizando uma tensão nominal de **12,6 V**. Essa tensão supre motores, microcontroladores e
sensores. As baterias de íon-lítio foram escolhidas pela facilidade de uso, portabilidade e
disponibilidade em laboratório — exigindo atenção ao controle de temperatura, já que são
inflamáveis em condições extremas.

Para gerenciar as baterias com segurança, é utilizado um **BMS (Battery Management System)**,
responsável por:
- Controlar temperatura, carga e descarga das baterias
- Balancear a carga entre as células
- Verificar estado de vida e estado de carga
- (Em versões mais avançadas) transmitir dados das baterias para processamento posterior

**Opção adotada:** BMS 3S 40A — escolhido como opção conservadora frente aos picos de corrente
estimados dos motores sob carga (consumo estimado do sistema entre 10–15 A dependendo do modo
de operação).

---

## 2.2 Regulador de tensão

Como a alimentação de 12,6 V das baterias é inconsistente para os demais componentes, é
utilizado um único regulador de tensão para estabilizar a alimentação e proteger componentes
sensíveis:

| Regulador | Função | Tensão de saída |
|---|---|---|
| **LM2596** | Alimenta todos os periféricos (Raspberry Pi, ESP32, sensores, câmera) | 12V → 5,3V |

> Um único regulador é suficiente porque todos os demais componentes (Raspberry Pi, ESP32,
sensores, câmera) já possuem reguladores de tensão internos próprios, que ajustam os 5,3V de
entrada para o nível exigido por cada um, evitando que queimem.

---

## 2.3 Motores e drivers

| Motor | Uso | Características |
|---|---|---|
| **Lego NXT (id 53787)** | Movimentação (tração) | Torque de 16,7 N·cm · 117 RPM · encoder integrado · controle via PWM (ESP32) |
| **JGY-370-12V (Worm Gear)** | Garfo mecânico (elevação) | Motor DC com caixa de redução sem-fim; dificulta *backdrive* (sustenta carga passivamente quando desenergizado) |

**Driver:** `L298N` (Ponte H) — utilizado para controlar os três motores (tração e garfo),
permitindo o acionamento e o controle do sentido de rotação.

---

## 2.4 Microcontroladores

O projeto utiliza dois microcontroladores em uma arquitetura hierárquica:

- **Raspberry Pi** — controle de alto nível: processamento das AprilTags (visão computacional),
máquina de estados de movimentação, lei de navegação autônoma e agregação de telemetria.
- **ESP32** — controle de baixo nível: geração de PWM, malhas fechadas locais (PID) dos motores,
leitura de sensores embarcados (MPU-6050, encoders) e comunicação serial com o Raspberry Pi.

> O ESP32 foi escolhido por sua facilidade em controlar motores com precisão em tempo real —
algo que o Raspberry Pi, rodando um SO Linux convencional, não garante nativamente.

---

## 2.5 Sensores

- **MPU-6050** — acelerômetro + giroscópio (o sensor de temperatura integrado não é utilizado).
Os dados são lidos pelo ESP32 via I²C e filtrados no Raspberry Pi com um **filtro de Kalman**
para reduzir ruído e obter estimativas estáveis de orientação (roll/pitch) e velocidade angular.
- **Encoders integrados** (motor Lego) — usados para calcular RPM e realimentar a malha PID de
controle de velocidade.
- **Câmera** — utilizada para detecção de AprilTags via visão computacional (OpenCV + pupil-apriltags).

---

## 2.6 Fluxo do projeto

A eletrônica funciona como um fluxo contínuo de energia e informação:

1. A energia das baterias é condicionada e dividida em dois caminhos: um direto aos motores, e
outro regulado (LM2596, 5,3V) para os microcontroladores/sensores.
2. Sensores e encoders alimentam o **ESP32**, que repassa os dados ao **Raspberry Pi** via serial (UART).
3. O Raspberry Pi processa a informação (visão computacional + telemetria) e retorna *setpoints*
ao ESP32.
4. O ESP32 converte os *setpoints* em movimento físico nos motores.
5. O Raspberry Pi transmite os dados consolidados ao dispositivo do operador (frontend), que
pode enviar novos comandos, fechando o ciclo.

```
Baterias (12,6V) ──┬──► Motores (tração + garfo)
                    └──► Regulador LM2596 (5,3V) ──► RPi / ESP32 / Sensores / Câmera

Sensores/Encoders ──► ESP32 ──UART──► Raspberry Pi ──WebSocket──► Frontend (operador)
                       ▲                                              │
                       └──────────────── comandos/setpoints ──────────┘
```

---

## 📦 Resumo de componentes

| Categoria | Componente | Observação |
|---|---|---|
| Fonte | 3× baterias 18650 (íon-lítio) | Série · 12,6 V nominal |
| Proteção | BMS 3S 40A | Balanceamento e proteção de carga/descarga |
| Regulador | LM2596 | 12V → 5,3V (único, alimenta todos os periféricos) |
| Driver | L298N (Ponte H) | Controle dos 3 motores |
| Motor | Lego NXT 53787 ×2 | Tração |
| Motor | JGY-370-12V (Worm Gear) | Garfo mecânico |
| Microcontrolador | Raspberry Pi | Alto nível — visão computacional, navegação, telemetria |
| Microcontrolador | ESP32 | Baixo nível — PWM, PID, leitura de sensores |
| Sensor | MPU-6050 | IMU (acelerômetro + giroscópio; termômetro não utilizado) |
| Sensor | Câmera | Detecção de AprilTags |
