# Daily Morning Checklist - Technical Service Assistant

**🌅 MANDATORY DAILY STARTUP ROUTINE**  
**Complete this checklist every morning before any development work or enhancements.**

---

## ✅ Phase 1: Docker Container Health Check

### 1.1 Container Status Verification
```bash
# Check all container status
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Expected containers (should all show "Up X minutes/hours"):
# - pgvector (PostgreSQL + pgvector)
# - pdf_processor (Document ingestion worker)
# - reranker (FastAPI service - port 8008)
# - ollama-server-1 (port 11434)
# - ollama-server-2 (port 11435) 
# - ollama-server-3 (port 11436)
# - ollama-server-4 (port 11437)
# - technical-service-assistant (Frontend - port 8080, renamed from next-rag-app-rag-app-1)
# - searxng (Privacy search engine - port 8888)
```

### 1.2 Start Missing Containers
```bash
# If any containers are stopped, restart the entire stack
make down && make up

# Or restart specific services:
docker compose restart <service-name>
```

### 1.3 Health Check Endpoints
```bash
# Test core service endpoints
curl -f http://localhost:8008/health || echo "❌ Reranker service down"
curl -f http://localhost:11434/api/tags || echo "❌ Ollama-1 down"
curl -f http://localhost:11435/api/tags || echo "❌ Ollama-2 down" 
curl -f http://localhost:11436/api/tags || echo "❌ Ollama-3 down"
curl -f http://localhost:11437/api/tags || echo "❌ Ollama-4 down"
curl -f http://localhost:8888 || echo "❌ SearXNG down"
curl -f http://localhost:8080 || echo "❌ Frontend down"
```

**✅ CHECKPOINT: All containers must be "Up" before proceeding**

---

## 📋 Phase 2: Log Review & Issue Detection

### 2.1 Container Log Analysis (Last 24 Hours)
```bash
# Check container logs for errors in last 24 hours
echo "=== PDF Processor Logs ===" 
docker logs --since="24h" pdf_processor | grep -E "(ERROR|FATAL|Exception|Failed)" | tail -10

echo -e "\n=== Reranker Service Logs ==="
docker logs --since="24h" reranker | grep -E "(ERROR|FATAL|Exception|Failed)" | tail -10

echo -e "\n=== Database Logs ==="
docker logs --since="24h" pgvector | grep -E "(ERROR|FATAL|Exception|Failed)" | tail -10

echo -e "\n=== Ollama Instance Logs ==="
for i in {1..4}; do
    echo "--- Ollama Server $i ---"
    docker logs --since="24h" ollama-server-$i | grep -E "(ERROR|FATAL|Exception|Failed)" | tail -5
done

echo -e "\n=== Frontend Logs ==="
docker logs --since="24h" technical-service-assistant | grep -E "(ERROR|FATAL|Exception|Failed)" | tail -10
```

### 2.2 System Log Files Review
```bash
# Check application log files for issues
echo "=== Application Log Files (Last 24 Hours) ===" 
find logs/ -name "*.log" -mtime -1 -exec echo "=== {} ===" \; -exec tail -20 {} \;

# Check for disk space issues
df -h | grep -E "(Use%|[8-9][0-9]%|100%)"

# Check memory usage
free -h
```

### 2.3 Critical Error Patterns to Address
**🚨 Immediate Action Required If Found:**
- Database connection failures
- Ollama model loading errors  
- PDF processing failures
- Memory/disk space warnings (>85%)
- Authentication/security errors
- Network connectivity issues

**✅ CHECKPOINT: Document and resolve any critical errors before proceeding**

---

## 🔍 Phase 3: End-to-End Functionality Testing

### 3.1 Database Connectivity & Content
```bash
# Test database connection and check content
docker exec -it pgvector psql -U postgres -d postgres -c "
SELECT 
    (SELECT COUNT(*) FROM documents) as documents,
    (SELECT COUNT(*) FROM document_chunks) as chunks,
    (SELECT COUNT(*) FROM search_events) as search_events;
"

# Test vector search capability
docker exec -it pgvector psql -U postgres -d postgres -c "
SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL;
"
```

### 3.2 AI Model Availability
```bash
# Verify all Ollama models are loaded
echo "=== Available Models on Each Instance ==="
for port in 11434 11435 11436 11437; do
    echo "--- Port $port ---"
    curl -s http://localhost:$port/api/tags | jq -r '.models[]?.name' | head -5
done
```

