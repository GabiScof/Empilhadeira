"""Testes dos encaixes de hardware (calibração, detector, transporte serial).

Garante que as interfaces que a equipe vai implementar estão prontas:
- Calibração: carrega JSON válido, falha claro quando não calibrado.
- Detector: prioridade de intrínsecos (injetado > config); from_calibration.
- Visão real: estimate_tag_observations produz TagObservation a partir de poses.
- Serial real: serial_loop_real dirige um SerialTransport injetável (fake).
"""

import asyncio
import json

import numpy as np
import pytest


class TestCalibration:
    def test_missing_file_raises(self, tmp_path):
        from app.vision.calibration import CalibrationError, load_intrinsics

        with pytest.raises(CalibrationError):
            load_intrinsics(tmp_path / "nao_existe.json")

    def test_null_values_raise(self, tmp_path):
        from app.vision.calibration import CalibrationError, load_intrinsics

        p = tmp_path / "cal.json"
        p.write_text(json.dumps({"fx": None, "fy": None, "cx": None, "cy": None}))
        with pytest.raises(CalibrationError):
            load_intrinsics(p)

    def test_valid_loads(self, tmp_path):
        from app.vision.calibration import is_calibrated, load_intrinsics

        p = tmp_path / "cal.json"
        p.write_text(json.dumps({
            "fx": 600.0, "fy": 605.0, "cx": 320.0, "cy": 240.0,
            "dist_coeffs": [0.1, -0.2, 0.0, 0.0, 0.0],
            "image_size": [640, 480], "reprojection_error": 0.3,
        }))
        intr = load_intrinsics(p)
        assert intr.camera_params == (600.0, 605.0, 320.0, 240.0)
        assert intr.image_size == (640, 480)
        assert is_calibrated(p) is True
        assert intr.camera_matrix.shape == (3, 3)
        assert intr.camera_matrix[0, 0] == 600.0


class TestDetector:
    def test_param_priority(self):
        from app import config
        from app.vision.calibration import CameraIntrinsics
        from app.vision.detector import AprilTagDetector

        assert AprilTagDetector().camera_params == config.CAMERA_PARAMS
        assert AprilTagDetector(camera_params=(1, 2, 3, 4)).camera_params == (1, 2, 3, 4)
        intr = CameraIntrinsics(fx=9, fy=9, cx=1, cy=1, dist_coeffs=[0] * 5)
        # intrinsics tem prioridade sobre camera_params
        det = AprilTagDetector(camera_params=(1, 2, 3, 4), intrinsics=intr)
        assert det.camera_params == (9, 9, 1, 1)

    def test_from_calibration_raises_when_uncalibrated(self, tmp_path):
        from app.vision.calibration import CalibrationError
        from app.vision.detector import AprilTagDetector

        p = tmp_path / "cal.json"
        p.write_text(json.dumps({"fx": None, "fy": None, "cx": None, "cy": None}))
        with pytest.raises(CalibrationError):
            AprilTagDetector.from_calibration(p)


class _FakeDetection:
    """Detecção crua mínima (atributos que pose.py consome)."""

    def __init__(self, tag_id, x, y, z, decision_margin=80.0):
        self.tag_id = tag_id
        self.pose_t = np.array([[x], [y], [z]], dtype=float)
        self.pose_R = np.eye(3)
        self.decision_margin = decision_margin


class TestObservations:
    def test_estimate_tag_observations(self):
        from app.hardware.interfaces import TagObservation
        from app.vision.pose import estimate_tag_observations

        dets = [_FakeDetection(3, 0.02, 0.0, 0.35), _FakeDetection(5, -0.1, 0.0, 0.6)]
        obs = estimate_tag_observations(dets)
        assert len(obs) == 2
        assert all(isinstance(o, TagObservation) for o in obs)
        # z_m vem direto da translação; x_m é NEGADO na fronteira (frame óptico
        # OpenCV: x positivo = direita; convenção do projeto/EKF: x positivo =
        # esquerda — mesmo fix do estimate_vision_state, 2026-07-07).
        assert obs[0].tag_id == 3
        assert obs[0].z_m == pytest.approx(0.35)
        assert obs[0].x_m == pytest.approx(-0.02)
        assert 0.0 <= obs[0].quality <= 1.0

    def test_empty(self):
        from app.vision.pose import estimate_tag_observations

        assert estimate_tag_observations([]) == []


