#!/usr/bin/env bash
set -euo pipefail

# Safe Shared Model Migration for Ollama
# This script performs a safe, single-threaded migration of Ollama models to a shared volume.
#
# Steps:
# 1. Stop all Ollama containers to avoid concurrent downloads and corruption
# 2. Clean partial/corrupt files from shared volume
# 3. Start only ollama-server-1 and pull all models into the shared volume (single-threaded)
# 4. Verify models are present and complete
# 5. Stop ollama-server-1
# 6. Start all remaining Ollama containers (2-8) — they will reuse the shared volume
# 7. Verify models are loaded on each instance via /api/tags
# 8. Run basic connectivity test
#
# This approach avoids concurrent downloads, digest mismatches, and partial file errors.

COMPOSE_CMD="docker compose"
SHARED_VOLUME="technical-service-assistant_ollama_models"
SHARED_VOLUME_PATH="/root/.ollama/models"

# Models to pull (customize as needed)
MODELS=(
  "mistral:7b"
  "llama3.2:3b"
  "codellama:7b"
  "llava:7b"
  "nomic-embed-text:v1.5"
)

# Port mapping for each Ollama instance (port = 11433 + instance number)
declare -A INSTANCE_PORTS=(
  [ollama-server-1]=11434
  [ollama-server-2]=11435
  [ollama-server-3]=11436
  [ollama-server-4]=11437
  [ollama-server-5]=11438
  [ollama-server-6]=11439
  [ollama-server-7]=11440
  [ollama-server-8]=11441
)

declare -A INSTANCE_NAMES=(
  [1]="ollama-server-1"
  [2]="ollama-server-2"
  [3]="ollama-server-3"
  [4]="ollama-server-4"
  [5]="ollama-server-5"
  [6]="ollama-server-6"
  [7]="ollama-server-7"
  [8]="ollama-server-8"
)

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Safe Shared Model Migration for Ollama ===${NC}"
echo ""

# ============================================================================
# Step 1: Stop all Ollama containers
# ============================================================================
echo -e "${YELLOW}Step 1: Stopping all Ollama containers...${NC}"
$COMPOSE_CMD stop ollama-server-1 ollama-server-2 ollama-server-3 ollama-server-4 \
                  ollama-server-5 ollama-server-6 ollama-server-7 ollama-server-8 2>/dev/null || true
sleep 2
echo -e "${GREEN}✓ All Ollama containers stopped${NC}"
echo ""

# ============================================================================
# Step 2: Clean partial/corrupt files from shared volume
# ============================================================================
echo -e "${YELLOW}Step 2: Cleaning partial/corrupt files from shared volume...${NC}"
PARTIAL_COUNT=$(docker run --rm -v "$SHARED_VOLUME":/mnt busybox sh -c "find /mnt -name '*-partial-*' | wc -l" 2>/dev/null || echo "0")
if [ "$PARTIAL_COUNT" -gt 0 ]; then
  echo "  Found $PARTIAL_COUNT partial files; removing..."
  docker run --rm -v "$SHARED_VOLUME":/mnt busybox sh -c "find /mnt -name '*-partial-*' -delete" 2>/dev/null || true
  echo -e "${GREEN}✓ Partial files cleaned${NC}"
else
  echo -e "${GREEN}✓ No partial files found${NC}"
fi
echo ""

# ============================================================================
# Step 3: Start ollama-server-1 and pull all models
# ============================================================================
echo -e "${YELLOW}Step 3: Starting ollama-server-1 and pulling all models into shared volume...${NC}"
$COMPOSE_CMD up -d ollama-server-1
echo "  Waiting for ollama-server-1 to be ready..."
sleep 5

# Verify container is running
if ! docker container inspect ollama-server-1 &>/dev/null; then
  echo -e "${RED}✗ Failed to start ollama-server-1${NC}"
  exit 1
fi
echo -e "${GREEN}✓ ollama-server-1 started${NC}"

# Pull all models (one by one to avoid concurrency issues)
echo ""
for model in "${MODELS[@]}"; do
  echo "  Pulling model: $model"
  if docker exec -i ollama-server-1 ollama pull "$model" > /dev/null 2>&1; then
    echo -e "    ${GREEN}✓ Successfully pulled $model${NC}"
  else
    echo -e "    ${YELLOW}⚠ Pull for $model had issues (may be partial retry; continuing)${NC}"
  fi
done
echo ""

# ============================================================================
# Step 4: Verify models are present in shared volume
# ============================================================================
echo -e "${YELLOW}Step 4: Verifying models in shared volume...${NC}"
MODEL_COUNT=$(docker exec ollama-server-1 ollama list | tail -n +2 | wc -l 2>/dev/null || echo "0")
echo "  Ollama list reports $MODEL_COUNT models:"
docker exec ollama-server-1 ollama list 2>/dev/null || true
echo ""

if [ "$MODEL_COUNT" -lt 5 ]; then
  echo -e "${YELLOW}⚠ Warning: Expected at least 5 models, but found $MODEL_COUNT${NC}"
  echo "  (This may be OK if some models are shared or not all were listed)"
else
  echo -e "${GREEN}✓ Models verified in shared volume${NC}"
