# Empilhadeira Robótica Autônoma

Empilhadeira em escala reduzida que transporta pallets (~15 cm) em ambiente controlado.

- **Manual** — joystick virtual no celular
- **Autônomo** — detecta AprilTag, navega por mapa, executa missão pick-and-place
- **Garfo sempre manual** — canal independente nos dois modos

## Arquitetura

```
Celular (React)  ←WebSocket 20Hz→  Raspberry Pi (Python/FastAPI)
                                        ↕ UART 115200 JSON+CRC8
                                   ESP32 (C++/PID 100Hz)
```

Documentação completa em [`src/README.md`](src/README.md).

## Quick start

```bash
cd src
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Simulação (sem hardware)
SIM=1 ./scripts/run_pi.sh

# Frontend
cd frontend && npm install && npm run dev   # http://localhost:5173/demo

# Testes
python3 -m pytest pi/tests/ -v              # 162 testes
```

## Deploy no robô real

Guia operacional: [`src/docs/hardware-deployment.md`](src/docs/hardware-deployment.md)

Simulador → robô real: [`src/docs/readiness-sim-to-real.md`](src/docs/readiness-sim-to-real.md)

## Status

| Item | Estado |
|------|--------|
| Lógica + simulação | ✅ Validado (162 pytest + sim_sweep 9/9) |
| Firmware ESP32 | ✅ Pronto para gravar |
| Interfaces Pi (câmera + serial) | ✅ Implementadas |
| Calibração câmera + mapa real | ❌ Pendente equipe |
| Teste UART no chão | ❌ Pendente equipe |

Detalhes: [`src/docs/verification-status.md`](src/docs/verification-status.md)
