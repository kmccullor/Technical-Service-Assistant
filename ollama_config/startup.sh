#!/bin/sh
set -e

# Start the Ollama server in the background
ollama serve &

# Give the server a moment to start
sleep 5

# Pull the models
ollama pull llama2:7b
ollama pull nomic-embed-text:v1.5

# Keep the container running by waiting for the background server process
wait
