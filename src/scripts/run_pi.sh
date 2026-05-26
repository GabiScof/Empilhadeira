#!/usr/bin/env bash
# Sobe o backend do Raspberry Pi (FastAPI/uvicorn).
# Uso: ./scripts/run_pi.sh   (a partir da raiz do monorepo, src/)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Carrega variaveis do .env, se existir.
if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

cd "${ROOT_DIR}/pi"
exec uvicorn app.main:create_app --factory \
  --host "${PI_HOST:-0.0.0.0}" \
  --port "${PI_PORT:-8000}"
