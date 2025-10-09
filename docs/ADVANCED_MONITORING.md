# Advanced Monitoring - Phase 2B Implementation

This document describes the comprehensive Prometheus and Grafana monitoring system for the Technical Service Assistant. 

## 🎯 Overview

The monitoring system provides real-time visibility into:
- **System Health**: Service availability and health checks
- **Performance Metrics**: Response times, throughput, and resource utilization  
- **Intelligent Routing**: Model selection accuracy and distribution
- **Database Performance**: Connection pools, query performance, cache hit rates
- **Search Operations**: Vector search performance and embedding generation

## 🏗️ Architecture

### Core Components
- **Prometheus** (`:9090`): Metrics collection and alerting engine
- **Grafana** (`:3001`): Visualization dashboards and analytics
- **Exporters**: Specialized metrics collectors for each service
  - `postgres-exporter` (`:9187`): PostgreSQL metrics
  - `redis-exporter` (`:9121`): Redis cache metrics  
  - `node-exporter` (`:9100`): Host system metrics
  - `cadvisor` (`:8081`): Container metrics

### Metrics Flow
```
Services → Prometheus → Grafana Dashboards
    ↓
Alert Rules → Notifications
```

## 🚀 Quick Start

### 1. Start Monitoring Stack
```bash
# Start all services including monitoring
make up

# Check monitoring services health
docker logs prometheus
docker logs grafana
```

### 2. Access Dashboards
- **Grafana**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9090  
- **cAdvisor**: http://localhost:8081

### 3. Import Dashboards
Pre-configured dashboards are automatically loaded:
- **System Overview**: General health and performance
- **Routing Analytics**: Model selection and accuracy tracking
- **Database Performance**: PostgreSQL and Redis metrics

## 📊 Dashboard Guide

### System Overview Dashboard
**Purpose**: High-level system health monitoring  
**Key Metrics**:
- Service availability status (UP/DOWN indicators)
- Request rate trends (requests/minute)
- Response time percentiles (50th, 90th, 95th, 99th)
- Active request count
- Error rate percentage with color thresholds

**Alert Thresholds**:
- Error Rate > 5% (Critical)
- Response Time > 5s (Warning)
- Service Down > 30s (Critical)

### Routing Analytics Dashboard  
**Purpose**: Intelligent routing performance analysis  
**Key Metrics**:
- Model selection distribution (pie chart)
- Instance utilization breakdown  
- Routing accuracy over time
- Ollama instance health heatmap
- Question classification breakdown

**Critical Insights**:
- Model imbalances indicate routing issues
- Accuracy drops below 80% trigger alerts
- Instance health failures affect availability

### Database Performance Dashboard
**Purpose**: Database and search performance monitoring  
**Key Metrics**:
- PostgreSQL connection pool usage
- Database operation rates (selects, inserts, updates)
- Vector search performance metrics
- Cache hit ratios (PostgreSQL and Redis)
- Embedding generation rates

**Performance Targets**:
- Cache Hit Ratio > 90%
- Connection Pool < 80% utilization
- Vector Search < 1s (95th percentile)

## 🔔 Alerting Rules

### Service Availability Alerts
```yaml
# Service down for > 30 seconds
- alert: RerankerDown
  expr: up{job="reranker"} == 0
  for: 30s
  labels:
    severity: critical
```

### Performance Alerts  
```yaml
# High response time > 5 seconds  
- alert: RerankerHighResponseTime
  expr: reranker_request_duration_seconds > 5.0
  for: 2m
  labels:
    severity: warning

# Error rate > 10%
- alert: RerankerErrorRate  
  expr: rate(reranker_requests_total{status=~"4..|5.."}[5m]) > 0.1
  for: 1m
  labels:
    severity: critical
```

### Resource Alerts
```yaml
# High memory usage > 90%
- alert: HighMemoryUsage
  expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) > 0.9
  for: 5m
  labels:
    severity: critical
```

## 📈 Custom Metrics

### Reranker Service Metrics
The reranker service exposes comprehensive Prometheus metrics:

