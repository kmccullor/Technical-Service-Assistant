# End-of-Day Reporting & Automation

This document describes the automated end-of-day (EOD) reporting system for the Technical Service Assistant, including enhanced monitoring integration and documentation tracking.

## Overview

The EOD reporting system provides comprehensive daily summaries of:
- **System Health**: Container status, database metrics, resource utilization
- **Monitoring Insights**: Prometheus metrics, firing alerts, performance indicators
- **Development Activity**: Git commits, feature additions, bug fixes
- **Documentation Statistics**: Markdown file counts, recent changes, content metrics
- **Operational Status**: Service availability, processing pipeline health

## Components

### 1. Scripts
| File | Purpose | Usage |
|------|---------|-------|
| `scripts/end_of_day.sh` | Main EOD automation script | `./scripts/end_of_day.sh [--automated]` |
| `email_eod_report.py` | Enhanced email reporting with metrics | `python email_eod_report.py recipient@domain.com` |
| `daily_email_report.sh` | Wrapper for secure email delivery | `./daily_email_report.sh` |

### 2. Report Sections

#### 🎯 System Health Overview
- **Container Status**: Running vs expected containers (parsed from `docker-compose.yml`)
- **Database Metrics**: Document and chunk counts from PostgreSQL
- **Resource Usage**: Disk and memory utilization with thresholds
- **Monitoring Status**: Prometheus availability, firing alerts, refresh age

#### 📈 Live Monitoring Snapshot
- **Alert Status**: Count and names of firing Prometheus alerts
- **Processing Metrics**: Documents processed in last 24 hours
- **Performance Indicators**: Exporter refresh lag, service health
- **Container Health**: Docker container count and status

#### 📚 Documentation Statistics
- **File Counts**: Total markdown files and line counts
- **Change Tracking**: Files modified in last 7 days and today
- **Content Metrics**: Top changed files and documentation activity

#### 📝 Development Activity
- **Git Metrics**: Commits today, features added, bugs fixed
- **Repository Status**: Uncommitted changes, recent commits
- **Code Quality**: Performance metrics, error logs, test results

## Configuration

### Environment Variables
```bash
# Email Configuration
export EOD_SENDER_EMAIL="alerts@company.com"
export EOD_SENDER_PASSWORD="app_password"
export EOD_SMTP_SERVER="smtp.gmail.com"
export EOD_SMTP_PORT="587"
export EOD_SMTP_USE_TLS="true"

# Notification Webhooks (optional)
export EOD_WEBHOOK_URL="https://hooks.slack.com/services/..."
export EOD_EMAIL="admin@company.com"

# Monitoring Endpoints
export PROMETHEUS_URL="http://localhost:9091"
export ALERTMANAGER_URL="http://localhost:9093"
```

### Cron Automation
Add to crontab for automated daily execution:
```bash
# End of day report (weekdays at 5 PM)
0 17 * * 1-5 /path/to/Technical-Service-Assistant/scripts/end_of_day.sh --automated

# Morning health check (weekdays at 8 AM)
0 8 * * 1-5 /path/to/Technical-Service-Assistant/scripts/end_of_day.sh --automated --quick
```

## Enhanced Features (October 2025)

### 🔍 Prometheus Integration
The system now queries Prometheus for real-time metrics:
- **Alert Status**: Firing alerts count and severity breakdown
- **Processing Metrics**: Docling documents processed, ingestion rates
- **Performance Data**: Refresh cycles, response times, error rates
- **Service Health**: Component availability and response metrics

Example metrics collected:
```
firing_alerts: 2
firing_alert_names: "DoclingIngestionStalled, PerformanceMonitorRefreshLag"
docs_processed_24h: 15
refresh_age_seconds: 45
containers_running: 12
```

### 📊 Documentation Tracking
Automated analysis of documentation changes:
- **File Discovery**: Recursively finds all `.md` files (max depth 6)
- **Change Detection**: Git log analysis for recent modifications
- **Content Metrics**: Total line counts across documentation
- **Activity Summary**: Top changed files and modification patterns

### 🛡️ Error Handling & Fallbacks
- **Prometheus Unavailable**: Gracefully handles monitoring system downtime
- **Docker Issues**: Falls back to alternative container detection methods
- **Git Repository**: Handles non-git environments and permission issues
- **Network Timeouts**: 5-second timeouts with "N/A" fallbacks

