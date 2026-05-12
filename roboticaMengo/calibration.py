"""
Calibração de câmera usando padrão de xadrez (checkerboard) com OpenCV.

Este script:
- Lê várias imagens de calibração
- Detecta os cantos do tabuleiro
- Calcula os parâmetros intrínsecos da câmera
- Retorna:
    fx, fy, cx, cy
    matriz da câmera
    coeficientes de distorção

Compatível posteriormente com:
- pupil-apriltags
- apriltag
- OpenCV pose estimation

Instalação:
pip install opencv-python numpy

Uso:
1. Tire várias fotos de um checkerboard em ângulos diferentes
2. Coloque as imagens em uma pasta
3. Ajuste os parâmetros CHECKERBOARD abaixo
4. Rode:
   python calibrar_camera.py
"""

import cv2
import numpy as np
import glob
import json

# ==========================================================
# CONFIGURAÇÕES
# ==========================================================

# Número de cantos internos do checkerboard
# Exemplo:
# tabuleiro 9x6 quadrados -> 8x5 cantos internos
CHECKERBOARD = (8, 5)

# Tamanho do quadrado em metros (ou qualquer unidade)
# Não afeta os parâmetros intrínsecos,
# apenas escala de pose futura
SQUARE_SIZE = 0.03  # 2.5 cm

# Pasta com imagens
IMAGE_PATH = "imagens/*.jpg"

# ==========================================================
# PREPARAÇÃO DOS PONTOS 3D
# ==========================================================

objp = np.zeros((CHECKERBOARD[0] * CHECKERBOARD[1], 3), np.float32)

objp[:, :2] = (
    np.mgrid[0:CHECKERBOARD[0], 0:CHECKERBOARD[1]]
    .T.reshape(-1, 2)
)

objp *= SQUARE_SIZE

# Pontos 3D reais
objpoints = []

# Pontos 2D detectados na imagem
imgpoints = []

# ==========================================================
# LEITURA DAS IMAGENS
# ==========================================================

images = glob.glob(IMAGE_PATH)

if len(images) == 0:
    raise Exception("Nenhuma imagem encontrada.")

print(f"{len(images)} imagens encontradas.\n")

image_size = None

for fname in images:

    img = cv2.imread(fname)

    if img is None:
        print(f"Erro ao abrir: {fname}")
        continue

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    image_size = gray.shape[::-1]

    # Detecta cantos
    ret, corners = cv2.findChessboardCorners(
        gray,
        CHECKERBOARD,
        cv2.CALIB_CB_ADAPTIVE_THRESH
        + cv2.CALIB_CB_FAST_CHECK
        + cv2.CALIB_CB_NORMALIZE_IMAGE,
    )

    if ret:

        # Refinamento subpixel
        criteria = (
            cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
            30,
            0.001,
        )

        corners2 = cv2.cornerSubPix(
            gray,
            corners,
            (11, 11),
            (-1, -1),
            criteria,
        )

        objpoints.append(objp)
        imgpoints.append(corners2)

        print(f"[OK] Cantos detectados: {fname}")

    else:
        print(f"[ERRO] Checkerboard não detectado: {fname}")

# ==========================================================
# CALIBRAÇÃO
# ==========================================================

if len(objpoints) < 5:
    raise Exception(
        "Poucas imagens válidas para calibração. "
        "Use pelo menos 10-15 imagens."
    )

ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
    objpoints,
    imgpoints,
    image_size,
    None,
    None,
)

# ==========================================================
# EXTRAÇÃO DOS PARÂMETROS
# ==========================================================

fx = camera_matrix[0, 0]
fy = camera_matrix[1, 1]
cx = camera_matrix[0, 2]
cy = camera_matrix[1, 2]

# ==========================================================
# RESULTADOS
# ==========================================================

print("\n==============================")
print("PARÂMETROS DA CÂMERA")
print("==============================\n")

print(f"fx = {fx}")
print(f"fy = {fy}")
print(f"cx = {cx}")
print(f"cy = {cy}")

print("\nMatriz da câmera:\n")
print(camera_matrix)

print("\nCoeficientes de distorção:\n")
print(dist_coeffs)

# ==========================================================
# ERRO DE REPROJEÇÃO
# ==========================================================

mean_error = 0

for i in range(len(objpoints)):
    imgpoints2, _ = cv2.projectPoints(
        objpoints[i],
        rvecs[i],
        tvecs[i],
        camera_matrix,
        dist_coeffs,
    )

    error = cv2.norm(
        imgpoints[i],
        imgpoints2,
        cv2.NORM_L2
    ) / len(imgpoints2)

    mean_error += error

mean_error /= len(objpoints)

print(f"\nErro médio de reprojeção: {mean_error}")

# ==========================================================
# SALVAR EM JSON
# ==========================================================

output = {
    "fx": float(fx),
    "fy": float(fy),
    "cx": float(cx),
    "cy": float(cy),
    "camera_matrix": camera_matrix.tolist(),
    "dist_coeffs": dist_coeffs.tolist(),
    "reprojection_error": float(mean_error),
}

with open("camera_calibration.json", "w") as f:
    json.dump(output, f, indent=4)

print("\nParâmetros salvos em:")
print("camera_calibration.json")

# ==========================================================
# EXEMPLO FUTURO COM pupil-apriltags
# ==========================================================

"""
Depois você poderá usar:

camera_params = [fx, fy, cx, cy]

Exemplo:

from pupil_apriltags import Detector

detector = Detector()

results = detector.detect(
    gray,
    estimate_tag_pose=True,
    camera_params=[fx, fy, cx, cy],
    tag_size=0.16
)
"""