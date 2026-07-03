#!/bin/bash
# Verificação completa do projeto: lint, formato e testes.
# Roda tudo em sequência; para no primeiro erro.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$SCRIPT_DIR/.."

echo "================================================"
echo "  Empilhadeira — Verificação Completa"
echo "================================================"
echo ""

echo "--- [1/5] ruff check (Python) ---"
cd "$ROOT"
python3 -m ruff check pi/
echo "✓ ruff OK"
echo ""

echo "--- [2/5] black --check (Python) ---"
python3 -m black --check pi/
echo "✓ black OK"
echo ""

echo "--- [3/5] pytest (Pi) ---"
python3 -m pytest pi/tests/ -v
echo "✓ pytest OK"
echo ""

echo "--- [4/5] npm test (Frontend) ---"
cd "$ROOT/frontend"
npm test
echo "✓ npm test OK"
echo ""

echo "--- [5/5] Frontend build check ---"
npm run build 2>&1
echo "✓ build OK"
echo ""

echo "================================================"
echo "  TUDO VERDE ✓"
echo "================================================"
