"""Tarefa serial: troca setpoint/sensores com o ESP32 via UART @20 Hz.

Responsabilidades:
- Calcular o setpoint (contrato 3) a partir do estado (manual: cinemática do
  joystick; automático: navegação) e enviá-lo emoldurado (JSON+CRC8+\\n).
- Receber e decodificar sensores (contrato 4), atualizar o estado compartilhado.
- Aplicar a fusão de Kalman sobre o MPU cru → roll/pitch.
- **Watchdog serial**: se a serial cair, o ESP32 zera os motores localmente; o Pi
  deve detectar a ausência de sensores e refletir estado seguro. [ref: Seção 7]

Usa `pyserial-asyncio`. [ref: Seção 2 da AGENTS.md]
"""

from __future__ import annotations

from app.state import SharedState


async def serial_loop(state: SharedState) -> None:
    """Loop da tarefa serial (setpoint out / sensores in).

    Args:
        state: estado compartilhado entre as tarefas.
    """
    raise NotImplementedError
