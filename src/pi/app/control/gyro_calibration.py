"""Auto-calibração de orientação do IMU e bias do giroscópio na partida.

Com o robô parado, infere o eixo vertical pela gravidade, projeta o giroscópio
sobre esse eixo (yaw = giro·û_cima, positivo = anti-horário = convenção do EKF)
e estima o bias de taxa-zero (rastreado devagar para drift térmico). A montagem
da placa no chassi deixa de importar desde que o eixo vertical não fique deitado;
a rotulagem X/Y/Z da GY-8x é ignorada.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

_AXIS_NAMES = ("X", "Y", "Z")


class GyroCalibrator:
    """Auto-detecta o eixo de yaw + sinal + bias do giroscópio, na partida.

    Uso: chame ``update(giro, accel, ...rodas...)`` a cada ciclo serial. Ele
    acumula amostras enquanto o robô está parado, trava a orientação ao atingir
    ``min_samples`` e daí em diante devolve a taxa de yaw corrigida (°/s),
    pronta para o EKF.
    """

    def __init__(
        self,
        min_samples: int,
        stationary_eps_rads: float,
        track_alpha: float,
        auto_orient: bool = True,
        fixed_sign: float = 1.0,
        tilt_warn_deg: float = 10.0,
    ) -> None:
        self._min_samples = max(1, min_samples)
        self._eps = stationary_eps_rads
        self._track_alpha = track_alpha
        self._auto = auto_orient
        self._tilt_warn_deg = tilt_warn_deg

        # Antes de calibrar: assume Z como eixo de yaw com o sinal manual.
        # (mantém comportamento razoável nos primeiros ciclos)
        self._up = np.array([0.0, 0.0, float(fixed_sign)])
        self._fixed_sign = float(fixed_sign)
        self._bias_dps = 0.0

        self._a_sum = np.zeros(3)
        self._g_sum = np.zeros(3)
        self._count = 0
        self._calibrated = False
        self._tilt_deg = 0.0
        self._axis_label = "?"

    @property
    def calibrated(self) -> bool:
        return self._calibrated

    @property
    def bias_dps(self) -> float:
        return self._bias_dps

    @property
    def up_axis(self) -> tuple[float, float, float]:
        """Vetor unitário 'para cima' no frame do sensor (eixo de yaw)."""
        return (float(self._up[0]), float(self._up[1]), float(self._up[2]))

    @property
    def tilt_deg(self) -> float:
        """Inclinação da placa vs. o eixo cardinal mais próximo (graus)."""
        return self._tilt_deg

    @property
    def axis_label(self) -> str:
        """Eixo de yaw detectado, ex.: '+Z' (Z p/ cima) ou '-Z' (Z p/ baixo)."""
        return self._axis_label

    def _is_stationary(
        self, w_left_cmd: float, w_right_cmd: float, w_left_meas: float, w_right_meas: float
    ) -> bool:
        return (
            abs(w_left_cmd) < self._eps
            and abs(w_right_cmd) < self._eps
            and abs(w_left_meas) < self._eps
            and abs(w_right_meas) < self._eps
        )

    def _lock(self) -> None:
        a_mean = self._a_sum / self._count
        g_mean = self._g_sum / self._count
        a_norm = float(np.linalg.norm(a_mean))

        if self._auto and a_norm >= 1.0:
            up = a_mean / a_norm  # aponta para cima (accel lê +g p/ cima)
        else:
            # Modo manual (ou gravidade degenerada): Z com sinal fixo.
            up = np.array([0.0, 0.0, self._fixed_sign])
            if self._auto:
                logger.warning(
                    "Auto-orientação IMU: |accel|=%.2f m/s² insuficiente — "
                    "usando fallback Z sinal %+.0f",
                    a_norm,
                    self._fixed_sign,
                )

        self._up = up
        self._bias_dps = float(g_mean @ up)

        # Diagnóstico: eixo dominante + inclinação vs. cardinal mais próximo.
        dom = int(np.argmax(np.abs(up)))
        self._axis_label = f"{'+' if up[dom] >= 0 else '-'}{_AXIS_NAMES[dom]}"
        self._tilt_deg = float(np.degrees(np.arccos(min(1.0, abs(up[dom])))))
        self._calibrated = True

        logger.info(
            "IMU calibrado: eixo de yaw = %s (p/ cima), inclinação %.1f°, "
            "bias %.4f °/s (%d amostras paradas)",
            self._axis_label,
            self._tilt_deg,
            self._bias_dps,
            self._count,
        )
        if self._tilt_deg > self._tilt_warn_deg:
            logger.warning(
                "IMU inclinado %.1f° (> %.1f°): heading ainda funciona (projeção "
                "na vertical), mas nivele a placa para melhor precisão.",
                self._tilt_deg,
                self._tilt_warn_deg,
            )

    def update(
        self,
        gyro_xyz,
        accel_xyz,
        *,
        w_left_cmd: float,
        w_right_cmd: float,
        w_left_meas: float,
        w_right_meas: float,
    ) -> float:
        """Devolve a taxa de yaw corrigida (°/s), pronta para o EKF.

        Args:
            gyro_xyz: (gx, gy, gz) em °/s.
            accel_xyz: (ax, ay, az) em m/s².
            w_*_cmd / w_*_meas: setpoint e medição das rodas (rad/s), p/ detectar parado.
        """
        gyro = np.asarray(gyro_xyz, dtype=float)
        accel = np.asarray(accel_xyz, dtype=float)

        # Frame MORTO do MPU (I2C caiu / sensor dormindo — assinaturas
        # documentadas no readMpu do firmware, 2026-07-06): accel ~zero é
        # fisicamente impossível com o sensor vivo (a gravidade sempre aparece,
        # |a| ≈ 9.8–11). Sem esta guarda, frames mortos no boot contaminam a
        # média da gravidade (eixo vertical sai errado) e, já calibrado,
        # erodem o bias rastreado em direção a zero. Descarta o frame inteiro:
        # não acumula, não rastreia, devolve 0 (o EKF segue só com encoders
        # neste tick; o firmware auto-recupera o MPU em ~1 s via mpuWake).
        if float(np.linalg.norm(accel)) < 2.0:
            return 0.0

        stationary = self._is_stationary(w_left_cmd, w_right_cmd, w_left_meas, w_right_meas)

        if stationary:
            if not self._calibrated:
                self._a_sum += accel
                self._g_sum += gyro
                self._count += 1
                if self._count >= self._min_samples:
                    self._lock()
            else:
                # Rastreia drift térmico do bias lentamente enquanto parado.
                yaw_raw = float(gyro @ self._up)
                self._bias_dps += self._track_alpha * (yaw_raw - self._bias_dps)

        return float(gyro @ self._up) - self._bias_dps

    def reset(self) -> None:
        """Descarta a calibração (ex.: reinício de hardware)."""
        self._up = np.array([0.0, 0.0, self._fixed_sign])
        self._bias_dps = 0.0
        self._a_sum = np.zeros(3)
        self._g_sum = np.zeros(3)
        self._count = 0
        self._calibrated = False
        self._tilt_deg = 0.0
        self._axis_label = "?"
