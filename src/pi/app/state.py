"""Estado compartilhado entre as três tarefas asyncio do backend.

Guarda o último comando recebido do frontend, a última leitura de sensores do
ESP32, a última saída de visão e o estado atual da máquina de estados. Serve de
ponto único de leitura/escrita coordenada entre WebSocket Handler, Vision Loop e
Serial Loop.

[ref: Seção 2 da AGENTS.md]
"""

from __future__ import annotations

from app.models import Command, ImuAngles, Mode, Sensors, Telemetry, VisionState, WheelSpeeds


class SharedState:
    """Estado compartilhado, protegido para acesso concorrente entre tarefas.

    Atributos esperados (a definir na implementação):
        mode: estado atual da máquina de estados.
        last_command: último Command recebido do frontend.
        last_sensors: último Sensors recebido do ESP32.
        last_vision: última VisionState produzida pelo Vision Loop.
    """

    def __init__(self) -> None:
        """Inicializa o estado compartilhado em PARADO, sem leituras."""
        self.mode: Mode = Mode.PARADO
        self.last_command: Command | None = None
        self.last_sensors: Sensors | None = None
        self.last_vision: VisionState = VisionState()

    def update_command(self, command: Command) -> None:
        """Registra o último comando do frontend (thread/loop-safe).

        Args:
            command: comando recebido via WebSocket.
        """
        self.last_command = command
        self.mode = command.modo

    def update_sensors(self, sensors: Sensors) -> None:
        """Registra a última leitura de sensores do ESP32.

        Args:
            sensors: pacote de sensores recebido via UART.
        """
        self.last_sensors = sensors

    def update_vision(self, vision: VisionState) -> None:
        """Registra a última saída de visão.

        Args:
            vision: detecção/pose produzida pelo Vision Loop.
        """
        self.last_vision = vision

    def set_mode(self, mode: Mode) -> None:
        """Atualiza o estado atual da máquina de estados.

        Args:
            mode: novo estado (MANUAL/AUTOMATICO/PARADO).
        """
        self.mode = mode

    def snapshot_telemetry(self) -> Telemetry:
        """Monta um snapshot de telemetria a partir do estado atual.

        Returns:
            Telemetry: contrato (2) pronto para envio ao frontend.
        """
        #TODO: Revisar esta parte pois está relacionada ao controle.
        if self.last_sensors is None:
            rodas = WheelSpeeds(esq=0.0, dir=0.0)
            imu = ImuAngles(roll=0.0, pitch=0.0)
        else:
            rodas = self.last_sensors.enc
            imu = ImuAngles(roll=0.0, pitch=0.0)

        return Telemetry(
            estado=self.mode,
            rodas=rodas,
            imu=imu,
            visao=self.last_vision,
        )
