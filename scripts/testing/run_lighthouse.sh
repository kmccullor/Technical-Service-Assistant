#!/usr/bin/env bash
set -euo pipefail

URL="${LIGHTHOUSE_URL:-https://rni-llm-01.lab.sensus.net}"
OUTPUT_DIR=${LIGHTHOUSE_OUTPUT_DIR:-next-rag-app/lighthouse-report}
mkdir -p "$OUTPUT_DIR"

docker run --rm \
  -v "$(pwd)/next-rag-app:/app" \
  -w /app \
  -e LIGHTHOUSE_URL="$URL" \
  node:18-bullseye \
  bash -c "npm install -g @lhci/cli && lhci autorun --config=tests/performance/lighthouse.config.cjs"
