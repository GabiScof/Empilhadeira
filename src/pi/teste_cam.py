"""Teste isolado da câmera + detecção de AprilTag.

Roda de forma totalmente independente do resto da aplicação (sem SharedState,
EKF, world model ou asyncio): abre a câmera, detecta AprilTags e mostra o vídeo
com as tags desenhadas. Serve para validar rapidamente que a câmera abre, que a
calibração carrega e que as tags são reconhecidas.

A saída imprime a ``VisionState`` COMPLETA (z_cm / x_cm / pitch_deg) calculada
pelo MESMO pipeline que o backend usa (``estimate_vision_state`` em
app/vision/pose.py, com a negação do x do frame OpenCV e o offset
câmera→garfo) — ou seja, o que aparece aqui é exatamente o que a navegação vai
consumir. Convenções (validar nos checks do 1.4 do real-robot-test-plan):
  - z_cm: distância à frente (fita métrica confere).
  - x_cm: POSITIVO = tag à ESQUERDA do centro da imagem.
  - pitch_deg: rotação da tag no eixo vertical (anotar sinal — check 6).

Uso:
    python teste_cam.py                # abre janela com o vídeo
    python teste_cam.py --janela       # FORÇA a janela (ignora HEADLESS do ambiente)
    python teste_cam.py --headless     # sem janela (só imprime no terminal, p/ SSH)
    HEADLESS=1 python teste_cam.py     # idem --headless, via ambiente
    (índice da câmera: FIXADO em app/config.py — CAMERA_INDEX=1, sem env)

Prioridade: flag de linha de comando > variável de ambiente. Se o HEADLESS=1
ficou exportado no shell, `--janela` sobrepõe sem precisar mexer no ambiente.

Teclas na janela: 'q' ou ESC para sair.
"""

from __future__ import annotations

import argparse
import os

import cv2
import numpy as np

from app import config
from app.vision.pose import estimate_vision_state


def _check_cv2_videoio() -> None:
    """Falha cedo e com mensagem útil se o cv2 não tiver o VideoCapture.

    Numa instalação sã (inclusive headless) o VideoCapture existe. Se sumiu, o
    pacote está quebrado/parcial ou há dois opencv brigando — não é problema da
    câmera nem deste script.
    """
    if hasattr(cv2, "VideoCapture"):
        return
    raise RuntimeError(
        "cv2 sem VideoCapture — instalação do OpenCV quebrada ou duplicada "
        f"(cv2 em {getattr(cv2, '__file__', '?')}). Conserte com:\n"
        "  pip uninstall -y opencv-python opencv-python-headless "
        "opencv-contrib-python opencv-contrib-python-headless\n"
        "  pip install --upgrade opencv-python-headless\n"
        "(ou: sudo apt install python3-opencv). O 'headless' NÃO remove o "
        "VideoCapture — só a janela (imshow)."
    )


def _gui_available() -> bool:
    """Testa se a build do OpenCV tem suporte a janela (imshow/highgui)."""
    try:
        cv2.namedWindow("__probe__")
        cv2.destroyWindow("__probe__")
        return True
    except cv2.error:
        return False


def _build_detector():
    """Cria o detector de AprilTag, usando a calibração se disponível."""
    from app.vision.calibration import CalibrationError
    from app.vision.detector import AprilTagDetector

    try:
        detector = AprilTagDetector.from_calibration()
        print("[OK] Detector criado com calibração da câmera.")
    except CalibrationError as exc:
        print(f"[AVISO] Câmera não calibrada, usando placeholders ({exc}).")
        detector = AprilTagDetector()
    return detector


