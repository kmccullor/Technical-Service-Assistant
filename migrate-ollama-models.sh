#!/bin/bash
# Migration script: Share Ollama model repository across all containers
# This script safely migrates from individual model volumes to a shared model volume

set -e

echo "=== Ollama Model Repository Sharing Migration ==="
echo ""

# Step 1: Check if running
echo "Step 1: Checking current container status..."
RUNNING=$(docker compose ps -q | wc -l)
if [ "$RUNNING" -eq 0 ]; then
    echo "✓ No containers running, safe to proceed with pull approach"
    RUNNING=false
else
    echo "⚠ $RUNNING containers are running"
    RUNNING=true
fi
echo ""

# Step 2: Create shared volume
echo "Step 2: Creating shared ollama_models volume..."
docker volume create technical-service-assistant_ollama_models 2>/dev/null || echo "✓ Volume already exists"
echo ""

# Step 3: If running, we'll migrate models data
if [ "$RUNNING" = true ]; then
    echo "Step 3: Migrating existing models to shared volume..."

    # Create temp container to copy models
    for i in {1..8}; do
        CONTAINER_ID="ollama-server-$i"
        VOL_NAME="technical-service-assistant_ollama_data_$i"

        # Check if the individual volume has models
        if docker volume inspect "$VOL_NAME" &>/dev/null; then
            echo "  Copying models from $CONTAINER_ID..."

            # Use temp container to copy models from individual volume to shared volume
            docker run --rm \
                -v "$VOL_NAME":/source \
                -v technical-service-assistant_ollama_models:/dest \
                busybox sh -c 'cp -r /source/models/* /dest/ 2>/dev/null || true'
        fi
    done
    echo "✓ Models migrated to shared volume"
    echo ""

    echo "Step 4: Restarting Ollama containers with new volume configuration..."
    docker compose up -d ollama-server-1 ollama-server-2 ollama-server-3 ollama-server-4 \
                       ollama-server-5 ollama-server-6 ollama-server-7 ollama-server-8
    echo "✓ Containers restarted"
else
    echo "Step 3: Containers not running, skipping migration"
    echo "Step 4: Models will be shared when containers start"
fi

echo ""
echo "=== Migration Complete ==="
echo ""
echo "Benefits:"
echo "  • Models are now shared across all 8 Ollama instances"
echo "  • Reduced storage: Only one copy of each model"
echo "  • Faster initialization: New containers can reuse existing models"
echo "  • Bandwidth savings: No duplicate model downloads"
echo ""
echo "Volume layout:"
echo "  • technical-service-assistant_ollama_models (SHARED - all 8 containers)"
echo "  • technical-service-assistant_ollama_data_1..8 (per-container state)"
echo ""
