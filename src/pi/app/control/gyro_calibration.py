"""Calibração de bias do giroscópio (eixo Z) — zero-rate offset.

O MPU-6050 tem um offset de taxa-zero (*bias*) que varia com temperatura e
entre unidades. Integrar ``gz`` com bias diferente de zero faz o heading do
EKF derivar mesmo com o robô totalmente parado — a maior fonte de erro de
heading no robô real. Este módulo estima o bias amostrando ``gz`` enquanto o
robô está **comprovadamente parado** e o subtrai de todas as leituras
subsequentes.

Por que a posição física do IMU no chassi não importa: usamos apenas ``gz``,
e o eixo Z do módulo aponta para cima (= eixo de yaw do robô). Um corpo
rígido tem UMA velocidade angular, idêntica em qualquer ponto — logo o
giroscópio mede a mesma taxa de yaw independentemente de onde esteja montado.
Só importam (1) o eixo Z ficar vertical e (2) o *bias* e o *sinal* do eixo,
tratados aqui. [ref: discussão IMU]
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class GyroCalibrator:
    """Estima e remove o bias de taxa-zero do giroscópio no eixo Z.

    Fluxo:
      1. Enquanto o robô está parado (setpoint zero E encoders ~0), acumula
         amostras de ``gz``.
      2. Ao atingir ``min_samples``, trava ``bias = média`` das amostras.
      3. Depois de calibrado, continua parado → rastreia drift térmico via
         uma média móvel exponencial lenta (``track_alpha``).
      4. ``update()`` sempre devolve ``sign * (gz - bias)``, pronto para o EKF.

    O ``sign`` converte a convenção do eixo do sensor para a do robô
    (yaw+ = anti-horário visto de cima). Com o eixo Z apontando para cima o
    default (+1) já está correto; use -1 se o heading girar ao contrário.
    """

    def __init__(
        self,
        min_samples: int,
        stationary_eps_rads: float,
        track_alpha: float,
        sign: float = 1.0,
    ) -> None:
        self._min_samples = max(1, min_samples)
        self._eps = stationary_eps_rads
        self._track_alpha = track_alpha
        self._sign = sign

        self._bias_dps = 0.0
        self._sum = 0.0
        self._count = 0
        self._calibrated = False

    @property
    def bias_dps(self) -> float:
        """Bias atual estimado (°/s)."""
        return self._bias_dps

    @property
    def calibrated(self) -> bool:
        """True quando o bias já foi travado com amostras suficientes."""
        return self._calibrated

    def _is_stationary(
        self,
        w_left_cmd: float,
        w_right_cmd: float,
        w_left_meas: float,
        w_right_meas: float,
    ) -> bool:
        """Parado = comando E medição de ambas as rodas abaixo de eps (rad/s)."""
        return (
            abs(w_left_cmd) < self._eps
            and abs(w_right_cmd) < self._eps
            and abs(w_left_meas) < self._eps
            and abs(w_right_meas) < self._eps
        )

    def update(
        self,
        gz_dps: float,
        *,
        w_left_cmd: float,
        w_right_cmd: float,
        w_left_meas: float,
        w_right_meas: float,
    ) -> float:
        """Atualiza o estimador e devolve ``gz`` corrigido (°/s, com sinal).

        Args:
            gz_dps: leitura crua do giroscópio no eixo Z (°/s).
            w_left_cmd / w_right_cmd: setpoint de velocidade das rodas (rad/s).
            w_left_meas / w_right_meas: velocidade medida pelos encoders (rad/s).

        Returns:
            Taxa de yaw corrigida em °/s: ``sign * (gz - bias)``.
        """
        if self._is_stationary(w_left_cmd, w_right_cmd, w_left_meas, w_right_meas):
            if not self._calibrated:
                self._sum += gz_dps
                self._count += 1
                if self._count >= self._min_samples:
                    self._bias_dps = self._sum / self._count
                    self._calibrated = True
                    logger.info(
                        "Giroscópio calibrado: bias=%.4f °/s (%d amostras paradas)",
                        self._bias_dps,
                        self._count,
                    )
            else:
                # Rastreia drift térmico lentamente enquanto parado.
                self._bias_dps += self._track_alpha * (gz_dps - self._bias_dps)

        return self._sign * (gz_dps - self._bias_dps)

    def reset(self) -> None:
        """Descarta a calibração (ex.: reinício de hardware)."""
        self._bias_dps = 0.0
        self._sum = 0.0
        self._count = 0
        self._calibrated = False
