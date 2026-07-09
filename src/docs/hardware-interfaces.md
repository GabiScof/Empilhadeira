# Encaixes de hardware (SIM ↔ real)

A lógica (navegação, EKF, missão, máquina de estados) é a mesma em simulação e
no robô real. O que muda é só a implementação injetada em `app/main.py`, escolhida
por `config.SIM`. Dois encaixes, definidos como `Protocol` em
[`app/hardware/interfaces.py`](../pi/app/hardware/interfaces.py).

| Encaixe | SIM | Real |
|---|---|---|
| `VisionSource` | `SimVisionSource` (visão sintética) | `RealVisionSource` (OpenCV + pupil-apriltags) |
| `SerialTransport` | `FirmwareEmulator` via `serial_loop_sim` | `PySerialTransport` (UART) |

Tipos de dados trocados: `VisionState`, `Setpoint`, `Sensors` em `app/models.py`;
`TagObservation` (detecção relativa p/ o EKF) em `app/hardware/interfaces.py`.

---

## 1. Visão — `VisionSource`

```python
def get_vision(self) -> VisionState          # pose da tag mais próxima (z_cm, x_cm, pitch_deg)
def get_all_detections(self) -> list[TagObservation]   # todas as tags p/ fusão no EKF
```

A `RealVisionSource` já está implementada. O que a equipe precisa fechar:

1. **Calibração da câmera.** `pi/calibracao/camera_intrinsics.json` contém a
   recalibração de 2026-07-07 (câmera nova, remontada com tilt de 30°):
   1280×720, fx=fy=1023,63, cx=634,08, cy=377,08 (ver
   [camera-calibration.md](./camera-calibration.md)). A calibração antiga,
   640×480 da câmera anterior, foi descartada. Se os valores estiverem
   `null`, `RealVisionSource()` falha no boot com mensagem clara (controlado por
   `REQUIRE_CAMERA_CALIBRATION`; os intrínsecos de fallback de `config.py` não
   substituem o JSON no hardware real).
2. **Validar o offset câmera→garfo** (`CAMERA_TO_FORK_OFFSET_CM`) — remontagem
   2026-07-07 (2ª vez): `(0.0, -14.2, -10.0)`, z negativo (lente ~10 cm atrás da
   ponta do garfo; `pose.py` soma o offset). Depois do offset, `z_cm` = distância
   da ponta do garfo até a tag. Validar: tag a 15 cm da ponta → `z_cm` ≈ 15.
3. **Validar a convenção de `yaw_rad`** em `estimate_tag_observations` (`pose.py`)
   contra o frame real — marcado `TODO(equipe)`. A correção de posição do EKF
   não depende disso; só a de heading.

Injeção para teste: `RealVisionSource(detector=..., estimate=..., estimate_observations=...)`.

## 2. Comandos de motor / sensores — `SerialTransport`

```python
async def open(self)
async def send_setpoint(self, setpoint: Setpoint)        # Pi → ESP32 (contrato 3)
async def read_sensors(self, timeout_s) -> list[Sensors] # ESP32 → Pi (contrato 4)
async def close(self)
```

`serial_loop_real(state, transport=None)` cuida da cadência (`SERIAL_HZ`) e da
alimentação do EKF; o transporte só move bytes. O default `PySerialTransport`
(UART via pyserial-asyncio + CRC de `app/comms/protocol.py`) já funciona. Para um
barramento diferente, implemente o mesmo Protocol e passe via `transport=`.

Teste sem hardware: injete um transporte fake (ver
[`tests/test_hardware_interfaces.py`](../pi/tests/test_hardware_interfaces.py)).

---

## Como mergear

- Implementações reais entram atrás dos Protocols — sem alterar a lógica.
- Ponto único de troca: a seção `else:` (modo real) de `lifespan` em `app/main.py`.
  No boot real, falhas de câmera/serial são logadas e isoladas (a app não cai).
- Antes de ligar o hardware, feche os `TODO(equipe)` de `config.py` (constantes
  mecânicas, intrínsecos, offset, tamanho da tag). Ver
  [hardware-bring-up.md](./hardware-bring-up.md) e o guia operacional
  [hardware-deployment.md](./hardware-deployment.md).
