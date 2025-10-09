# Alerting & Notification Setup

This document describes how Prometheus alerts are routed through Alertmanager and surfaced in Grafana.

## Components Added
- **Alertmanager** (`alertmanager:9093`) added to `docker-compose.yml`.
- **Prometheus alerting block** enabled in `monitoring/prometheus/prometheus.yml`.
- **Alertmanager config** at `monitoring/alertmanager/alertmanager.yml` with routing rules.
- **Grafana Alertmanager datasource** (`alertmanager.yml`) provisioned for in-UI alert browsing.

## Alert Routing Logic
Top-level `route` groups alerts by `alertname, service` with:
- `group_wait: 30s` – batch initial related alerts.
- `group_interval: 5m` – suppress duplicate group notifications within 5 minutes.
- `repeat_interval: 3h` – resend if still firing.

### Sub-routes
| Matcher | Receiver | Notes |
|---------|----------|-------|
| severity="critical" | `critical` | Always processed first (continue: true) |
| service="performance_monitor" | `ops` | Dedicated ops pipeline |

### Inhibition
If a `critical` alert and a `warning` alert share `alertname` and `service`, the warning is inhibited.

## Receivers
Receivers are currently webhook placeholders hitting the frontend (endpoints should be implemented or replaced):
- `default`: `http://technical-service-assistant:3000/api/alerts/mock`
- `critical`: `http://technical-service-assistant:3000/api/alerts/critical`
- `ops`: `http://technical-service-assistant:3000/api/alerts/ops`

Email receiver example is commented until SMTP is available.

## Adding Real Notification Channels
1. **Slack**:
   ```yaml
   receivers:
     - name: slack
       slack_configs:
         - send_resolved: true
           channel: '#alerts'
           api_url: ${SLACK_WEBHOOK_URL}
           title: |-
             [{{ .Status | toUpper }}] {{ .CommonLabels.alertname }} ({{ .CommonLabels.severity }})
           text: |-
             {{ range .Alerts }}*{{ .Labels.alertname }}* on *{{ .Labels.instance }}*\n  {{ .Annotations.description }}\n{{ end }}
   ```
2. **Email**: Uncomment template in `alertmanager.yml` and configure Grafana SMTP or external relay.
3. **PagerDuty**:
   ```yaml
   pagerduty_configs:
     - routing_key: ${PAGERDUTY_KEY}
       severity: '{{ .CommonLabels.severity }}'
   ```
4. **OpsGenie / Webhook**: Add `opsgenie_configs` or additional `webhook_configs` entries.

## Validating the Integration
1. Bring up stack (or recreate altered services):
   ```bash
   docker compose up -d alertmanager prometheus grafana
   ```
2. Reload Prometheus (already enabled with lifecycle API):
   ```bash
   curl -X POST http://localhost:9091/-/reload
   ```
3. Visit:
   - Prometheus Alerts: http://localhost:9091/alerts
   - Alertmanager UI:   http://localhost:9093
   - Grafana Alerting (Explore -> Alerting -> Alert rules / Alert instances)
4. Force a test alert:
   - Stop a monitored container (e.g., `docker stop performance-monitor`) and wait for `PerformanceMonitorDown`.

## Common Adjustments
| Goal | Change |
|------|--------|
| Reduce noise in dev | Increase `repeat_interval` and add route match on `environment="prod"` |
| Add environment label | Add `relabel_configs` in scrape jobs or set `external_labels` in Prometheus |
| Silence maintenance | Use Alertmanager UI: create silence by matchers (service="docling_processor") |
| Escalate after N minutes | Use two routes: initial warning, then critical after longer `for:` threshold |

## Recommended External Labels
In `prometheus.yml` (top-level):
```yaml
global:
  external_labels:
    environment: dev
    cluster: local-dev
```

## Future Enhancements
- Deduplicate frontend webhook endpoints (deploy a unified alert ingestion API).
- Add templated notification bodies (reusable files in `templates/`).
- Map severity to Slack channel / PagerDuty urgency.
- Auto-create Grafana contact points and notification policies (Grafana unified alerting) – optional alternative.

## Troubleshooting
| Symptom | Diagnosis |
|---------|-----------|
| No alerts in Alertmanager | Check Prometheus `/status` -> rules; ensure `alerting` block is active. |
| Alerts firing but no notifications | Verify receiver endpoints accessible from alertmanager container. |
| Duplicate notifications | Adjust `group_interval` / remove `continue: true` where not needed. |
| Inhibited alerts unexpected | Inspect inhibition rules tab in Alertmanager UI. |

---
Maintained by: Monitoring & Reliability Initiative
