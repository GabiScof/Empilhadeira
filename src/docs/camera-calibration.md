# Calibração da câmera

[ref: Seção 3 e Seção 8 da AGENTS.md]

A estimativa de pose da AprilTag (`pupil-apriltags`, família `tag25h9`) exige os
**parâmetros intrínsecos** da câmera: `fx`, `fy`, `cx`, `cy` e os coeficientes de
distorção. Eles são produzidos pela calibração e salvos em
[`../pi/calibracao/camera_intrinsics.json`](../pi/calibracao/camera_intrinsics.json).

> **Estado atual:** o arquivo nasce com `fx/fy/cx/cy = null` (placeholder).
> A calibração real é **`TODO(equipe)`** — sem ela, a estimativa de pose não roda.

## Opção A — Checkerboard (xadrez) com OpenCV

1. Imprima um padrão de xadrez (checkerboard) e fixe-o numa superfície plana e rígida.
2. Anote o número de **cantos internos** (ex.: tabuleiro 9×6 quadrados → 8×5 cantos)
   e o **tamanho do quadrado** em metros.
3. Tire **10–15 fotos** do padrão em ângulos e distâncias variados, com a **mesma
   câmera e resolução** que serão usadas no robô.
4. Rode `cv2.findChessboardCorners` + `cv2.calibrateCamera` para obter a matriz da
   câmera e os coeficientes de distorção.
5. Extraia `fx = K[0,0]`, `fy = K[1,1]`, `cx = K[0,2]`, `cy = K[1,2]`.
6. Verifique o **erro de reprojeção** (idealmente < 0,5 px).
7. Salve em `camera_intrinsics.json` no formato esperado (ver abaixo).

> Há um script de referência em `../../roboticaMengo/calibration.py` que executa
> exatamente esse fluxo e gera um JSON compatível.

## Opção B — 3DF Zephyr

Alternativa de calibração fotogramétrica. Documentar passo a passo quando a equipe
definir a câmera. **`TODO(equipe)`**.

## Formato esperado de `camera_intrinsics.json`

```jsonc
{
  "fx": null,            // float — distância focal x (px)
  "fy": null,            // float — distância focal y (px)
  "cx": null,            // float — centro óptico x (px)
  "cy": null,            // float — centro óptico y (px)
  "dist_coeffs": null,   // [float, ...] — coeficientes de distorção
  "image_size": null,    // [largura, altura] (px) da calibração
  "reprojection_error": null
}
```

> A resolução de calibração deve casar com a resolução usada em operação; caso
> contrário `fx/fy/cx/cy` precisam ser reescalados.
