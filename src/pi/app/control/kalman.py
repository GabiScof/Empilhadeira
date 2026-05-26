"""Filtro de Kalman para fusão do MPU-6050 → roll/pitch estáveis.

Especificação [ref: Seção 7 da AGENTS.md]:
- Funde **acelerômetro** (referência de gravidade, ruidoso mas sem deriva) com
  **giroscópio** (suave, mas com deriva) do MPU-6050.
- A filtragem é feita **no Pi**; o ESP32 envia apenas dados **crus** (contrato 4).
- Saída: roll e pitch em **graus** (sub-objeto `imu` do contrato de telemetria).

Sugestão de implementação: `filterpy`. [ref: Seção 8]
"""

from __future__ import annotations

from app.models import ImuAngles, MpuRaw


class AttitudeKalman:
    """Estima roll/pitch fundindo acelerômetro e giroscópio do MPU-6050."""

    def __init__(self) -> None:
        """Inicializa o filtro (estado, covariâncias, modelo)."""
        raise NotImplementedError

    def update(self, mpu: MpuRaw, dt_s: float) -> ImuAngles:
        """Avança o filtro com uma nova leitura crua do MPU.

        Args:
            mpu: leitura crua do MPU-6050 (m/s² e graus/s).
            dt_s: passo de tempo desde a última atualização (s).

        Returns:
            ImuAngles: roll e pitch filtrados (graus).
        """
        raise NotImplementedError