## Usage Examples

### Manual Execution
```bash
# Generate today's report
./scripts/end_of_day.sh

# Automated mode (cron-friendly)
./scripts/end_of_day.sh --automated

# Email report with enhanced metrics
python email_eod_report.py admin@company.com

# Test email configuration
python email_eod_report.py --test admin@company.com
```

### Output Locations
- **Reports**: `logs/daily_report_YYYYMMDD.md`
- **Automation Logs**: `logs/end_of_day_automation_YYYYMMDD.log`
- **Health Checks**: `logs/health_check_YYYYMMDD.log`
- **System Snapshots**: `logs/system_snapshot_YYYYMMDD.json`

## Monitoring Integration

### Prometheus Queries Used
| Metric | Query | Purpose |
|--------|-------|---------|
| Firing Alerts | `/api/v1/alerts` | Alert status and names |
| Documents Processed | `increase(docling_documents_processed_total[24h])` | Daily processing volume |
| Refresh Age | `ingestion:last_refresh_age_seconds` | Exporter health |
| Service Status | `up{job="performance-monitor"}` | Component availability |

### Alert Correlation
The system correlates EOD findings with Prometheus alerts:
- **High Alert Count**: Highlights system issues requiring attention
- **Stale Metrics**: Detects monitoring pipeline problems
- **Performance Degradation**: Identifies slow or failing components
- **Documentation Drift**: Tracks knowledge base maintenance needs

## Customization

### Adding New Metrics
1. **Prometheus Queries**: Add to `get_prometheus_metrics()` in `email_eod_report.py`
2. **Shell Variables**: Extend metric collection in `end_of_day.sh`
3. **Report Sections**: Update markdown templates in both scripts
4. **Thresholds**: Adjust health/warning indicators in status logic

### Notification Channels
```python
# Slack Integration
def send_slack_notification(webhook_url, message):
    payload = {"text": message}
    requests.post(webhook_url, json=payload)

# Teams Integration
def send_teams_notification(webhook_url, message):
    payload = {"@type": "MessageCard", "text": message}
    requests.post(webhook_url, json=payload)
```

### Custom Report Sections
Add new sections to `end_of_day.sh`:
```bash
# Custom metrics collection
CUSTOM_METRIC=$(your_command_here)

cat >> "$REPORT_FILE" << EOF
## 🔧 Custom Section
- **Metric Name**: $CUSTOM_METRIC
- **Status**: $([ "$CUSTOM_METRIC" -gt 0 ] && echo "✅ Good" || echo "⚠️ Check")
EOF
```

## Troubleshooting

| Issue | Cause | Resolution |
|-------|-------|-----------|
| No Prometheus metrics | Service down or unreachable | Check `http://localhost:9091/api/v1/query?query=up` |
| Email delivery fails | SMTP credentials or config | Test with `python email_eod_report.py --test` |
| Missing documentation stats | Git repository issues | Verify git commands work: `git log --since=yesterday` |
| Container count mismatch | Docker permission or service issues | Check `docker ps` output and permissions |
| Report generation slow | Large git history or many files | Reduce search depth or add `--quick` flag |

## Security Considerations

- **Email Credentials**: Use app passwords, not account passwords
- **File Permissions**: Ensure scripts have appropriate execute permissions
- **Log Retention**: Implement rotation to prevent disk space issues
- **Network Access**: Prometheus queries require network connectivity
- **Git Access**: Repository access needed for change detection

## Future Enhancements

### Planned Features
- **Trend Analysis**: Historical metric comparison and trend detection
- **Alert Correlation**: Deeper integration with Alertmanager routing
- **Custom Dashboards**: Grafana integration for visual EOD reports
- **Multi-Environment**: Support for dev/staging/prod environment labeling
- **Performance Profiling**: Detailed timing analysis of report generation

### Integration Opportunities
- **ITSM Systems**: ServiceNow, Jira integration for ticket creation
- **ChatOps**: Direct Slack/Teams bot integration for interactive reports
- **CI/CD Pipelines**: Integration with GitHub Actions or GitLab CI
- **Monitoring Platforms**: DataDog, New Relic metric forwarding

---

**Maintained by**: Technical Service Assistant Operations Team
**Last Updated**: October 8, 2025
**Version**: 2.1 (Enhanced Monitoring Integration)
