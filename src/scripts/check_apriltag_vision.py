#!/usr/bin/env python3
"""Checagem curta da pipeline de visão com a imagem de AprilTags do repositório.

Uso:
    python scripts/check_apriltag_vision.py

Opcionalmente, informe outro caminho de imagem:
    python scripts/check_apriltag_vision.py --image ../images/april_tags_25h9.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "pi"))

from app.vision.detector import AprilTagDetector  # noqa: E402
from app.vision.pose import estimate_vision_state  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--image",
        type=Path,
        default=ROOT_DIR.parent / "images" / "april_tags_25h9.png",
        help="Caminho da imagem de teste",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/april_tags_25h9_annotated.png"),
        help="Arquivo de saída com a imagem anotada",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    frame = cv2.imread(str(args.image))
    if frame is None:
        print(f"Nao foi possivel ler a imagem: {args.image}")
        return 1

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    detector = AprilTagDetector()
    detections = detector.detect(gray)
    vision_state = estimate_vision_state(detections)

    print(f"imagem={args.image}")
    print(f"shape={frame.shape}")
    print(f"detections={len(detections)}")
    print(vision_state)

    for tag in detections:
        corners = tag.corners.astype(int)
        for i in range(4):
            p1 = tuple(corners[i])
            p2 = tuple(corners[(i + 1) % 4])
            cv2.line(frame, p1, p2, (0, 255, 0), 2)

        center = tuple(tag.center.astype(int))
        cv2.circle(frame, center, 5, (0, 0, 255), -1)
        cv2.putText(
            frame,
            f"ID {tag.tag_id}",
            (center[0], max(0, center[1] - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 0, 0),
            2,
        )

    cv2.imwrite(str(args.output), frame)
    print(f"annotated={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())