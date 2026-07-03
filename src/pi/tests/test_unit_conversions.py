"""Testes de conversão de unidades (risco #1).

Garante que v em cm/s NUNCA é tratado como rad/s. Se o código confundir
unidades, o robô ficaria ~5-6× rápido/lento.

Cobre:
- m/s → rad/s → contagem e volta.
- cm/s → rad/s no contrato legado.
- RobotModel forward/inverse roundtrip.
"""

import math


class TestUnitConversions:
    def test_robot_model_roundtrip(self):
        from app.world.robot_model import RobotModel

        rm = RobotModel(wheelbase_m=0.15, wheel_radius_m=0.028)
        v_orig, omega_orig = 0.10, 0.5  # m/s, rad/s
        w_l, w_r = rm.inverse_kinematics(v_orig, omega_orig)
        v_back, omega_back = rm.forward_kinematics(w_l, w_r)
        assert abs(v_back - v_orig) < 1e-10
        assert abs(omega_back - omega_orig) < 1e-10

    def test_cm_vs_m_not_confused(self):
        """Se alguém tratar 30 cm/s como 30 m/s, as rodas giram absurdamente rápido."""
        from app.world.robot_model import RobotModel

        rm = RobotModel(wheel_radius_m=0.028)
        v_ms = 0.30  # 30 cm/s em m/s
        w_l, w_r = rm.inverse_kinematics(v_ms, 0.0)
        # Com r=0.028 m, v=0.30 m/s → ω ≈ 10.7 rad/s (razoável)
        assert w_l < 15.0  # NÃO é 1071 rad/s (que seria se v fosse 30 m/s)
        assert w_r < 15.0

    def test_kinematics_cm_legacy(self):
        """Cinemática legada usa cm — deve ser consistente."""
        from app.control.kinematics import twist_to_wheel_speeds, wheel_speeds_to_twist

        v_cms, omega = 15.0, 0.5  # cm/s, rad/s
        w_l, w_r = twist_to_wheel_speeds(v_cms, omega)
        v_back, omega_back = wheel_speeds_to_twist(w_l, w_r)
        assert abs(v_back - v_cms) < 1e-6
        assert abs(omega_back - omega) < 1e-6

    def test_rad_per_pulse(self):
        from app.world.robot_model import RobotModel

        rm = RobotModel(encoder_ppr=360)
        rpp = rm.rad_per_pulse()
        assert abs(rpp - 2 * math.pi / 360) < 1e-10
