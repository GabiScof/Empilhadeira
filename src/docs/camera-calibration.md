# Calibração da câmera

[ref: Seção 3 e Seção 8 da AGENTS.md]

A estimativa de pose da AprilTag (`pupil-apriltags`, família `tag25h9`) exige os
**parâmetros intrínsecos** da câmera: `fx`, `fy`, `cx`, `cy` e os coeficientes de
distorção. Eles são produzidos pela calibração e salvos em
[`../pi/calibracao/camera_intrinsics.json`](../pi/calibracao/camera_intrinsics.json).

> **Estado atual (2026-07-07): ⚠️ RECALIBRAÇÃO EM ANDAMENTO.** O arquivo contém a
> calibração OpenCV feita com 28 fotos **640×480** de `roboticaMengo/imagens/`
> (erro de reprojeção 0,144 px), mas os valores estão **suspeitos**: cx=399 e
> cy=273 são anômalos para 640×480 — cx é exatamente 800/2, o que sugere fotos
> tiradas em resolução errada. A equipe vai recalibrar (possivelmente com a
> webcam nova Logitech 1080p), **capturando em 640×480 e com foco travado**, e
> re-validar z/x com fita métrica depois. A captura em operação **tem** que rodar
> na resolução da calibração: `vision_loop` e `teste_cam` **forçam** o
> `image_size` anotado no JSON de calibração (os defaults
> `CAMERA_FRAME_WIDTH/HEIGHT=640/480` do config são só fallback) — capturar em
> resolução diferente invalida fx/fy/cx/cy silenciosamente (armadilha vista na
> bancada). Existe uma calibração alternativa (Zephyr, fx=fy=833) anotada no
> próprio JSON — o teste de fita métrica a 30 cm (ver `real-robot-test-plan.md`
> §1.4) decide qual fica.

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
> contrário `fx/fy/cx/cy` precisam ser reescalados. Em operação isso é garantido
> por código: `vision_loop`/`teste_cam` forçam a captura para o `image_size` do
> JSON de calibração.
