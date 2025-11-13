#!/usr/bin/env bash
set -euo pipefail

TARGET_URL="${LOAD_TEST_TARGET_URL:-https://rni-llm-01.lab.sensus.net}"
API_KEY="${LOAD_TEST_API_KEY:-}"
BEARER_TOKEN="${LOAD_TEST_BEARER_TOKEN:-}"
PROM_URL="${LOAD_TEST_PROM_URL:-}"

REPORT_DIR=${LOAD_TEST_REPORT_DIR:-load_test_results}
mkdir -p "$REPORT_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
SCRIPT_PATH="$REPORT_DIR/k6_script_${TIMESTAMP}.js"
SUMMARY_PATH="$REPORT_DIR/k6_raw_summary_${TIMESTAMP}.json"

python scripts/testing/load_test.py --target "$TARGET_URL" --api-key "$API_KEY" --bearer-token "$BEARER_TOKEN" --prometheus-url "$PROM_URL" --report-dir "$REPORT_DIR" --use-docker
done
