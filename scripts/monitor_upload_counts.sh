#!/usr/bin/env bash
# Periodically report the number of files remaining in the uploads directory.
# Usage: ./monitor_upload_counts.sh [interval_seconds]

set -euo pipefail

INTERVAL="${1:-60}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -d "$SCRIPT_DIR/uploads" ]]; then
    DEFAULT_UPLOAD_DIR="$SCRIPT_DIR/uploads"
elif [[ -d "$SCRIPT_DIR/../uploads" ]]; then
    DEFAULT_UPLOAD_DIR="$(cd "$SCRIPT_DIR/.." && pwd)/uploads"
else
    DEFAULT_UPLOAD_DIR="uploads"
fi

UPLOAD_DIR="${UPLOAD_DIR:-$DEFAULT_UPLOAD_DIR}"

# Normalize to absolute path if caller passed relative value
if [[ "$UPLOAD_DIR" != /* ]]; then
    UPLOAD_DIR="${SCRIPT_DIR}/${UPLOAD_DIR}"
fi

if [[ ! -d "$UPLOAD_DIR" ]]; then
    echo "$(date +"%F %T") uploads: directory '$UPLOAD_DIR' not found" >&2
    exit 1
fi

while true; do
    timestamp="$(date +"%F %T")"
    count="$(find "$UPLOAD_DIR" -type f | wc -l)"
    echo "$timestamp uploads: $count"
    if [[ "$count" -eq 0 ]]; then
        break
    fi
    sleep "$INTERVAL"
done