def _open_camera() -> cv2.VideoCapture:
    """Abre a câmera FORÇANDO a resolução da calibração.

    Os intrínsecos (fx/fy/cx/cy) só valem na resolução em que a câmera foi
    calibrada. Capturar em outra (ex.: default 1280x720 quando o .env não foi
    carregado) produz z/x silenciosamente errados — armadilha vista na bancada
    em 2026-07-07. Por isso a resolução da calibração tem prioridade sobre o
    config/env aqui.
    """
    from app.vision.calibration import calibration_image_size

    cal_size = calibration_image_size()
    width, height = cal_size or (config.CAMERA_FRAME_WIDTH, config.CAMERA_FRAME_HEIGHT)
    if cal_size and cal_size != (config.CAMERA_FRAME_WIDTH, config.CAMERA_FRAME_HEIGHT):
        print(
            f"[AVISO] Config/env pedia {config.CAMERA_FRAME_WIDTH}x"
            f"{config.CAMERA_FRAME_HEIGHT}, mas a calibração é "
            f"{cal_size[0]}x{cal_size[1]} — usando a da CALIBRAÇÃO."
        )

    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    if not cap.isOpened():
        raise RuntimeError(
            f"Câmera não abriu (índice {config.CAMERA_INDEX}). "
            "Verifique a conexão e as permissões de câmera do sistema."
        )

    real_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    real_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[OK] Câmera aberta (índice {config.CAMERA_INDEX}, {real_w}x{real_h}).")
    if (real_w, real_h) != (width, height):
        print(
            f"[ERRO] A câmera NÃO aceitou {width}x{height} (entregou "
            f"{real_w}x{real_h}) — os z/x abaixo NÃO são confiáveis. "
            "Ajuste a resolução suportada ou recalibre nessa resolução."
        )
    return cap


def _draw_detection(frame: np.ndarray, det) -> None:
    """Desenha o contorno, o ID e a distância de uma tag no frame."""
    corners = det.corners.astype(int)
    cv2.polylines(frame, [corners], isClosed=True, color=(0, 255, 0), thickness=2)

    cx, cy = int(det.center[0]), int(det.center[1])
    label = f"id={det.tag_id}"
    if getattr(det, "pose_t", None) is not None:
        dist_m = float(np.linalg.norm(det.pose_t))
        label += f" {dist_m:.2f}m"

    cv2.putText(
        frame, label, (cx - 20, cy),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Teste da câmera + AprilTag.")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument(
        "--janela", action="store_true",
        help="força o modo com janela (sobrepõe HEADLESS=1 do ambiente)",
    )
    grupo.add_argument(
        "--headless", action="store_true",
        help="força o modo sem janela (só terminal)",
    )
    args = parser.parse_args()

    if args.janela:
        headless = False
    elif args.headless:
        headless = True
    else:
        headless = os.getenv("HEADLESS", "0") == "1"

    _check_cv2_videoio()

    # Sem tela (Pi via SSH) ou build sem GUI → cai pra headless automaticamente.
    if not headless and not _gui_available():
        print("[AVISO] OpenCV sem suporte a janela (imshow). Rodando em modo "
              "headless — defina HEADLESS=1 para silenciar este aviso.")
        headless = True

    detector = _build_detector()
    cap = _open_camera()
    frame_count = 0

    print("Rodando. " + ("Ctrl+C para sair." if headless else "'q' ou ESC para sair."))
    try:
        while True:
            read_ok, frame = cap.read()
            if not read_ok:
                print("[AVISO] Falha ao ler frame da câmera.")
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            detections = detector.detect(gray)

            # VisionState pelo pipeline REAL do backend (pose.py): melhor tag,
            # x já na convenção do projeto (positivo = esquerda) e offset
            # câmera→garfo aplicado. É o que a navegação consome.
            vision = estimate_vision_state(detections)

            frame_count += 1
            if headless:
                # ~4 linhas/s para não inundar o terminal via SSH.
                if vision.detectado and frame_count % 5 == 0:
                    others = (
                        f"  (+{len(detections) - 1} tag(s))"
                        if len(detections) > 1
                        else ""
                    )
                    print(
                        f"id={vision.id}  z={vision.z_cm:6.1f}cm  "
                        f"x={vision.x_cm:+6.1f}cm  pitch={vision.pitch_deg:+6.1f}°"
                        f"{others}"
                    )
                continue

            for det in detections:
                _draw_detection(frame, det)
            hud = f"tags: {len(detections)}"
            if vision.detectado:
                hud += (
                    f"  id={vision.id} z={vision.z_cm:.1f}cm "
                    f"x={vision.x_cm:+.1f}cm pitch={vision.pitch_deg:+.1f}"
                )
            cv2.putText(
                frame, hud, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2,
            )

            cv2.imshow("teste_cam - AprilTag", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):  # 'q' ou ESC
                break
    except KeyboardInterrupt:
        print("\nEncerrado pelo usuário (Ctrl+C).")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("Câmera liberada.")


if __name__ == "__main__":
    main()
