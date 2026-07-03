# Encaixes de hardware (SIM ↔ real)

A lógica (navegação, EKF, missão, máquina de estados) é **a mesma** em simulação e
no robô real. O que muda é só a implementação injetada em `app/main.py`, escolhida
por `config.SIM`. Há dois encaixes, definidos como `Protocol` em
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

1. **Calibrar a câmera.** Gere `pi/calibracao/camera_intrinsics.json` com `fx, fy,
   cx, cy` (ver [camera-calibration.md](./camera-calibration.md)). Enquanto os
   valores estiverem `null`, `RealVisionSource()` falha no boot com mensagem clara
   (controlado por `REQUIRE_CAMERA_CALIBRATION`; os intrínsecos placeholder de
   `config.py` **não** servem para o hardware real).
2. **Medir o offset câmera→garfo** (`CAMERA_TO_FORK_OFFSET_CM`) — aplicado em
   `pose.py`. Sem isso, há erro sistemático de alguns cm.
3. **Validar a convenção de `yaw_rad`** em `estimate_tag_observations` (`pose.py`)
   contra o frame real — marcado `TODO(equipe)`. A correção de **posição** do EKF
   não depende disso; só a de **heading**.

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

- Implementações reais entram **atrás dos Protocols** — não toquem na lógica.
- Ponto único de troca: a seção `else:` (modo real) de `lifespan` em `app/main.py`.
  No boot real, falhas de câmera/serial são logadas e isoladas (a app não cai).
- Antes de ligar o hardware, feche os `TODO(equipe)` de `config.py` (constantes
  mecânicas, intrínsecos, offset, tamanho da tag). Ver
  [hardware-bring-up.md](./hardware-bring-up.md) e o guia operacional
  [hardware-deployment.md](./hardware-deployment.md).
