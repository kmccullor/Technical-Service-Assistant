## Service Rename Migration (2025-10-05)

The Docker Compose service previously named `rag-app` (runtime container sometimes shown as `next-rag-app-rag-app-1`) has been renamed to:

New service name: `technical-service-assistant`
Container name: `technical-service-assistant`

### Rationale
1. Eliminate ambiguity between folder `next-rag-app` and overall platform.
2. Provide a single canonical name for logs, automation, and monitoring.
3. Prepare for future multi-frontend or gateway additions.

### Summary of Changes
| Item | Before | After |
|------|--------|-------|
| Compose service key | rag-app | technical-service-assistant |
| Container name | rag-app / next-rag-app-rag-app-1 | technical-service-assistant |
| Docs references | next-rag-app-rag-app-1 | technical-service-assistant |

### Update Your Commands
```bash
# Old
docker logs rag-app
# New
docker logs technical-service-assistant

# Old
docker exec -it rag-app sh
# New
docker exec -it technical-service-assistant sh
```

### Rollout
```bash
docker compose up -d --build technical-service-assistant
```
Bind mounts (uploads/, logs/) ensure no data migration needed.

### Labels Added
```
com.project.name=technical-service-assistant
com.project.component=frontend
com.project.migration_note="Renamed from rag-app on 2025-10-05"
```

### Deprecated Files Removed
Legacy per-frontend compose files were deleted to reduce confusion; retrieve via git history if required.

---
Search for remaining `rag-app` references if any scripts still rely on the old name.

### Addition: Reasoning Engine Service (2025-10-05)

A new lightweight `reasoning-engine` service (port 8050) was added to begin exposing advanced orchestration APIs (chain-of-thought, knowledge synthesis). Initially it ships only with a health endpoint; future iterations will surface reasoning endpoints currently embedded in the `reranker` process. This decoupling allows independent scaling and performance profiling.

### Duplicate / Orphaned Stack Cleanup

After the rename some environments may still display a second stack (e.g. `next-rag-app-rag-app`) due to cached earlier compose metadata. To purge:

```bash
# 1. Stop & remove any lingering old containers
docker ps --filter name=rag-app -a
docker rm -f $(docker ps --filter name=rag-app -q) 2>/dev/null || true

# 2. Remove obsolete networks (only if present)
docker network ls | grep rag-app || true
# example cleanup (replace <id>):
# docker network rm <network_id>

# 3. Prune dangling images referencing old tag
docker image ls | grep rag-app || true
docker image prune -f

# 4. Recreate current stack cleanly
docker compose down -v
docker compose up -d --build
```

Expected running containers (core app scope): `technical-service-assistant`, `reranker`, `pdf_processor`, four `ollama-server-*`, `pgvector`, `redis-cache`, metrics exporters, monitoring stack (`prometheus`, `grafana`, `node-exporter`, `cadvisor`, `redis-exporter`, `ollama-exporter`, `postgres-exporter`), and the new `reasoning-engine`.

If a second Redis container appears, note that only `redis-cache` is the actual datastore; `redis-exporter` is a metrics sidecar exposing Prometheus metrics on port 9121.