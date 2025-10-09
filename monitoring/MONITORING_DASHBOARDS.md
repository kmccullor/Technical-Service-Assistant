## Monitoring Dashboards & Ollama Exporter

### Overview
Grafana dashboards are provisioned from `monitoring/grafana/provisioning/dashboards/`. A custom Python exporter (`ollama-exporter`) supplies reliable availability metrics for all Ollama instances because the native Ollama HTTP API does not expose Prometheus-formatted metrics.

### Ollama Exporter
- Location: `monitoring/ollama_exporter/`
- Image built via `docker-compose.yml` service `ollama-exporter`
- Environment variable `OLLAMA_TARGETS` lists instances to probe
- Endpoint: `http://ollama-exporter:9105/metrics`

Metrics exposed:
```
ollama_instance_up{instance="ollama-server-1"} 1
ollama_instance_up{instance="ollama-server-2"} 1
ollama_instance_up{instance="ollama-server-3"} 1
ollama_instance_up{instance="ollama-server-4"} 1
ollama_instances_online 4
```

### Prometheus Scrape Job
Added to `monitoring/prometheus/prometheus.yml`:
```yaml
  - job_name: 'ollama-exporter'
    static_configs:
      - targets: ['ollama-exporter:9105']
    scrape_interval: 15s
```

### Dashboard Panel Query (System Overview)
Panel: "Ollama Instances Online" now uses a robust expression:
```
sum(ollama_instance_up) OR on() vector(0)
```
Rationale:
- `sum(ollama_instance_up)` gives an accurate live count from per-instance gauges.
- `OR on() vector(0)` guarantees a numeric zero instead of "No data" if the exporter hasn't emitted yet (avoids ambiguous fallback to a hardcoded expected value like 4).

Historical note (replaced): The earlier approach `ollama_instances_online OR 4` could mask failures (always showing 4) and in some Grafana stat panel evaluations intermittently produced "No data" due to scalar vs instant mode handling. The new expression eliminates that ambiguity.

### Updating / Adding Dashboards
1. Place JSON in the dashboards directory (avoid duplicate filenames).
2. Run normalization script:
   ```bash
   python3 monitoring/grafana/provisioning/dashboards/_normalize_dashboards.py
   docker compose restart grafana
   ```
3. Verifying provisioning:
   ```bash
   docker logs grafana | grep "provision dashboards"
   ```

### Adding New Ollama Instances
1. Append the new instance URL to `OLLAMA_TARGETS` in `docker-compose.yml` under the `ollama-exporter` service.
2. Recreate/exporter (hot reload not required but recommended):
   ```bash
   docker compose up -d --build ollama-exporter
   ```
3. Confirm metric:
   ```bash
   curl -s http://localhost:9091/api/v1/query?query=ollama_instances_online
   ```

### Troubleshooting
| Symptom | Probable Cause | Resolution |
|---------|----------------|------------|
| Panel shows "No data" even though metric exists in Prometheus | Query returned a scalar without time series context and stat panel reduction produced null (earlier `ollama_instances_online OR 4` pattern) | Use `sum(ollama_instance_up) OR on() vector(0)`; ensure panel time range includes last scrape interval |
| Panel shows "No data" on startup | Exporter not scraped yet | Wait one scrape interval (15s) or reload Prometheus: `curl -X POST http://localhost:9091/-/reload` |
| Panel shows constant expected value (e.g. 4) even when instances down | Hardcoded fallback (`OR 4`) masking real outage | Replace with `OR on() vector(0)` and rely on per-instance gauges; add alert on drop |
| Individual instance disappearance not reflected | Only aggregated metric used | Add a table / stat list panel querying `ollama_instance_up` by `instance` for granular visibility |
| Duplicate dashboards warnings | Duplicate JSON names or archived files inside provisioning path | Move/archive duplicates outside provisioning tree |
| UID length errors | Manual JSON added with >40 char `uid` | Remove `uid` and re-run normalization script |
| Grafana shows stale panel after JSON edit | Provisioned dashboard cached in DB | Bump `version` in JSON and restart Grafana (or remove grafana_data volume) |

### Per-Instance Ollama Status Panels (AI Services Dashboard)
Each individual server tile uses (Prometheus scraping injects exporter address as `instance` and preserves the original target hostname as `exported_instance`):
```
ollama_instance_up{exported_instance="ollama-server-N"}
```
Prometheus sets the scrape target's address as `instance` (the exporter itself), so the original container hostname is preserved in the `exported_instance` label. Avoid the generic `up{job="..."}` pattern—these Ollama containers have no native Prometheus endpoint; only the exporter provides their status.

To add a new server panel:
1. Ensure its URL is added to `OLLAMA_TARGETS` for the exporter.
2. Duplicate an existing tile and change the `instance` label.
3. Increment dashboard `version` in JSON for provisioning.
4. (Optional) Add an alert when the value transitions from 1 to 0.

### Future Improvements
- Add a recording rule: `ollama_instances_online` to stable namespace if additional exporters needed.
- Integrate alerting when `ollama_instance_up` falls to 0 for any instance.
- Add latency / model load time probes via a lightweight head call to `/api/generate` with a short timeout (not implemented yet for safety).

---
Last updated: Panel query migration to `sum(ollama_instance_up) OR on() vector(0)` (improved reliability and visibility).
