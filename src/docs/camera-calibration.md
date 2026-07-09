# Calibração da câmera

A estimativa de pose da AprilTag (`pupil-apriltags`, família `tag25h9`) exige os
**parâmetros intrínsecos** da câmera: `fx`, `fy`, `cx`, `cy` e os coeficientes de
distorção. Eles são produzidos pela calibração e salvos em
[`../pi/calibracao/camera_intrinsics.json`](../pi/calibracao/camera_intrinsics.json).

> **Estado atual (2026-07-07):** 2ª calibração com a câmera nova, pós-remontagem
> com tilt de 30°, em 1280×720 (cantos 8×5, quadrado 3 cm). Intrínsecos:
> fx=fy=1023,63, cx=634,08, cy=377,08 — coerentes com 1280×720 (cx/cy a poucos
> pixels do centro geométrico). Coeficientes de distorção:
> [0,0403, −0,0243, 0,0029, −0,0019, −0,0493]. Erro de reprojeção não
> registrado no JSON.
>
> Histórico: a calibração da câmera antiga (640×480, 28 fotos, erro de
> reprojeção 0,144 px) foi descartada — cx=399 era anômalo para 640×480,
> indício de fotos capturadas em resolução errada. A 1ª calibração da câmera
> nova (fx=fy=998,17) também foi substituída pela recalibração de 2026-07-07.
>
> A captura em operação precisa rodar na resolução da calibração
> (`CAMERA_FRAME_WIDTH=1280`, `CAMERA_FRAME_HEIGHT=720` em config):
> `vision_loop` e `teste_cam` forçam o `image_size` anotado no JSON de
> calibração — capturar em resolução diferente invalida fx/fy/cx/cy
> silenciosamente (problema observado na bancada).

## Opção A — Checkerboard (xadrez) com OpenCV

1. Imprima um padrão de xadrez (checkerboard) e fixe-o numa superfície plana e rígida.
2. Anote o número de cantos internos (ex.: tabuleiro 9×6 quadrados → 8×5 cantos)
   e o tamanho do quadrado em metros.
3. Tire 10–15 fotos do padrão em ângulos e distâncias variados, com a mesma
   câmera e resolução que serão usadas no robô.
4. Rode `cv2.findChessboardCorners` + `cv2.calibrateCamera` para obter a matriz da
   câmera e os coeficientes de distorção.
5. Extraia `fx = K[0,0]`, `fy = K[1,1]`, `cx = K[0,2]`, `cy = K[1,2]`.
6. Verifique o erro de reprojeção (idealmente < 0,5 px).
7. Salve em `camera_intrinsics.json` no formato esperado (ver abaixo).

## Opção B — 3DF Zephyr

Alternativa de calibração fotogramétrica. Passo a passo não documentado.
`TODO(equipe)`.

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
> contrário `fx/fy/cx/cy` precisam ser reescalados. `vision_loop`/`teste_cam`
> forçam a captura para o `image_size` do JSON de calibração.
