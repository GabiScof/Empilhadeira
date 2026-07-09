"""Estado compartilhado entre as tarefas asyncio do backend.

Guarda o último comando, sensores, visão, EKF, missão, navegação e
modelo de mundo. Ponto único de leitura/escrita coordenada.
"""

from __future__ import annotations

import asyncio
import time

from app import config
from app.control.ekf import PoseEKF
from app.control.gyro_calibration import GyroCalibrator
from app.control.kalman import AttitudeKalman
from app.control.path_planner import Segment
from app.control.segment_executor import SegmentExecutor
from app.mission.mission_sm import MissionSM
from app.models import (
    Battery,
    Command,
    DetectedTag,
    DockInfo,
    EkfState,
    ImuAngles,
    MissionInfo,
    Mode,
    NavigationInfo,
    Sensors,
    Setpoint,
    Telemetry,
    VisionState,
    WheelSpeeds,
)
from app.world.robot_model import RobotModel
from app.world.world_model import WorldModel


class SharedState:
    """Estado compartilhado, protegido por lock asyncio."""

    def __init__(self) -> None:
        self.lock = asyncio.Lock()

        from app.control.navigation import NavigationController
        from app.control.state_machine import StateMachine

        self.state_machine = StateMachine()
        self.kalman = AttitudeKalman()
        self.navigator = NavigationController()

        self.robot_model = RobotModel(
            wheelbase_m=config.WHEELBASE_M,
            wheel_radius_m=config.WHEEL_RADIUS_M,
            encoder_ppr=config.ENCODER_PPR,
            max_linear_speed_ms=config.MAX_LINEAR_SPEED_MS,
            max_angular_speed_rads=config.MAX_ANGULAR_SPEED_RADS,
        )
        self.ekf = PoseEKF()
        self.gyro_cal = GyroCalibrator(
            min_samples=config.GYRO_CAL_MIN_SAMPLES,
            stationary_eps_rads=config.GYRO_CAL_STATIONARY_EPS_RADS,
            track_alpha=config.GYRO_CAL_TRACK_ALPHA,
            auto_orient=config.IMU_AUTO_ORIENT,
            fixed_sign=config.IMU_GYRO_Z_SIGN,
            tilt_warn_deg=config.IMU_TILT_WARN_DEG,
        )
        self.mission = MissionSM()
        self.segment_executor = SegmentExecutor(
            wheel_radius_m=config.WHEEL_RADIUS_M,
            wheelbase_m=config.WHEELBASE_M,
            max_v_ms=config.MAX_LINEAR_SPEED_MS,
            max_omega_rads=config.MAX_ANGULAR_SPEED_RADS,
        )
        from app.control.dock_to_tag import TagDocker
        self.docker = TagDocker()
        self.dock_enabled: bool = config.DOCK_TO_TAG_ENABLED
        self.world_model: WorldModel | None = None

        self.last_command: Command | None = None
        self.last_sensors: Sensors | None = None
        self.last_vision: VisionState = VisionState()
        self.last_imu: ImuAngles = ImuAngles(roll=0.0, pitch=0.0)

        self.current_setpoint: Setpoint = Setpoint(w_esq=0.0, w_dir=0.0)

        self.planned_path: list[Segment] = []
        self.executed_trail: list[tuple[float, float]] = []
        self.detected_tags_cache: list[DetectedTag] = []

        # Objetos de simulação (hot-swappable em troca de mapa)
        self.sim_emulator: object | None = None
        self.sim_world: object | None = None
        self.sim_vision: object | None = None

    @property
    def mode(self) -> Mode:
        return self.state_machine.mode

    @property
    def map_name(self) -> str | None:
        if self.world_model:
            return self.world_model.map.name
        return None

    def load_world(self, world: WorldModel) -> None:
        """Carrega modelo de mundo e reseta EKF para pose inicial."""
        self.world_model = world
        sx, sy, st = world.start_pose
        self.ekf.reset(sx, sy, st)
        self.planned_path = []
        self.executed_trail = [(sx, sy)]
        self.mission.reset()
        self.docker.reset()

    async def update_command(self, command: Command) -> None:
        async with self.lock:
            self.last_command = command

    async def clear_command(self) -> None:
        async with self.lock:
            self.last_command = None

    async def update_sensors(self, sensors: Sensors) -> None:
        async with self.lock:
            self.last_sensors = sensors

    async def update_vision(self, vision: VisionState) -> None:
        async with self.lock:
            self.last_vision = vision

    async def update_imu(self, imu: ImuAngles) -> None:
        async with self.lock:
            self.last_imu = imu

    async def update_setpoint(self, setpoint: Setpoint) -> None:
        async with self.lock:
            self.current_setpoint = setpoint

    async def snapshot_telemetry(self) -> Telemetry:
        """Monta um snapshot completo de telemetria."""
        async with self.lock:
            if self.last_sensors is not None:
                rodas = WheelSpeeds(
                    esq=self.last_sensors.enc.esq,
                    dir=self.last_sensors.enc.dir,
                )
            else:
                rodas = WheelSpeeds(esq=0.0, dir=0.0)

            bateria = Battery()
            if self.last_sensors is not None and self.last_sensors.bms is not None:
                bateria = self.last_sensors.bms

            reason = (
                self.state_machine.last_safety_reason
                if self.state_machine.safety_latched
                else None
            )

            nav_phase = (
                self.navigator.phase
                if self.state_machine.mode == Mode.AUTOMATICO
                else None
            )

            ekf_dict = self.ekf.to_dict()
            ekf_state = EkfState(
                x_m=ekf_dict["x_m"],
                y_m=ekf_dict["y_m"],
                theta_rad=ekf_dict["theta_rad"],
                theta_deg=ekf_dict["theta_deg"],
                covariance_trace=ekf_dict["covariance_trace"],
                last_correction=ekf_dict["last_correction"],
                correction_count=ekf_dict["correction_count"],
                ellipse_semi_major_m=ekf_dict["ellipse"]["semi_major_m"],
                ellipse_semi_minor_m=ekf_dict["ellipse"]["semi_minor_m"],
                ellipse_angle_rad=ekf_dict["ellipse"]["angle_rad"],
            )

            m_dict = self.mission.to_dict()
            mission_info = MissionInfo(**m_dict)

            dock_dict = self.docker.to_dict()
            dock_info = DockInfo(enabled=self.dock_enabled, **dock_dict)

            exec_dict = self.segment_executor.to_dict()
            nav_info = NavigationInfo(
                executor_state=exec_dict["state"],
                segment_index=exec_dict["segment_index"],
                total_segments=exec_dict["total_segments"],
                progress=exec_dict["progress"],
                current_segment_type=(
                    exec_dict["current_segment"]["type"]
                    if exec_dict["current_segment"]
                    else None
                ),
            )

            return Telemetry(
                estado=self.state_machine.mode,
                rodas=rodas,
                imu=self.last_imu,
                visao=self.last_vision,
                bateria=bateria,
                ts_ms=int(time.time() * 1000),
                parado_reason=reason,
                nav_phase=nav_phase,
                ekf=ekf_state,
                mission=mission_info,
                navigation=nav_info,
                dock=dock_info,
                detected_tags=list(self.detected_tags_cache),
                map_name=self.map_name,
            )
