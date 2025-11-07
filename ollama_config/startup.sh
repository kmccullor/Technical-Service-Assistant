#!/bin/sh
set -e

# Start the Ollama server in the background so we can issue pull commands.
ollama serve &

# Give the server a moment to start before pulling models.
sleep 5

# Default model set covers embeddings, chat, coding, reasoning, and vision.
DEFAULT_MODELS="
nomic-embed-text:v1.5
mistral:7b
codellama:7b
llama3.2:3b
llava:7b
"

# Allow overrides via OLLAMA_PRELOAD_MODELS (whitespace or comma separated).
RAW_MODELS="${OLLAMA_PRELOAD_MODELS:-$DEFAULT_MODELS}"
MODELS=$(printf '%s' "$RAW_MODELS" | tr ',' ' ')

for model in $MODELS; do
  if [ -n "$model" ]; then
    echo "Pulling model: $model"
    if ! ollama pull "$model"; then
      echo "Failed to pull model: $model" >&2
      exit 1
    fi
  fi
done

# Keep the container running by waiting for the background server process.
wait