class _FakeTransport:
    """SerialTransport em memória para testar serial_loop_real sem hardware."""

    def __init__(self, sensors):
        self.opened = False
        self.closed = False
        self.sent = []
        self._sensors = sensors

    async def open(self):
        self.opened = True

    async def send_setpoint(self, setpoint):
        self.sent.append(setpoint)

    async def read_sensors(self, timeout_s):
        return list(self._sensors)

    async def close(self):
        self.closed = True


class TestSerialLoopReal:
    def test_drives_injected_transport(self):
        from app.models import Encoders, MpuRaw, Sensors
        from app.state import SharedState
        from app.tasks.serial_loop import serial_loop_real

        sensors = Sensors(
            enc=Encoders(esq=1.0, dir=1.0),
            mpu=MpuRaw(ax=0, ay=0, az=9.8, gx=0, gy=0, gz=0, temp_c=25.0),
        )
        transport = _FakeTransport([sensors])
        state = SharedState()

        async def run_once():
            task = asyncio.create_task(serial_loop_real(state, transport))
            await asyncio.sleep(0.12)  # algumas iterações @ SERIAL_HZ
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(run_once())

        assert transport.opened is True
        assert transport.closed is True
        assert len(transport.sent) >= 1  # setpoint enviado
        # sensores alimentaram o estado
        assert state.last_sensors is not None


class TestCameraTilt:
    """Compensação da câmera inclinada (CAMERA_TILT_DEG) em pose.py.

    A câmera no topo do trilho do garfo olha para baixo; o z do AprilTag sai
    na hipotenusa. Com o tilt configurado, z/x devem virar distâncias
    HORIZONTAIS (o desnível vai para o y, ignorado pelo contrato).
    """

    def test_tilt_zero_is_identity(self, monkeypatch):
        from app import config
        from app.vision.pose import estimate_vision_state

        monkeypatch.setattr(config, "CAMERA_TILT_DEG", 0.0)
        monkeypatch.setattr(config, "CAMERA_TO_FORK_OFFSET_CM", (0.0, 0.0, 0.0))
        vs = estimate_vision_state([_FakeDetection(1, 0.0, 0.0, 0.30)])
        assert vs.z_cm == pytest.approx(30.0)
        assert vs.x_cm == pytest.approx(0.0)

    def test_tilt_recovers_horizontal_distance(self, monkeypatch):
        import math

        from app import config
        from app.vision.pose import estimate_vision_state

        tilt = 20.0
        monkeypatch.setattr(config, "CAMERA_TILT_DEG", tilt)
        monkeypatch.setattr(config, "CAMERA_TO_FORK_OFFSET_CM", (0.0, 0.0, 0.0))
        # Tag no CENTRO da imagem (sobre o eixo óptico), a 1.0 m HORIZONTAL:
        # a câmera vê a hipotenusa L = 1/cos(20°).
        slant = 1.0 / math.cos(math.radians(tilt))
        vs = estimate_vision_state([_FakeDetection(1, 0.0, 0.0, slant)])
        assert vs.z_cm == pytest.approx(100.0, abs=0.1)
        assert vs.x_cm == pytest.approx(0.0, abs=1e-6)

    def test_tilt_applies_to_ekf_observations_too(self, monkeypatch):
        import math

        from app import config
        from app.vision.pose import estimate_tag_observations

        tilt = 20.0
        monkeypatch.setattr(config, "CAMERA_TILT_DEG", tilt)
        slant = 0.5 / math.cos(math.radians(tilt))
        obs = estimate_tag_observations([_FakeDetection(7, 0.0, 0.0, slant)])
        assert obs[0].z_m == pytest.approx(0.5, abs=1e-3)
        # x lateral não é afetado pelo tilt (rotação em torno do próprio x).
        assert obs[0].x_m == pytest.approx(0.0, abs=1e-9)