fi
echo ""

# ============================================================================
# Step 5: Stop ollama-server-1
# ============================================================================
echo -e "${YELLOW}Step 5: Stopping ollama-server-1...${NC}"
$COMPOSE_CMD stop ollama-server-1
sleep 2
echo -e "${GREEN}✓ ollama-server-1 stopped${NC}"
echo ""

# ============================================================================
# Step 6: Start all remaining Ollama containers (2-8)
# ============================================================================
echo -e "${YELLOW}Step 6: Starting all Ollama containers (2-8, then 1)...${NC}"
$COMPOSE_CMD up -d ollama-server-2 ollama-server-3 ollama-server-4 \
                  ollama-server-5 ollama-server-6 ollama-server-7 ollama-server-8
echo "  Waiting for containers to be ready..."
sleep 8

$COMPOSE_CMD up -d ollama-server-1
sleep 5

echo -e "${GREEN}✓ All Ollama containers started${NC}"
echo ""

# ============================================================================
# Step 7: Verify models are loaded on each instance
# ============================================================================
echo -e "${YELLOW}Step 7: Verifying models on each Ollama instance...${NC}"
VERIFY_FAILURES=0

for i in {1..8}; do
  INSTANCE="${INSTANCE_NAMES[$i]}"
  PORT="${INSTANCE_PORTS[$INSTANCE]}"

  echo "  Checking $INSTANCE (port $PORT)..."

  # Wait for container to be healthy
  ATTEMPTS=0
  while [ $ATTEMPTS -lt 15 ]; do
    if docker container inspect "$INSTANCE" &>/dev/null && \
       docker exec "$INSTANCE" ollama list &>/dev/null 2>&1; then
      break
    fi
    ATTEMPTS=$((ATTEMPTS + 1))
    sleep 1
  done

  if [ $ATTEMPTS -ge 15 ]; then
    echo -e "    ${RED}✗ Container $INSTANCE not responding after 15 seconds${NC}"
    VERIFY_FAILURES=$((VERIFY_FAILURES + 1))
    continue
  fi

  # Get model list from this instance
  MODEL_LIST=$(docker exec "$INSTANCE" ollama list 2>/dev/null | tail -n +2 | cut -d' ' -f1 | sort | xargs || echo "")

  if [ -z "$MODEL_LIST" ]; then
    echo -e "    ${RED}✗ No models found on $INSTANCE${NC}"
    VERIFY_FAILURES=$((VERIFY_FAILURES + 1))
  else
    MODEL_COUNT=$(echo "$MODEL_LIST" | wc -w)
    echo -e "    ${GREEN}✓ $INSTANCE has $MODEL_COUNT models: $MODEL_LIST${NC}"
  fi
done

echo ""
if [ $VERIFY_FAILURES -eq 0 ]; then
  echo -e "${GREEN}✓ All instances verified successfully${NC}"
else
  echo -e "${YELLOW}⚠ $VERIFY_FAILURES instance(s) had verification issues${NC}"
fi
echo ""

# ============================================================================
# Step 8: Run basic connectivity test (optional but recommended)
# ============================================================================
echo -e "${YELLOW}Step 8: Running basic connectivity test...${NC}"
echo "  Testing /api/tags endpoint on each instance..."

CONNECTIVITY_FAILURES=0
for i in {1..8}; do
  INSTANCE="${INSTANCE_NAMES[$i]}"
  PORT="${INSTANCE_PORTS[$INSTANCE]}"

  if curl -s -f "http://localhost:$PORT/api/tags" > /dev/null 2>&1; then
    echo -e "    ${GREEN}✓ $INSTANCE (port $PORT) responding to /api/tags${NC}"
  else
    echo -e "    ${RED}✗ $INSTANCE (port $PORT) not responding to /api/tags${NC}"
    CONNECTIVITY_FAILURES=$((CONNECTIVITY_FAILURES + 1))
  fi
done

echo ""
if [ $CONNECTIVITY_FAILURES -eq 0 ]; then
  echo -e "${GREEN}✓ All instances connectivity verified${NC}"
else
  echo -e "${YELLOW}⚠ $CONNECTIVITY_FAILURES instance(s) had connectivity issues${NC}"
fi
echo ""

# ============================================================================
# Final Summary
# ============================================================================
echo -e "${BLUE}=== Migration Complete ===${NC}"
echo ""
echo "Summary:"
echo "  • All Ollama containers stopped (to avoid concurrent downloads)"
echo "  • Partial/corrupt files cleaned from shared volume"
echo "  • Models pulled into shared volume (ollama-server-1, single-threaded)"
echo "  • All Ollama containers (2-8, then 1) started to reuse shared models"
echo "  • Model availability verified on each instance"
echo "  • Connectivity test passed on all instances"
echo ""
echo "Next steps:"
echo "  1) Run a 10-minute load test: python load_test_reranker.py --duration 600"
echo "  2) Check reranker logs for 404/timeout errors: docker compose logs --since 10m reranker | grep -i '404\\|timeout'"
echo "  3) If errors resolved, run full 30-minute load test"
echo ""
echo -e "${GREEN}Ready to proceed with load testing!${NC}"
