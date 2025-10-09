#!/usr/bin/env bash
# Archive (tar.gz) backup snapshot directories older than a threshold (default 14 days)
# Skips already archived directories and preserves original by default unless --remove-original is passed.
# Usage:
#   ./scripts/archive_old_backups.sh [--days 14] [--remove-original]
set -euo pipefail

DAYS=14
REMOVE_ORIGINAL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --days)
      DAYS="$2"; shift 2;;
    --remove-original)
      REMOVE_ORIGINAL=1; shift;;
    *) echo "Unknown argument: $1" >&2; exit 1;;
  esac
done

BACKUP_DIR="backup"
if [[ ! -d "$BACKUP_DIR" ]]; then
  echo "No backup directory present." >&2
  exit 0
fi

echo "Archiving backup snapshots older than $DAYS days..."

find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%P\n' | while read -r SNAPSHOT; do
  PATH_FULL="$BACKUP_DIR/$SNAPSHOT"
  # Extract timestamp prefix pattern YYYYMMDD_HHMMSS if present
  if [[ "$SNAPSHOT" =~ ^([0-9]{8}_[0-9]{6})_end_of_day ]]; then
    # Use directory mtime to determine age
    if [[ $(find "$PATH_FULL" -type d -mtime +"$DAYS" -prune -print) ]]; then
      TAR_NAME="$BACKUP_DIR/${SNAPSHOT}.tar.gz"
      if [[ -f "$TAR_NAME" ]]; then
        echo "Skipping $SNAPSHOT (archive already exists)"
        continue
      fi
      echo "Compressing $SNAPSHOT -> $TAR_NAME"
      tar -czf "$TAR_NAME" -C "$BACKUP_DIR" "$SNAPSHOT"
      if [[ $REMOVE_ORIGINAL -eq 1 ]]; then
        rm -rf "$PATH_FULL"
        echo "Removed original directory $SNAPSHOT"
      fi
    fi
  fi
done

echo "Archive process complete."