### 3.3 API Endpoint Testing
```bash
# Test core API endpoints
echo "=== Testing Core APIs ==="

# Data Dictionary API
curl -s "http://localhost:8008/api/data-dictionary/health" | jq '.'

# RNI Versions
curl -s "http://localhost:8008/api/data-dictionary/rni-versions" | jq '.[] | .version' | head -3

# Database Instances  
curl -s "http://localhost:8008/api/data-dictionary/database-instances" | jq '.[] | .name' | head -3

# Intelligent Routing Test
curl -X POST http://localhost:8008/api/intelligent-route \
  -H "Content-Type: application/json" \
  -d '{"query":"test system health"}' | jq '.'
```

### 3.4 Document Processing Pipeline
```bash
# Check document processing status
echo "=== Document Processing Status ==="
ls -la uploads/ | grep -E "\.pdf$" | wc -l | xargs echo "PDFs in uploads:"

# Check processing logs (last 5 cycles)
docker logs --tail 50 pdf_processor | grep -E "(Found|Processing|complete)" | tail -10
```

### 3.5 Frontend Interface Testing
```bash
# Test frontend accessibility
curl -f http://localhost:8080/ > /dev/null && echo "✅ Frontend accessible" || echo "❌ Frontend issues"

# Test data dictionary interface
curl -f http://localhost:8080/data-dictionary > /dev/null && echo "✅ Data Dictionary accessible" || echo "❌ Data Dictionary issues"
```

### 3.6 Search & RAG Functionality
```bash
# Test hybrid search (if documents exist)
curl -X POST http://localhost:8008/api/hybrid-search \
  -H "Content-Type: application/json" \
  -d '{"query":"system installation", "confidence_threshold":0.3}' | jq '.confidence_score'

# Test web search fallback
curl -X GET "http://localhost:8008/api/test-web-search" | jq '.results | length'
```

**✅ CHECKPOINT: All functionality tests must pass before development work**

---

## 📊 Phase 4: Performance & Resource Monitoring

### 4.1 System Resource Check
```bash
# Check container resource usage
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

# Check disk usage
du -sh uploads/ logs/ 
df -h . | tail -1
```

### 4.2 Database Performance
```bash
# Check database performance metrics
docker exec -it pgvector psql -U postgres -d postgres -c "
SELECT 
    schemaname,
    tablename, 
    n_tup_ins as inserts, 
    n_tup_upd as updates,
    n_tup_del as deletes
FROM pg_stat_user_tables 
WHERE schemaname = 'public';
"
```

**✅ CHECKPOINT: System performance within acceptable ranges**

---

## 🚨 Issue Resolution Protocols

### Critical Issues (Stop All Work)
- **Any container consistently failing to start**
- **Database connectivity lost** 
- **>90% disk usage**
- **Memory exhaustion** 
- **Security alerts in logs**

**Action:** Resolve immediately before any development work.

### Warning Issues (Monitor Closely)  
- **Intermittent API timeouts**
- **>80% disk usage**
- **Slow search response times**
- **PDF processing backlogs**

**Action:** Schedule resolution within 24 hours.

### Info Issues (Track & Plan)
- **Minor log warnings** 
- **Performance optimization opportunities**
- **Feature enhancement requests**

**Action:** Add to backlog for future sprints.

---

## 📝 Daily Checklist Summary

**Date:** ___________  
**Completed By:** ___________

- [ ] **Phase 1:** All Docker containers running ✅
- [ ] **Phase 2:** No critical errors in logs ✅  
- [ ] **Phase 3:** All functionality tests pass ✅
- [ ] **Phase 4:** Performance within acceptable ranges ✅
- [ ] **Issues Found:** _____________ (Document any issues)
- [ ] **Actions Taken:** _____________ (Resolution steps)
- [ ] **System Ready for Development:** ✅

**⚡ SYSTEM STATUS:** 🟢 Ready | 🟡 Caution | 🔴 Critical Issues

---

## 🛠️ Quick Commands Reference

```bash
# Complete system restart
make down && make up

# View all logs
make logs

# Run full test suite  
make test

# Database reset (DESTRUCTIVE - backup first!)
make recreate-db

# System health overview
docker ps && docker stats --no-stream
```

**💡 Remember:** Never skip this checklist. A healthy system is the foundation for successful development.