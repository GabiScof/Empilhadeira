"""Tarefa de visão: captura frames, detecta AprilTags e alimenta o EKF.

Suporta detecção de múltiplas tags (sintética ou real). Resolve IDs contra
o world model e aplica correções de pose no EKF.
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Protocol

from app import config
from app.models import DetectedTag, VisionState
from app.state import SharedState

logger = logging.getLogger(__name__)


class VisionSource(Protocol):
    """Interface para fontes de visão injetáveis."""

    def get_vision(self) -> VisionState:
        ...


class RealVisionSource:
    """Fonte de visão real usando OpenCV + pupil-apriltags.

    Implementa ``app.hardware.interfaces.VisionSource``. O detector é construído a
    partir da calibração da câmera (``config.CAMERA_INTRINSICS_PATH``); se a câmera
    ainda não foi calibrada e ``REQUIRE_CAMERA_CALIBRATION`` está ligado, a
    construção falha com erro claro (os intrínsecos placeholder de config NÃO
    servem para o hardware real).

    O ``detector`` e o estimador podem ser injetados para teste/mocking.
    """

    def __init__(self, detector=None, estimate=None, estimate_observations=None) -> None:
        import cv2

        from app.vision.calibration import CalibrationError
        from app.vision.detector import AprilTagDetector
        from app.vision.pose import estimate_tag_observations, estimate_vision_state

        if detector is not None:
            self._detector = detector
        else:
            try:
                self._detector = AprilTagDetector.from_calibration()
                logger.info("Detector criado com calibração de câmera")
            except CalibrationError as exc:
                if config.REQUIRE_CAMERA_CALIBRATION:
                    raise RuntimeError(
                        f"Visão real exige calibração da câmera: {exc} "
                        "(defina REQUIRE_CAMERA_CALIBRATION=0 para usar placeholders, "
                        "mas a pose será imprecisa)."
                    ) from exc
                logger.warning("Câmera não calibrada — usando placeholders (%s)", exc)
                self._detector = AprilTagDetector()

        self._estimate = estimate or estimate_vision_state
        self._estimate_observations = estimate_observations or estimate_tag_observations

        # Resolução: a da CALIBRAÇÃO tem prioridade sobre config/env — os
        # intrínsecos só valem nela; capturar em outra produz z/x
        # silenciosamente errados (armadilha vista na bancada, 2026-07-07).
        from app.vision.calibration import calibration_image_size

        cal_size = calibration_image_size()
        width, height = cal_size or (config.CAMERA_FRAME_WIDTH, config.CAMERA_FRAME_HEIGHT)
        if cal_size and cal_size != (config.CAMERA_FRAME_WIDTH, config.CAMERA_FRAME_HEIGHT):
            logger.warning(
                "Config/env pedia %dx%d, mas a calibração é %dx%d — usando a da calibração",
                config.CAMERA_FRAME_WIDTH, config.CAMERA_FRAME_HEIGHT, width, height,
            )

        self._capture = cv2.VideoCapture(config.CAMERA_INDEX)
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._cv2 = cv2
        self._last_detections: list = []

        if not self._capture.isOpened():
            raise RuntimeError(f"Câmera não abriu (índice {config.CAMERA_INDEX})")

        real_w = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        real_h = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if (real_w, real_h) != (width, height):
            msg = (
                f"Câmera entregou {real_w}x{real_h} em vez dos {width}x{height} "
                "da calibração — pose z/x da navegação sairia inválida. "
                "Recalibre nessa resolução ou ajuste a câmera."
            )
            if config.REQUIRE_CAMERA_CALIBRATION:
                self._capture.release()
                raise RuntimeError(msg)
            logger.error(msg)
        logger.info("Câmera aberta a %dx%d (índice %d)", real_w, real_h, config.CAMERA_INDEX)

    def _detect(self) -> list:
        read_ok, frame = self._capture.read()
        if not read_ok:
            self._last_detections = []
            return []
        gray = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY)
        self._last_detections = self._detector.detect(gray)
        return self._last_detections

    def get_vision(self) -> VisionState:
        return self._estimate(self._detect())

    def get_all_detections(self) -> list:
        """Tags do **último frame** (do get_vision deste tick) como TagObservation.

        Reutiliza as detecções capturadas por ``get_vision`` para não capturar dois
        frames por tick — a ``vision_loop`` chama os dois em sequência.
        """
        return self._estimate_observations(self._last_detections)

    def release(self) -> None:
        self._capture.release()


class SimVisionSource:
    """Fonte de visão sintética para SIM=1 com suporte a múltiplas tags.

    Lê ``state.sim_vision`` e ``state.sim_world`` a cada tick para suportar
    hot-swap de mapa.
    """

    def __init__(self, state: "SharedState") -> None:
        self._state = state

    def get_vision(self) -> VisionState:
        from app.sim.synthetic_vision import SyntheticVision
        from app.sim.world import SimWorld

        vision = self._state.sim_vision
        world = self._state.sim_world
        if not isinstance(vision, SyntheticVision) or not isinstance(world, SimWorld):
            return VisionState()

        return vision.compute_legacy(world)

    def get_all_detections(self) -> list:
        """Retorna todas as detecções para alimentar o EKF."""
        from app.sim.synthetic_vision import SyntheticVision
        from app.sim.world import SimWorld

        vision = self._state.sim_vision
        world = self._state.sim_world
        if not isinstance(vision, SyntheticVision) or not isinstance(world, SimWorld):
            return []

        return vision.compute_all(world)


def _feed_ekf_from_detections(state: SharedState, detections: list) -> None:
    """Alimenta o EKF com correções de tags detectadas.

    Também publica em ``state.detected_tags_cache`` TODAS as tags vistas (para
    a telemetria), inclusive as fora do mapa/sem mapa carregado — nesses casos
    a posição no mundo é ESTIMADA da pose do EKF + leitura relativa
    (``in_map=False``), o que ajuda a conferir a colocação física das tags.
    """
    detected_cache: list[DetectedTag] = []
    robot_heading = state.ekf.theta

    for det in detections:
        tag_spec = None
        position_id = getattr(det, 'position_id', None)
        tag_id = getattr(det, 'tag_id', -1)

        if state.world_model is not None:
            if position_id:
                tag_spec = state.world_model.get_tag_by_position_id(position_id)
                if tag_spec and tag_id >= 0:
                    state.world_model.resolve_tag_id(tag_id, position_id)

            if tag_spec is None and tag_id >= 0:
                tag_spec_by_id = state.world_model.get_position_for_tag_id(tag_id)
                if tag_spec_by_id is not None:
                    tag_spec = tag_spec_by_id

        z_m = getattr(det, 'z_m', 0.0)
        x_m_rel = getattr(det, 'x_m', 0.0)
        yaw_rad = getattr(det, 'yaw_rad', 0.0)
        quality = getattr(det, 'quality', 1.0)

        dist = math.sqrt(z_m**2 + x_m_rel**2)
        bearing_relative = math.atan2(x_m_rel, z_m)
        bearing_world = robot_heading + bearing_relative

        if tag_spec is not None:
            # tag − dist·direção = posição da LENTE (a medida é da lente).
            lens_x = tag_spec.x_m - dist * math.cos(bearing_world)
            lens_y = tag_spec.y_m - dist * math.sin(bearing_world)

            # Braço de alavanca lente→eixo (2026-07-07): a pose do EKF é o
            # CENTRO do robô (eixo das rodas); a lente fica
            # LENS_TO_AXLE_FORWARD_CM à frente dele. Sem esta conversão, cada
            # correção puxava a pose ~18 cm na direção errada — viés da ordem
            # do próprio standoff num corredor de 80 cm.
            fwd_m = config.LENS_TO_AXLE_FORWARD_CM / 100.0
            observed_x = lens_x - fwd_m * math.cos(robot_heading)
            observed_y = lens_y - fwd_m * math.sin(robot_heading)

            observed_theta = tag_spec.yaw_rad - yaw_rad - math.pi
            observed_theta = math.atan2(math.sin(observed_theta), math.cos(observed_theta))

            # DOCK em execução: NÃO corrigir o EKF por tag. O dock planeja a
            # rota no frame odométrico do instante do plano e executa nele;
            # uma correção no meio (tag fisicamente fora da posição do mapa,
            # ex.: teste de bancada) TELEPORTA a pose → o executor persegue um
            # alvo num frame que já não existe → curvas tortas e "engasgos"
            # (visto na bancada 2026-07-07). A missão continua corrigindo
            # normalmente — lá as tags estão nas posições do mapa.
            if not state.docker.is_docking:
                state.ekf.correct_apriltag(
                    observed_x=observed_x,
                    observed_y=observed_y,
                    observed_theta=observed_theta,
                    quality=quality,
                )
            world_x, world_y, in_map = tag_spec.x_m, tag_spec.y_m, True
        else:
            # Tag fora do mapa (ou sem mapa): posição estimada pela pose atual.
            world_x = state.ekf.x + dist * math.cos(bearing_world)
            world_y = state.ekf.y + dist * math.sin(bearing_world)
            in_map = False

        detected_cache.append(DetectedTag(
            tag_id=tag_id,
            position_id=position_id,
            x_m=round(world_x, 3),
            y_m=round(world_y, 3),
            quality=quality,
            z_cm=round(z_m * 100.0, 1),
            x_cm=round(x_m_rel * 100.0, 1),
            in_map=in_map,
        ))

    state.detected_tags_cache = detected_cache


async def vision_loop(state: SharedState, source: VisionSource) -> None:
    """Loop da tarefa de visão."""
    logger.info("Vision loop iniciado")

    try:
        get_all = getattr(source, "get_all_detections", None)
        # Câmera real: a leitura OpenCV bloqueia, então roda em thread para não
        # travar o event loop (melhoria de infra trazida de main, via to_thread).
        # SIM permanece síncrono (visão sintética é barata e evita corrida com o mundo).
        offload = isinstance(source, RealVisionSource)
        while True:
            if offload:
                vision_state = await asyncio.to_thread(source.get_vision)
            else:
                vision_state = source.get_vision()
            await state.update_vision(vision_state)

            if get_all is not None:
                detections = get_all()
                if detections:
                    _feed_ekf_from_detections(state, detections)

            await asyncio.sleep(1.0 / 20.0)
    except asyncio.CancelledError:
        logger.info("Vision loop cancelado")
    finally:
        if isinstance(source, RealVisionSource):
            source.release()
