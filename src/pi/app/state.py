"""Estado compartilhado entre as três tarefas asyncio do backend.

Guarda o último comando recebido do frontend, a última leitura de sensores do
ESP32, a última saída de visão, a última saída do Kalman (roll/pitch) e o estado
atual da máquina de estados. Serve de ponto único de leitura/escrita coordenada
entre WebSocket Handler, Vision Loop e Serial Loop.

[ref: Seção 2 da AGENTS.md]
"""

from __future__ import annotations

import time

from app.models import Battery, Command, ImuAngles, Mode, Sensors, Telemetry, VisionState, WheelSpeeds


class SharedState:
    """Estado compartilhado, acessado de forma cooperativa pelas tarefas asyncio.

    Atributos:
        mode: estado atual da máquina de estados.
        last_command: último Command recebido do frontend.
        last_sensors: último Sensors recebido do ESP32 (Serial Loop).
        last_vision: última VisionState produzida pelo Vision Loop.
        last_imu: roll/pitch filtrados pelo Kalman (escritos pelo Serial Loop;
            inicializados em zero para o scaffolding com o produtor fake).
    """

    def __init__(self) -> None:
        """Inicializa o estado compartilhado em PARADO, sem leituras."""
        self.mode: Mode = Mode.PARADO
        self.last_command: Command | None = None
        self.last_sensors: Sensors | None = None
        self.last_vision: VisionState = VisionState()
        self.last_imu: ImuAngles = ImuAngles(roll=0.0, pitch=0.0)

    def update_command(self, command: Command) -> None:
        """Registra o último comando do frontend e aplica o modo pedido.

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

    def update_imu(self, imu: ImuAngles) -> None:
        """Registra a saída filtrada do Kalman (roll/pitch).

        Será chamado pelo Serial Loop depois de aplicar o filtro de Kalman
        sobre o MPU cru. Durante o scaffolding é escrito pelo produtor fake.

        Args:
            imu: roll e pitch filtrados (graus).
        """
        self.last_imu = imu

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

        Lê exclusivamente os campos do SharedState; não recalcula nada.
        Quando Serial Loop e Vision Loop estiverem ativos, eles apenas
        passam a escrever nos mesmos campos — este método não precisa mudar.

        Returns:
            Telemetry: contrato (2) pronto para envio ao frontend.
        """
        ts = int(time.monotonic() * 1000)

        if self.last_sensors is None:
            rodas = WheelSpeeds(esq=0.0, dir=0.0)
            bateria = Battery()
        else:
            enc = self.last_sensors.enc
            rodas = WheelSpeeds(esq=enc.esq, dir=enc.dir)
            bateria = self.last_sensors.bms if self.last_sensors.bms is not None else Battery()

        return Telemetry(
            estado=self.mode,
            rodas=rodas,
            imu=self.last_imu,
            visao=self.last_vision,
            bateria=bateria,
            ts_ms=ts,
        )
