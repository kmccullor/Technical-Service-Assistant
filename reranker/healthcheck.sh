#!/bin/bash
# Reranker container healthcheck script.
# Allows remote / non-localhost deployments by honoring RERANKER_URL env var.
# Usage (Dockerfile / compose): set ENV RERANKER_URL="http://your-hostname:8008" or rely on default.

RERANKER_URL="${RERANKER_URL:-http://localhost:8008}"

if curl -fsS "${RERANKER_URL}/health" > /dev/null; then
  exit 0
else
  echo "Healthcheck failed for ${RERANKER_URL}/health" >&2
  exit 1
fi
