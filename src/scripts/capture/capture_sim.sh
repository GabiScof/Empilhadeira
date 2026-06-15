#!/bin/bash
# Captura artefatos de simulação para o RELATORIO_SIM.md.
#
# Uso:
#   1. Suba o backend em modo SIM:
#      cd src && SIM=1 uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
#   2. Suba o frontend:
#      cd src/frontend && npm run dev
#   3. Execute este script:
#      bash scripts/capture/capture_sim.sh
#
# Requer: curl (para APIs do backend sim)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/../../artifacts"
API="http://localhost:8000"

mkdir -p "$OUTPUT_DIR"

echo "=== Captura de artefatos de simulação ==="

echo "[1/5] Verificando backend sim..."
if ! curl -s "$API/sim/world-state" > /dev/null 2>&1; then
    echo "ERRO: Backend não está rodando em modo SIM. Suba com SIM=1."
    exit 1
fi

echo "[2/5] Capturando estado inicial do mundo..."
curl -s "$API/sim/world-state" | python3 -m json.tool > "$OUTPUT_DIR/world_state_initial.json"

echo "[3/5] Testando reset de pose..."
curl -s -X POST "$API/sim/reset-pose" \
    -H "Content-Type: application/json" \
    -d '{"x": 50, "y": 150, "theta": 0}' > "$OUTPUT_DIR/pose_reset_result.json"

echo "[4/5] Testando injeção de falha (tag oculta)..."
curl -s -X POST "$API/sim/inject-fault" \
    -H "Content-Type: application/json" \
    -d '{"fault_type": "tag_hidden", "active": true}' > "$OUTPUT_DIR/fault_inject_tag.json"

curl -s -X POST "$API/sim/inject-fault" \
    -H "Content-Type: application/json" \
    -d '{"fault_type": "clear_all", "active": false}' > "$OUTPUT_DIR/fault_clear.json"

echo "[5/5] Capturando estado final..."
curl -s "$API/sim/world-state" | python3 -m json.tool > "$OUTPUT_DIR/world_state_final.json"

echo ""
echo "=== Artefatos salvos em $OUTPUT_DIR ==="
ls -la "$OUTPUT_DIR/"
echo ""
echo "Para screenshots do frontend, use Playwright ou capture manualmente via navegador."