```python
# Request metrics
REQUEST_COUNT = Counter('reranker_requests_total', 'Total requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('reranker_request_duration_seconds', 'Request duration', ['method', 'endpoint'])
ACTIVE_REQUESTS = Gauge('reranker_active_requests', 'Active requests')

# Routing metrics  
ROUTING_ACCURACY = Gauge('reranker_routing_accuracy', 'Intelligent routing accuracy')
MODEL_SELECTION_COUNT = Counter('reranker_model_selection_total', 'Model selection count', ['model', 'instance'])
OLLAMA_HEALTH = Gauge('reranker_ollama_health', 'Ollama instance health', ['instance'])

# Search metrics
SEARCH_OPERATIONS = Counter('reranker_search_operations_total', 'Search operations', ['type', 'status'])
EMBEDDINGS_GENERATED = Counter('reranker_embeddings_generated_total', 'Embeddings generated')
DATABASE_OPERATIONS = Counter('reranker_database_operations_total', 'Database operations', ['operation', 'status'])
```

### Metrics Endpoints
- **Service Metrics**: http://localhost:8008/metrics (Prometheus format)
- **Health Check**: http://localhost:8008/api/metrics/health (JSON format)

## 🔧 Configuration

### Prometheus Configuration
Located in `monitoring/prometheus/prometheus.yml`:
- Scrape intervals optimized per service type
- Service discovery for dynamic containers  
- Alert rule integration
- Retention policies (200h default)

### Grafana Configuration  
Located in `monitoring/grafana/`:
- Datasource provisioning (automatic Prometheus connection)
- Dashboard provisioning (automatic import)
- Plugin installations (piechart, heatmap)

### Environment Variables
```bash
# Grafana
GF_SECURITY_ADMIN_PASSWORD=admin
GF_USERS_ALLOW_SIGN_UP=false

# Exporters  
DATA_SOURCE_NAME=postgresql://postgres:postgres@pgvector:5432/vector_db
REDIS_ADDR=redis://redis:6379
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. Metrics Not Appearing
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Check service metrics endpoint
curl http://localhost:8008/metrics

# Verify service connectivity
docker logs prometheus
```

#### 2. Dashboard Not Loading
```bash
# Check Grafana logs
docker logs grafana

# Verify dashboard provisioning
ls -la monitoring/grafana/dashboards/

# Check datasource connection
curl http://localhost:3001/api/datasources
```

#### 3. Alert Rules Not Firing
```bash
# Check alert rule syntax
promtool check rules monitoring/prometheus/alerts.yml

# View active alerts
curl http://localhost:9090/api/v1/alerts
```

### Performance Tuning

#### Scrape Interval Optimization
```yaml
# High-frequency for critical services
- job_name: 'reranker'
  scrape_interval: 5s

# Lower frequency for system metrics  
- job_name: 'node'
  scrape_interval: 15s
```

#### Storage Retention
```bash
# Adjust retention in prometheus command
--storage.tsdb.retention.time=200h
--storage.tsdb.retention.size=10GB
```

## 📋 Maintenance

### Regular Tasks
1. **Weekly**: Review dashboard performance, check for metric anomalies
2. **Monthly**: Update Grafana plugins, review alert thresholds  
3. **Quarterly**: Analyze storage usage, optimize scrape intervals

### Backup Procedures
```bash
# Backup Grafana dashboards
docker exec grafana grafana-cli admin export-dashboard

# Backup Prometheus data
docker cp prometheus:/prometheus ./prometheus-backup

# Backup configuration
tar -czf monitoring-config-backup.tar.gz monitoring/
```

## 🎯 Next Steps

### Phase 2C Integration
The monitoring system is designed to support Phase 2C accuracy improvements:
- Enhanced retrieval pipeline metrics
- Hybrid search performance tracking  
- Quality evaluation dashboards

### Advanced Features
- **Distributed Tracing**: Jaeger integration for request tracing
- **Log Aggregation**: ELK stack for centralized logging
- **Anomaly Detection**: ML-based alerting for unusual patterns

## 📞 Support

For monitoring issues or questions:
1. Check Grafana dashboard annotations for known issues
2. Review Prometheus alert history for patterns
3. Analyze service logs for error correlation
4. Consult this documentation for configuration details

---

**Status**: ✅ **PRODUCTION READY** - Advanced monitoring fully implemented with comprehensive dashboards, alerting, and documentation.