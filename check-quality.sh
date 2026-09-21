#!/usr/bin/env bash
# Единый quality gate проекта.
# Использование: ./check-quality.sh или pnpm run check:quality
set -euo pipefail
cd "$(dirname "$0")"

echo "== Backend tests =="
./run-tests.sh

echo
echo "== Architecture guardrails =="
pnpm run check:architecture

echo
echo "== Frontend and scripts tests =="
pnpm run test:run

echo
echo "== TypeScript typecheck =="
pnpm run typecheck

echo
echo "== Production frontend build =="
pnpm --filter ./artifacts/intellect-learning-platform run build

echo
echo "Quality gate passed."
