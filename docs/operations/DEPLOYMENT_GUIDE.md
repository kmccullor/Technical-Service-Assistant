# Technical Service Assistant - Deployment & Maintenance Guide

**Date:** October 7, 2025  
**Version:** Production v2.1  
**Target Audience:** System Administrators & DevOps Engineers

---

## 🚀 Quick Deployment Guide

### Prerequisites
- **Operating System**: Linux (Ubuntu 20.04+ recommended)
- **Docker**: Version 20.10+ with Docker Compose v2
- **Hardware**: 16GB RAM minimum, 32GB recommended
- **Storage**: 100GB+ available disk space
- **Network**: Ports 3000, 5432, 6379, 8008, 8050, 9091, 11434-11437 available

### One-Command Deployment
```bash
# Clone and deploy
git clone https://github.com/your-org/Technical-Service-Assistant.git
cd Technical-Service-Assistant
make up
```

### Verification Steps
```bash
# Check all services are healthy
docker compose ps

# Test API endpoints
curl http://localhost:8008/health
curl http://localhost:8050/health
curl http://localhost:3000/api/status

# Verify monitoring
open http://localhost:3001  # Grafana (admin/admin)
open http://localhost:9091  # Prometheus
```

---

## 🔧 Configuration Management

### Environment Variables
Critical environment variables in `.env`:

```bash
# Database Configuration
DB_HOST=pgvector
DB_PORT=5432
DB_NAME=vector_db
DB_USER=postgres
DB_PASSWORD=your_secure_password_here

# Security
API_KEY=your_api_key_here
JWT_SECRET=your_jwt_secret_here
ALLOWED_ORIGINS=*

# Performance Tuning
RERANK_TOP_K=5
RETRIEVAL_CANDIDATES=50
MAX_CONTEXT_TOKENS=4000
CACHE_TTL=3600

# Feature Flags
ENABLE_TABLE_EXTRACTION=true
ENABLE_IMAGE_EXTRACTION=true
ENABLE_OCR=true
ENABLE_FEEDBACK=true
```

### Service Configuration

#### Ollama Container Configuration
```bash
# Pull required models to all 4 containers
for port in 11434 11435 11436 11437; do
    curl -X POST http://localhost:$port/api/pull \
        -d '{"name": "nomic-embed-text:v1.5"}'
    curl -X POST http://localhost:$port/api/pull \
        -d '{"name": "mistral:7b"}'
done
```

#### Database Initialization
```bash
Run the `init.sql` file against the pgvector container (database `vector_db`) after first startup if migrations are not automated.
docker compose exec pgvector psql -U postgres -d vector_db -c "
CREATE EXTENSION IF NOT EXISTS vector;
docker exec -i pgvector psql -U postgres -d vector_db < init.sql
"

### Standardized Access
Use the helper script for consistent access:
```bash
bin/psql-vector -c "SELECT COUNT(*) FROM documents;"
```

All new scripts should target:
```
Host: pgvector
DB:   vector_db
User: postgres
Port: 5432
```

Avoid hard-coding `-d postgres` in operational scripts—this leads to writing objects into the wrong database. Always reference `vector_db` (or use `DB_NAME` env var consumed by `config.py`).
```

---

## 📊 Health Monitoring & Alerts

### Health Check Endpoints
| Service | Health Endpoint | Expected Response |
|---------|----------------|-------------------|
| API | `http://localhost:8008/health` | `{"status": "ok"}` |
| Reasoning | `http://localhost:8050/health` | `{"status": "ok"}` |
| Frontend | `http://localhost:3000/api/status` | `{"status": "healthy"}` |
| Database | `docker compose exec pgvector pg_isready` | `ready` |

### Monitoring Dashboard Access
- **Grafana**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9091
- **Container Metrics**: http://localhost:8081 (cAdvisor)

### Key Metrics to Monitor
```bash
# System performance metrics
curl -s http://localhost:9091/api/v1/query?query=avg_query_duration_seconds
curl -s http://localhost:9091/api/v1/query?query=container_cpu_usage_seconds_total
curl -s http://localhost:9091/api/v1/query?query=container_memory_usage_bytes
```

---

## 🛠️ Maintenance Procedures

### Daily Maintenance
```bash
# Check system health
make logs | grep -i error
docker compose ps | grep -v healthy

# Monitor resource usage
docker stats --no-stream

# Check disk space
df -h
du -sh uploads/ logs/
```

### Weekly Maintenance
```bash
# Update documentation
git pull origin main

# Clean up old logs
find logs/ -name "*.log" -mtime +7 -delete

# Database maintenance
docker compose exec pgvector psql -U postgres -d vector_db -c "VACUUM ANALYZE;"

# Backup system state
./scripts/backup_system.sh
```

