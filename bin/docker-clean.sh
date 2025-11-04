#!/usr/bin/env bash
#
# docker-clean.sh
# Selectively clean Docker images and containers by name prefix and age

set -euo pipefail

# --- Configuration defaults ---
IMAGE_PREFIX="${1:-}"       # Required: prefix of image names
DAYS_OLD="${2:-7}"          # Optional: age threshold in days (default: 7)
DRY_RUN="${DRY_RUN:-true}"  # Optional: set DRY_RUN=false to actually delete

# --- Validation ---
if [[ -z "$IMAGE_PREFIX" ]]; then
  echo "Usage: $0 <image_prefix> [days_old]"
  echo "Example: $0 myapp 10"
  exit 1
fi

echo "Starting Docker cleanup..."
echo "Target: images with prefix '$IMAGE_PREFIX' older than $DAYS_OLD days"
echo "Dry run: $DRY_RUN"
echo

# --- Gather images matching prefix ---
IMAGES=$(docker images --format "{{.Repository}} {{.ID}}" | grep "^$IMAGE_PREFIX" | awk '{print $2}' || true)

if [[ -z "$IMAGES" ]]; then
  echo "No images found matching prefix '$IMAGE_PREFIX'"
  exit 0
fi

# --- Remove old images ---
for ID in $IMAGES; do
  CREATED_AT=$(docker inspect -f '{{.Created}}' "$ID" | cut -d'.' -f1)
  CREATED_SECS=$(date --date="$CREATED_AT" +%s)
  NOW_SECS=$(date +%s)
  AGE_DAYS=$(( (NOW_SECS - CREATED_SECS) / 86400 ))

  if (( AGE_DAYS > DAYS_OLD )); then
    echo "Deleting image $ID ($AGE_DAYS days old)..."
    if [[ "$DRY_RUN" == "false" ]]; then
      docker rmi -f "$ID"
    fi
  fi
done

echo
echo "Pruning stopped containers and dangling images..."
if [[ "$DRY_RUN" == "false" ]]; then
  docker container prune -f
  docker image prune -f
fi

echo
echo "Cleanup complete!"

