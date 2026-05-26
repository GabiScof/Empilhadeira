"""Tarefas asyncio concorrentes do backend do Pi.

- websocket_handler: troca comando/telemetria com o frontend.
- vision_loop: captura, detecção de AprilTag e estimativa de pose.
- serial_loop: troca setpoint/sensores com o ESP32 via UART.
"""
