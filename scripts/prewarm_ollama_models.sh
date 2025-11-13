#!/usr/bin/env bash
set -euo pipefail

# Pre-warm specified Ollama models across all Ollama server containers.
# This script executes `ollama pull` and a short warmup generation inside each
# container to ensure the model is resident and ready to handle /api/chat
# requests. Designed to be idempotent and safe to run multiple times.

# Models to pre-load; customize as needed or pass as arguments
MODELS=(
  "mistral:7b"
  "llama3.2:3b"
  "codellama:7b"
  "llava:7b"
  "nomic-embed-text:v1.5"
)

# Container names (adjust if your compose uses different names)
CONTAINERS=(
  "ollama-server-1"
  "ollama-server-2"
  "ollama-server-3"
  "ollama-server-4"
  "ollama-server-5"
  "ollama-server-6"
  "ollama-server-7"
  "ollama-server-8"
)

# Number of seconds to allow for a short 'warmup' generation per model
WARMUP_TIMEOUT=20

echo "== Ollama Model Pre-warm Script =="
echo "Containers: ${CONTAINERS[*]}"
echo "Models: ${MODELS[*]}"
echo

for container in "${CONTAINERS[@]}"; do
  echo "--> Processing container: $container"

  # Check container exists
  if ! docker container inspect "$container" &>/dev/null; then
    echo "    ✖ Container $container not found; skipping"
    continue
  fi

  for model in "${MODELS[@]}"; do
    echo "    Pulling model $model into $container..."
    # Attempt to pull the model inside the container; continue on errors
    if ! docker exec "$container" ollama pull "$model" 2>&1 | sed -n '1,3p'; then
      echo "      ⚠ Pull command exited with non-zero status for $model (continuing)"
    else
      echo "      ✓ Pull initiated (or already present)"
    fi

    echo "    Warming model $model in $container (short generation)..."
    # Use host `timeout` to avoid blocking indefinitely; if timeout not available it's okay
    if command -v timeout &>/dev/null; then
      timeout "$WARMUP_TIMEOUT" docker exec -i "$container" \
        sh -c "ollama run '$model' 'Warmup: respond briefly' || true" 2>&1 | sed -n '1,2p' || true
    else
      docker exec -i "$container" sh -c "ollama run '$model' 'Warmup: respond briefly' || true" 2>&1 | sed -n '1,2p' || true
    fi

    echo "      ✓ Warmup done (errors ignored)"
  done

  echo
done

echo "== Pre-warm complete =="

echo "Next steps:"
echo "  1) Check each instance for loaded models:"
echo "       curl -s http://localhost:11434/api/tags | jq '.models[].name'  # adjust port/container mapping"
echo "  2) Re-run small smoke test and verify 404/timeout counts are gone in logs"
