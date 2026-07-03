#!/usr/bin/env python3
"""Teste de bancada: envia setpoint ao ESP32 via UART e imprime os sensores.

Fase 1 do plano de testes (docs/real-robot-test-plan.md) — RODAS NO AR.
Valida, sem subir o backend: sentido dos motores, sinal dos encoders,
garfo e watchdog (< 200 ms ao interromper com Ctrl-C).

Uso (a partir de src/):
    python3 scripts/bench_setpoint.py                        # 2 rad/s frente, 5 s
    python3 scripts/bench_setpoint.py --w-esq 2 --w-dir 2 --seconds 5
    python3 scripts/bench_setpoint.py --garfo subir --seconds 2
    python3 scripts/bench_setpoint.py --port /dev/ttyACM0

O que observar:
  - As DUAS rodas giram para FRENTE com w positivo (senão: MOTOR_*_INV em
    firmware/src/config.h).
  - enc.esq / enc.dir convergem para ~w comandado e POSITIVOS (senão:
    ENC_*_INV; sempre zero no direito = falta pull-up externo em GPIO 34/35).
  - Ao encerrar (Ctrl-C ou fim do tempo), os motores devem parar sozinhos em
    < 200 ms (watchdog SETPOINT_TIMEOUT_MS do firmware).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pi"))

import serial  # noqa: E402

from app.comms.protocol import SensorsFrameDecoder, encode_setpoint  # noqa: E402
from app.models import Setpoint  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="/dev/ttyUSB0", help="porta serial do ESP32")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--w-esq", type=float, default=2.0, help="rad/s roda esquerda")
    parser.add_argument("--w-dir", type=float, default=2.0, help="rad/s roda direita")
    parser.add_argument(
        "--garfo", choices=["subir", "descer", "parar"], default="parar"
    )
    parser.add_argument("--seconds", type=float, default=5.0, help="duração do teste")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        port = serial.Serial(args.port, args.baud, timeout=0.05)
    except serial.SerialException as exc:
        print(f"[ERRO] Não abriu {args.port}: {exc}")
        print("       Confira a porta (ls /dev/ttyUSB* /dev/ttyACM*) e a permissão")
        print("       (sudo usermod -aG dialout $USER && relogar).")
        return 1

    setpoint = Setpoint(w_esq=args.w_esq, w_dir=args.w_dir, garfo=args.garfo)
    frame = encode_setpoint(setpoint)
    decoder = SensorsFrameDecoder()

    print(
        f"[OK] {args.port} @ {args.baud}. Enviando w_esq={args.w_esq} "
        f"w_dir={args.w_dir} garfo={args.garfo} por {args.seconds:.1f} s @ 20 Hz."
    )
    print("     Ctrl-C encerra — os motores devem parar sozinhos em < 200 ms.\n")

    deadline = time.monotonic() + args.seconds
    frames_rx = 0
    try:
        while time.monotonic() < deadline:
            port.write(frame)
            time.sleep(0.05)  # 20 Hz
            for sensors in decoder.feed(port.read(4096)):
                frames_rx += 1
                if frames_rx % 5 == 0:  # imprime a ~4 Hz para não inundar
                    mpu = sensors.mpu
                    print(
                        f"enc esq={sensors.enc.esq:+6.2f} dir={sensors.enc.dir:+6.2f} rad/s"
                        f"  |  mpu az={mpu.az:5.2f} gz={mpu.gz:+7.2f}"
                    )
    except KeyboardInterrupt:
        print("\n[Ctrl-C] Parando de enviar — cronometre: motores devem parar < 200 ms.")
    finally:
        port.close()

    if frames_rx == 0:
        print("\n[FALHA] Nenhum frame de sensores recebido.")
        print("        Baudrate? TX/RX invertidos? Firmware gravado? CRC?")
        return 1

    print(f"\n[OK] {frames_rx} frames de sensores válidos recebidos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
