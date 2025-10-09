# Technical Service Assistant - Monitoring & Observability

## 📊 Overview

Comprehensive monitoring stack built with **Prometheus** and **Grafana** for the Technical Service Assistant project. Provides real-time visibility into system performance, application health, and AI service metrics.

## 🚀 Quick Start

### Start Monitoring Stack
```bash
# Start all monitoring services
docker compose up -d prometheus grafana postgres-exporter redis-exporter node-exporter cadvisor

# Check status
./check_monitoring.sh
```

### Access Dashboards
- **Grafana**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9091
- **cAdvisor**: http://localhost:8081

## 📈 Available Metrics

### System Metrics
- **CPU Usage**: Real-time CPU utilization across all cores
- **Memory Usage**: RAM consumption and availability
- **Disk Usage**: Storage utilization by mount point
- **Network I/O**: Network traffic statistics

### Container Metrics (via cAdvisor)
- **Container CPU**: Per-container CPU usage
- **Container Memory**: Memory consumption by container
- **Container Network**: Network traffic per container
- **Container Filesystem**: Storage usage per container

### Database Metrics (PostgreSQL)
- **Connection Count**: Active database connections
- **Query Performance**: Query execution times and rates
- **Database Size**: Storage utilization
- **Lock Statistics**: Database lock analysis
- **Vector Operations**: pgvector-specific metrics

### Cache Metrics (Redis)
- **Memory Usage**: Redis memory consumption
- **Hit/Miss Ratio**: Cache effectiveness
- **Command Statistics**: Operation rates
- **Connection Count**: Active Redis connections

### AI Service Metrics
- **Ollama Health**: Status of all 4 Ollama instances
- **Model Selection**: Distribution of AI model usage
- **Response Times**: AI inference performance
- **Reranker Performance**: Search quality metrics

## 📊 Pre-configured Dashboards

### 1. System Overview Dashboard
- **Location**: `monitoring/grafana/dashboards/system_overview.json`
- **Features**: 
  - System health status
  - CPU and memory usage trends
  - Container status table
  - Disk usage gauges

### 2. AI Services Dashboard  
- **Location**: `monitoring/grafana/dashboards/ai_services.json`
- **Features**:
  - Ollama instance status
  - Reranker performance metrics
  - Model selection distribution
  - RAG query success rates

### 3. Database & Infrastructure Dashboard
- **Location**: `monitoring/grafana/dashboards/database_infrastructure.json`
- **Features**:
  - PostgreSQL performance
  - Redis cache statistics
  - Container resource usage
  - Document processing metrics

## 🎯 Key Prometheus Queries

### System Health
```promql
# CPU Usage
100 - (avg(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory Usage  
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100

# Disk Usage
(1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes)) * 100
```

### Application Performance
```promql
# HTTP Request Rate
rate(http_requests_total[5m])

# Response Time (95th percentile)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error Rate
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])
```

### Database Performance
```promql
# Active Connections
pg_stat_activity_count

# Query Rate
rate(pg_stat_statements_calls[5m])

# Average Query Time
pg_stat_statements_mean_time_ms
```

## 🚨 Alerting Rules

Comprehensive alerting rules are defined in `monitoring/prometheus/alerts.yml`:

### Critical Alerts
- **Service Down**: Any critical service becomes unavailable
- **High Memory Usage**: Memory usage > 90%
- **Disk Space Low**: Disk usage > 90%
- **All Ollama Instances Down**: Complete AI functionality loss

### Warning Alerts
- **High CPU Usage**: CPU usage > 80% for 5 minutes
- **High Database Connections**: Connection count > 80% of max
- **Slow Database Queries**: Average query time > 1000ms
- **High Error Rate**: API error rate > 10%

## 🔧 Configuration Files

### Prometheus Configuration
- **Main Config**: `monitoring/prometheus/prometheus.yml`
- **Alert Rules**: `monitoring/prometheus/alerts.yml`
- **Scrape Targets**: All services automatically discovered

### Grafana Configuration
- **Datasources**: `monitoring/grafana/provisioning/datasources/`
- **Dashboards**: `monitoring/grafana/provisioning/dashboards/`
- **Dashboard JSON**: `monitoring/grafana/dashboards/`

## 📱 Mobile-Friendly Access

All dashboards are responsive and work well on mobile devices for on-the-go monitoring.

## 🔍 Troubleshooting

### Check Service Status
```bash
# View monitoring container status
docker ps --filter "name=prometheus|grafana|exporter|cadvisor"

# Check Prometheus targets
curl http://localhost:9091/api/v1/targets

# View container logs
docker logs prometheus
docker logs grafana
```

### Common Issues

**Grafana Login**: Default credentials are `admin/admin`. Change on first login.

**Missing Metrics**: Some services may need to be running to provide metrics. Start all services:
```bash
docker compose up -d
```

**Ollama Metrics**: Ollama doesn't expose Prometheus metrics natively. Health is monitored via HTTP endpoints.

## 🎯 Next Steps

1. **Custom Dashboards**: Create specialized dashboards for your specific use cases
2. **Alertmanager**: Add Alertmanager for email/Slack notifications
3. **Log Aggregation**: Consider adding ELK stack for log analysis
4. **Distributed Tracing**: Add Jaeger for request tracing

## 📊 Metrics Retention

- **Prometheus**: 200 hours of metrics retention (configurable)
- **Grafana**: Persistent dashboards and configurations
- **Automatic Cleanup**: Old metrics automatically pruned

---

**Your Technical Service Assistant monitoring stack is production-ready!** 🚀

Access Grafana at http://localhost:3001 to start exploring your system metrics and performance dashboards.