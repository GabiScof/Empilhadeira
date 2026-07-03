"""Contratos de hardware (encaixes SIM ↔ real) — ver ``interfaces.py``."""

from app.hardware.interfaces import SerialTransport, VisionSource

__all__ = ["SerialTransport", "VisionSource"]
