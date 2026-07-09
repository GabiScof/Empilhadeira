# Status de Verificação — Simulação e Testes

Última contagem: 2026-07-08 (achados das sessões de simulação, antes em `ACHADOS_SIM.md` e `ACHADOS_SIM_v2.md`).

---

O sistema está funcional e validado em simulação. A lógica de controle, missão,
navegação e telemetria roda identicamente em `SIM=1` e `SIM=0` — só mudam os encaixes
de hardware (câmera e serial).

| Verificação | Resultado |
|-------------|-----------|
| pytest (`pi/tests/`) | 210 testes — 209 passam, 1 pulado (contagem 2026-07-08) |
| vitest (`frontend/`) | 11/11 passam |
| `sim_sweep.py` (9 cenários) | 9/9 convergem |
| `full_trace.py` (13 cenários) | 12/13 convergem |
| Cenário `far_off25_h20` | LOST esperado — tag fora do FOV (offset 25 cm + heading 20° a 130 cm) |

---

## Bugs corrigidos (histórico)

### Runtime / integração (ACHADOS v1)

| # | Problema | Correção |
|---|----------|----------|
| 1 | APIs `/sim/*` retornavam HTTP 422 | Modelos Pydantic movidos para nível de módulo |
| 2 | WebSocket `/ws` retornava 404 | Dependência `websockets` adicionada (hoje suprida por `uvicorn[standard]`) |
| 3 | AUTOMATICO congelava após 1 comando | `control_loop.py` @20 Hz independente do frontend |
| 4 | PARADO oscilava sem latch | `_safety_latched` na máquina de estados |
| 5 | Fallback sequencial deadlock de rotação | Omega combinado X+pitch |
| 6 | PID integral não resetava em PARADO | Reset no emulador ao setpoint≈0 |
| 7 | ZREF=5 cm causava overshoot | Aumentado para 15 cm |
| 8 | Offset lateral perdia tag | Bearing guard + histerese + α_min + retreat bearing |

### Navegação / telemetria (ACHADOS v2)

| # | Problema | Correção |
|---|----------|----------|
| 1 | Omega bang-bang (NAV_KX × x_cm) | Bearing-based omega proporcional |
| 2 | Telemetria instável em MANUAL | Removido double-noise perto de 0° pitch |
| 3 | FACE durava 1-2 ticks | `_FACE_MIN_TICKS = 10` (0,5 s) |
| 4 | FACE→RETREAT glitch (0,0) | Transição direta com `-_RETREAT_SPEED` |
| 5 | Parada falsa a 24-25 cm | Dead zone com D + tolerâncias Z/pitch |
| 6 | `nav_phase` ausente no dashboard | Campo adicionado ao contrato de telemetria |
| 7 | Eventos escondidos em `<details>` | SafetyAlert sempre visível |

---

## Resultados de simulação (referência)

### sim_sweep — todos convergem

Distância final: 15,0–16,3 cm (ZREF=15). Offset lateral máx: ~2,4 cm. Heading error máx: ~3,7°.

### Navegação reativa vs path-following

Análise comparativa (Stanley, Pure Pursuit, bearing unificado) concluiu que o controlador
APPROACH/FACE/RETREAT com mode-switching é a abordagem adequada para robô diferencial
com câmera frontal. Detalhes em [`navigation.md`](./navigation.md).

---

## Cobertura de testes

| Área | Arquivo(s) | O que valida |
|------|------------|--------------|
| Loop de controle | `test_control_loop.py` (4; 1 pulado — ramo do navegador legado, dock ligado por padrão) | AUTOMATICO com 1 comando; latch perda tag |
| Navegação | `test_navigation.py` (31) | Bearing, FACE/RETREAT, fallback, dead zone |
| Missão | `test_mission.py` (10), `test_integration_mission.py` (5) | SM completa em 4 mapas + deriva sem visão |
| EKF | `test_ekf.py` (10) | Predição, correção, outlier rejection |
| Dock-to-tag | `test_dock_to_tag.py` (21) | Geometria, planejamento, SM, convergência < 5 cm |
| Gyro calibration | `test_gyro_calibration.py` (13) | Bias, auto-orientação, eixo, rastreamento |
| Segment executor | `test_segment_executor.py` (6) | FORWARD/TURN, tolerância, timeout |
| Hardware interfaces | `test_hardware_interfaces.py` (13) | Calibração, serial injetável |
| World state | `test_world_state.py` (3) | Modelo de mundo, arena bounds |
| Map schema | `test_map_schema.py` (12) | Validação JSON, tag uniqueness, edges |
| Firmware emulator | `test_firmware_emulator.py` (13) | PID, motor, garfo, watchdog, CRC |
| APIs sim | `test_sim_api.py` | OpenAPI requestBody correto |
| Integração E2E sim | `test_integration_sim.py` | Convergência ZREF, perda tag, manual |

**Gap conhecido:** não há teste E2E automatizado que suba uvicorn e dirija via WebSocket
real. Validado manualmente ao vivo; recomendado adicionar com `httpx`.

---

## Como reproduzir

```bash
cd src

# Suíte completa
python3 -m pytest pi/tests/ -v

# Cenários de navegação
python3 pi/tests/sim_sweep.py
python3 pi/tests/full_trace.py

# Backend sim + frontend
SIM=1 ./scripts/run_pi.sh
cd frontend && npm run dev   # /demo

# Verificação lint + testes + build
bash scripts/verify.sh
```

---

## Próximo passo: hardware real

Ver [`hardware-deployment.md`](./hardware-deployment.md) para o passo a passo completo
no robô físico.
