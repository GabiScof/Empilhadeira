#!/usr/bin/env bash
# Compila e grava o firmware do ESP32 via PlatformIO.
# Uso: ./scripts/flash_firmware.sh   (a partir da raiz do monorepo, src/)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "${ROOT_DIR}/firmware"
pio run -t upload
