# Daily Morning Checklist - Quick Start Guide

## 🌅 Quick Start

**Run this every morning before development work:**

```bash
make morning
```

This single command will:
1. ✅ Check all Docker containers are running
2. 🔍 Scan logs for critical errors (last 24 hours)  
3. 🧪 Test all functionality end-to-end
4. 📊 Monitor system performance and resources
5. 📋 Generate a detailed status report

## Individual Commands

```bash
# Quick health check (30 seconds)
make health-check

# Full automated checklist (2-3 minutes)
make daily-checklist

# Check recent error logs only
make check-logs

# Manual checklist (follow step-by-step)
open DAILY_MORNING_CHECKLIST.md
```

## Status Indicators

- 🟢 **Ready for Development** - All systems operational
- 🟡 **Caution** - Minor issues, monitor closely
- 🔴 **Critical Issues** - Must resolve before development

## Common Issues & Quick Fixes

### Missing Containers
```bash
# Restart entire stack
make down && make up
```

### API Endpoints Not Responding
```bash
# Check specific container logs
docker logs reranker
docker logs ollama-server-1

# Restart specific service
docker compose restart reranker
```

### High Resource Usage
```bash
# Check resource usage
docker stats --no-stream

# Check disk space
df -h
du -sh uploads/ logs/
```

### Database Issues
```bash
# Test database connection
docker exec -it pgvector psql -U postgres -d postgres -c "SELECT 1;"

# Reset database (DESTRUCTIVE!)
make recreate-db
```

## Log Files

Daily checklist logs are saved to:
- `logs/daily_checklist_YYYYMMDD.log`

Container logs accessible via:
- `docker logs <container_name>`
- `make logs` (PDF processor)

## Integration with Development Workflow

**Mandatory:** Run `make morning` before:
- Adding new features
- Making code changes
- Deploying updates
- Performance testing
- Security reviews

**Never skip the morning checklist** - it ensures a stable foundation for all development work.