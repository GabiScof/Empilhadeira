"""Contratos das interfaces de hardware (os "encaixes" SIM ↔ real).

Este arquivo é o **ponto único** que a equipe de hardware implementa. A lógica
(navegação, EKF, missão, máquina de estados) consome apenas estas interfaces e
nunca conhece a implementação concreta — por isso o mesmo código roda em SIM e
no robô real, trocando só a implementação injetada em ``app/main.py``.

Há dois encaixes:

1. ``VisionSource`` — câmera → detecção/pose de AprilTag.
     SIM:  ``app.tasks.vision_loop.SimVisionSource``  (visão sintética)
     REAL: ``app.tasks.vision_loop.RealVisionSource`` (OpenCV + pupil-apriltags)

2. ``SerialTransport`` — comandos de motor (Pi → ESP32) e sensores (ESP32 → Pi).
     SIM:  ``app.sim.firmware_emulator.FirmwareEmulator`` (via ``serial_loop_sim``)
     REAL: ``app.comms.serial_transport.PySerialTransport`` (UART real)

Os tipos de dados trocados nestes contratos vivem em ``app/models.py``
(``VisionState``, ``DetectedTag``, ``Setpoint``, ``Sensors``) e no protocolo
emoldurado em ``app/comms/protocol.py``.

[ref: Seção 2 e 3 da AGENTS.md]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.models import Sensors, Setpoint, VisionState


@dataclass(frozen=True)
class TagObservation:
    """Uma AprilTag observada, em coordenadas **relativas ao robô/câmera**.

    É o que ``VisionSource.get_all_detections`` devolve para a fusão multi-tag no
    EKF (``vision_loop._feed_ekf_from_detections``). Qualquer objeto com estes
    atributos é aceito (duck typing), mas use este tipo em código novo.

    Atributos:
        tag_id: ID AprilTag decodificado (-1 se desconhecido).
        position_id: ID lógico no mapa (ex.: "L3"), ou "" se não resolvido.
        z_m: distância à frente da câmera até a tag (m).
        x_m: deslocamento lateral da tag (m, +direita).
        yaw_rad: orientação relativa da tag — convenção:
            ``yaw_rad = (yaw_tag_no_mundo - theta_robô) - π``.
            O EKF recupera o heading via ``tag_yaw_mundo - yaw_rad - π``.
        quality: confiança da detecção em [0, 1] (1 = nítida).
    """

    tag_id: int
    position_id: str
    z_m: float
    x_m: float
    yaw_rad: float
    quality: float = 1.0


@runtime_checkable
class VisionSource(Protocol):
    """Fonte de visão: produz a pose da tag-alvo e todas as detecções do frame.

    A ``vision_loop`` chama ``get_vision()`` a cada tick e, quando disponível,
    ``get_all_detections()`` para alimentar o EKF com correções multi-tag.

    Implementações reais devem:
    - Capturar um frame da câmera e detectar AprilTags.
    - Retornar ``VisionState(detectado=False)`` quando não houver detecção
      (nunca lançar por ausência de tag — isso é normal).
    - Aplicar o offset extrínseco câmera→garfo (``CAMERA_TO_FORK_OFFSET_CM``).
    """

    def get_vision(self) -> "VisionState":
        """Pose da melhor tag (mais próxima) no contrato (z_cm, x_cm, pitch_deg).

        Sem detecção → ``VisionState(detectado=False)`` (campos null).
        """
        ...

    def get_all_detections(self) -> "list[TagObservation]":
        """Todas as tags visíveis no frame, para fusão multi-tag no EKF.

        Pode retornar ``[]`` se a fonte não suportar múltiplas detecções.
        """
        ...


@runtime_checkable
class SerialTransport(Protocol):
    """Transporte bidirecional de baixo nível com o firmware (ESP32).

    Encapsula a UART (ou qualquer barramento equivalente). A ``serial_loop_real``
    cuida da cadência (``SERIAL_HZ``) e da alimentação do EKF; o transporte só
    abre o canal, envia o setpoint e devolve os pacotes de sensores recebidos.

    O enquadramento/CRC do fio é responsabilidade do transporte (use
    ``app.comms.protocol.encode_setpoint`` / ``SensorsFrameDecoder`` como base).
    """

    async def open(self) -> None:
        """Abre o canal (porta serial, socket, etc.). Idempotente."""
        ...

    async def send_setpoint(self, setpoint: "Setpoint") -> None:
        """Envia um setpoint de rodas/garfo ao firmware (contrato 3)."""
        ...

    async def read_sensors(self, timeout_s: float) -> "list[Sensors]":
        """Lê pacotes de sensores disponíveis (contrato 4) dentro do timeout.

        Retorna ``[]`` se nada chegou na janela — não deve lançar por timeout.
        """
        ...

    async def close(self) -> None:
        """Fecha o canal e libera recursos."""
        ...