### Monthly Maintenance
```bash
# Security updates
docker compose pull
docker compose up -d

# Performance review
python scripts/performance_report.py

# Capacity planning
python scripts/capacity_analysis.py
```

---

## 🔒 Security Procedures

### API Key Rotation
```bash
# Generate new API key
python scripts/rotate_api_key.py --preview

# Apply rotation
python scripts/rotate_api_key.py --apply

# Restart services
docker compose restart reranker technical-service-assistant
```

### User Management
```bash
# Create admin user
python scripts/setup_rbac_data.py

# List active users
curl -H "X-API-Key: $API_KEY" http://localhost:8008/api/auth/users

# Disable user
curl -X PUT -H "X-API-Key: $API_KEY" \
    http://localhost:8008/api/auth/users/123/disable
```

### Security Audit
```bash
# Check for vulnerabilities
docker compose exec reranker bandit -r . -f json

# Review access logs
docker compose logs reranker | grep "401\|403\|429"

# Check SSL certificates (if applicable)
openssl x509 -in cert.pem -text -noout
```

---

## 📦 Backup & Recovery

### Automated Backup
```bash
# Setup automated backup (cron)
echo "0 2 * * * /path/to/Technical-Service-Assistant/scripts/backup_system.sh" | crontab -

# Manual backup
./scripts/backup_system.sh
```

### Recovery Procedures
```bash
# Stop services
docker compose down

# Restore database
docker compose up -d pgvector
docker compose exec pgvector psql -U postgres -d vector_db < backup/database_20251007.sql

# Restore configuration
tar -xzf backup/config_20251007.tar.gz

# Restore uploads
tar -xzf backup/uploads_20251007.tar.gz

# Start all services
docker compose up -d
```

---

## 🚨 Troubleshooting Guide

### Common Issues

#### Service Won't Start
```bash
# Check logs
docker compose logs [service-name]

# Check port conflicts
netstat -tulpn | grep :[port]

# Reset container
docker compose stop [service-name]
docker compose rm [service-name]
docker compose up -d [service-name]
```

#### Performance Issues
```bash
# Check resource usage
docker stats

# Monitor query performance
curl -s http://localhost:8008/api/metrics | grep query_duration

# Check database connections
docker compose exec pgvector psql -U postgres -d vector_db -c "
SELECT state, count(*) FROM pg_stat_activity GROUP BY state;
"
```

#### Database Issues
```bash
# Check database status
docker compose exec pgvector pg_isready -U postgres

# Monitor database performance
docker compose exec pgvector psql -U postgres -d vector_db -c "
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY total_time DESC 
LIMIT 10;
"

# Rebuild indexes if needed
docker compose exec pgvector psql -U postgres -d vector_db -c "REINDEX DATABASE vector_db;"
```

### Emergency Procedures

#### Service Recovery
```bash
# Restart all services
docker compose restart

# Restart specific service
docker compose restart [service-name]

# Complete reset (last resort)
docker compose down
docker compose up -d
```

#### Data Recovery
```bash
# Restore from backup
./scripts/restore_system.sh [backup-date]

# Manual data recovery
docker compose exec pgvector pg_dump -U postgres vector_db > emergency_backup.sql
```

---

## 📈 Performance Optimization

### Database Optimization
```sql
-- Optimize vector search performance
CREATE INDEX CONCURRENTLY idx_document_chunks_embedding_hnsw 
ON document_chunks USING hnsw (embedding vector_cosine_ops) 
WITH (m = 16, ef_construction = 64);

-- Optimize metadata queries
CREATE INDEX CONCURRENTLY idx_document_chunks_metadata_gin 
ON document_chunks USING gin(metadata);
```

### Cache Optimization
```bash
# Monitor Redis performance
docker compose exec redis redis-cli info stats

# Adjust cache settings
docker compose exec redis redis-cli config set maxmemory-policy allkeys-lru
```

### Container Resource Limits
```yaml
# In docker-compose.yml
services:
  reranker:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

---

## 📋 Checklist Templates

### Pre-Deployment Checklist
- [ ] Environment variables configured
- [ ] SSL certificates installed (if applicable)
- [ ] Firewall rules configured
- [ ] Backup procedures tested
- [ ] Monitoring configured
- [ ] Documentation updated

### Post-Deployment Checklist
- [ ] All services healthy
- [ ] API endpoints responding
- [ ] Database connected and operational
- [ ] Monitoring dashboards accessible
- [ ] Test queries returning results
- [ ] Backup system functional

### Monthly Review Checklist
- [ ] Performance metrics reviewed
- [ ] Security audit completed
- [ ] Capacity planning updated
- [ ] Documentation current
- [ ] Backup tests successful
- [ ] User feedback addressed

---

**Deployment Guide Maintained By:** Technical Service Assistant Team  
**Last Updated:** October 7, 2025  
**Next Review:** November 7, 2025  
**Support:** technical-service-assistant@yourorg.com