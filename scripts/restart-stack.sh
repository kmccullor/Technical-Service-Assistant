#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
COMPOSE_CMD="docker compose -f ${COMPOSE_FILE}"

log() { printf "[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

run() {
  if ! output="$("$@")"; then
    log "ERROR running: $*"
    return 1
  fi
  printf "%s\n" "$output"
}

health_check() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    printf "✅ %s\n" "$desc"
  else
    printf "❌ %s\n" "$desc"
  fi
}

log "Bringing stack down (remove orphans)…"
${COMPOSE_CMD} down --remove-orphans

log "Starting stack…"
${COMPOSE_CMD} up -d

log "Reloading nginx to refresh upstream DNS…"
${COMPOSE_CMD} exec nginx nginx -s reload >/dev/null 2>&1 || true

log "Stack status:"
${COMPOSE_CMD} ps

log "Health checks:"
health_check "Frontend reachable from nginx" ${COMPOSE_CMD} exec nginx curl -sf http://frontend:3000/
health_check "Reranker health from nginx" ${COMPOSE_CMD} exec nginx curl -sf http://reranker:8008/health
health_check "External HTTPS /health" curl -k -sf https://rni-llm-01.lab.sensus.net/health
health_check "Reranker /health direct" curl -sf http://127.0.0.1:8008/health || true

log "Done."
