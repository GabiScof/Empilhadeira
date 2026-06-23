# Simulação (`SIM=1`)

[ref: `pi/app/main.py`, `pi/app/sim/`, `pi/app/config.py`]

## Visão Geral

O backend do Pi pode rodar **sem hardware físico** quando `SIM=1` no ambiente.
Nesse modo, o ESP32, a câmera e o mundo físico são substituídos por componentes
Python que espelham o comportamento real com fidelidade suficiente para
desenvolver navegação, missão e UI.

```bash
# .env ou linha de comando
SIM=1
MAP=corredor_pequeno   # mapa padrão (opcional)
```

Subir o backend:

```bash
cd src/pi
SIM=1 python -m app.main
```

Frontend de demo: `npm run dev` em `frontend/` → página `/demo`.

## O que é Real vs Emulado

| Componente | SIM=1 | SIM=0 (real) |
|------------|-------|--------------|
| FastAPI + WebSocket | ✅ real | ✅ real |
| Control Loop (20 Hz) | ✅ real | ✅ real |
| Mission SM + PathPlanner | ✅ real | ✅ real |
| EKF 2D | ✅ real | ✅ real |
| Serial UART | ❌ emulado | ✅ pyserial-asyncio |
| PID por roda (~100 Hz) | ❌ `FirmwareEmulator` | ✅ ESP32 |
| Encoders / MPU-6050 | ❌ sintéticos | ✅ ESP32 |
| Câmera / AprilTag | ❌ `SyntheticVision` | ✅ OpenCV + pupil-apriltags |
| Mundo físico | ❌ `SimWorld` paramétrico | ✅ arena real |
| Garfo + fim-de-curso | ❌ emulado (altura 0–10 cm) | ✅ ESP32 + switches |
| BMS | ❌ null ou injetado | ✅ se conectado |

### Cadeia de Simulação

```
Control Loop (20 Hz)
    ↓ Setpoint
Serial Loop (SIM) ──► FirmwareEmulator (PID 100 Hz)
                           ↓
                      SimWorld (cinemática + slip)
                           ↓ pose
Vision Loop (SIM) ──► SyntheticVision (PnP sintético)
                           ↓ detecção
                      EKF correct_apriltag()
```

O emulador de firmware (`firmware_emulator.py`) replica fielmente:

- PID Kp=20, Ki=5, Kd=1, anti-windup ±500
- Motor 1ª ordem (τ ≈ 50 ms), saturação ~12.25 rad/s
- Encoder PPR=360, watchdog 200 ms
- Garfo com duty fixo 180 e limites topo/base

## Mapas na Simulação

Ao iniciar com `SIM=1`:

1. Carrega `DEFAULT_MAP` de `config.py` (ou `MAP` do `.env`)
2. Cria `WorldModel` → `SimWorld` com dimensões e tags do JSON
3. Posiciona o robô em `start_pose`
4. Inicializa o EKF na mesma pose

Trocar mapa em runtime:

```bash
curl -X POST http://localhost:8000/maps/load/arena_media
```

Reinicializa mundo, emulador e visão sintética sem reiniciar o servidor.

## Injeção de Falhas

Disponível apenas em `SIM=1` via `POST /sim/inject-fault`:

| `fault_type` | Parâmetros | Efeito |
|--------------|------------|--------|
| `serial_drop` | `active: bool` | Emulador para de responder → watchdog ESP32 |
| `tag_hidden` | `active: bool` | Visão sintética retorna não-detecção |
| `wheel_slip` | `value`, `value2` | Multiplicadores de slip esq/dir |
| `battery_saturated` | `active: bool` | Dados BMS falsos |
| `vision_blur` | `value` (prob) | Probabilidade de blur por frame |
| `vision_drop` | `value` (prob) | Probabilidade de drop (sem detecção) |
| `encoder_noise` | `value` (std) | Ruído gaussiano nos encoders |
| `gyro_drift` | `value` (rad/s) | Drift constante no giroscópio |
| `clear_all` | — | Remove todas as falhas |

A UI expõe esses controles via `FaultInjector.jsx` na página de demo.

### Exemplo

```bash
curl -X POST http://localhost:8000/sim/inject-fault \
  -H "Content-Type: application/json" \
  -d '{"fault_type": "wheel_slip", "value": 0.5, "value2": 1.0}'
```

## Rotas de Debug (SIM)

| Rota | Descrição |
|------|-----------|
| `POST /sim/reset-pose` | Reposiciona robô e reseta EKF |
| `GET /sim/world-state` | Pose, EKF, missão, executor, trail |
| `GET /sim/debug-dump` | Snapshot completo para exportação |
| `GET /maps/list` | Lista mapas disponíveis |
| `POST /maps/load/{name}` | Troca mapa |

## Matriz de Testes

### Testes Unitários

| Arquivo | O que valida |
|---------|--------------|
| `test_map_schema.py` | Schema JSON, validações |
| `test_mission.py` | Transições MissionSM |
| `test_path_planner.py` | A*, Manhattan, segmentos |
| `test_navigation.py` | NavigationController legado |
| `test_crc8.py` / `test_protocol.py` | Framing serial |
| `test_kinematics.py` | Cinemática diferencial |

### Testes de Integração (SIM)

| Arquivo | Cenário |
|---------|---------|
| `test_integration_sim.py` | AUTO converge a Zref; watchdog serial |
| `test_integration_mission.py` | Missão pick-and-place end-to-end |
| `test_sim_api.py` | Rotas REST de simulação |
| `test_vision_sim.py` | SyntheticVision + ruído |

### Scripts de Traçado

| Script | Uso |
|--------|-----|
| `sim_trace.py` | Trajetória curta com log |
| `full_trace.py` | Trajetória longa com métricas |
| `sim_sweep.py` | Varredura de parâmetros |
| `compare_nav.py` | Compara NavigationController vs Stanley |

Executar a suíte completa:

```bash
cd src/pi
pytest tests/ -v
```

## Ruído e Realismo

Parâmetros configuráveis em `config.py`:

| Constante | Default | Descrição |
|-----------|---------|-----------|
| `SIM_VISION_NOISE_STD_CM` | 0.2 | Ruído de posição (cm) |
| `SIM_VISION_NOISE_STD_DEG` | 0.5 | Ruído angular (°) |
| `SIM_VISION_FOV_H_DEG` | 60 | Campo de visão horizontal |
| `SIM_VISION_MIN_RANGE` | 3 cm | Distância mínima de detecção |
| `SIM_VISION_MAX_RANGE` | 150 cm | Distância máxima de detecção |
| `SIM_ENCODER_NOISE_STD` | 0.05 | Ruído encoder (rad/s) |
| `SIM_GYRO_DRIFT_RADS` | 0.001 | Drift giroscópio (rad/s) |
| `SIM_DEFAULT_SEED` | 42 | Seed para sorteio de missão |

## Limitações da Simulação

- Não modela dinâmica 3D (pitch/roll do chassi)
- Slip modelado como multiplicador escalar, não física de contato
- Visão sintética não simula motion blur real — apenas probabilidade de drop
- Garfo emulado não interage com pallets (sem física de carga)
- Latência de rede Wi-Fi não é simulada

Para validação final, sempre testar em hardware real (`SIM=0`).

## Transição SIM → Real

Ver [`simulator-to-real.md`](./simulator-to-real.md) — **documento completo** sobre o que
foizemos no simulador, o que aproveitamos no robô e o que precisa recalibrar.

Resumo operacional: [`hardware-deployment.md`](./hardware-deployment.md).
