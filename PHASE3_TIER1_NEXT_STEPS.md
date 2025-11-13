# Phase 3 Tier 1 - Next Steps (Post-Deployment)

## Current Status
✅ **PHASE 3 TIER 1 LIVE IN PRODUCTION**
- Load balancer managing 8 Ollama instances
- Advanced cache (3 layers) initialized
- Monitoring endpoints responding
- All validation tests passed

---

## Immediate Actions (Next 1 Hour)

### 1. Import Grafana Dashboards

```bash
# Dashboard 1: Performance Metrics
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <grafana_token>" \
  -d @monitoring/phase3_performance_dashboard.json

# Dashboard 2: Health Monitoring
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <grafana_token>" \
  -d @monitoring/phase3_health_dashboard.json

# Dashboard 3: Business Metrics
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <grafana_token>" \
  -d @monitoring/phase3_business_dashboard.json
```

Or manually via Grafana UI:
1. Open http://localhost:3000
2. Go to Dashboards → New → Import
3. Upload JSON files from `monitoring/` directory
4. Configure datasources (Prometheus)
5. Save dashboards

### 2. Monitor Live Metrics

```bash
# Check load balancer stats
curl http://localhost:8008/api/load-balancer-stats | jq .

# Check cache stats
curl http://localhost:8008/api/advanced-cache-stats | jq .

# Watch logs
docker logs -f reranker | grep -E "(cache|balancer|load)" 
```

### 3. Generate Test Traffic

```bash
# Run simple queries to warm up caches
python3 << 'EOF'
import requests
import time

for i in range(100):
    query = f"Test query {i % 5}"  # Repeat patterns for cache hits
    # Make request to /api/chat (requires auth)
    time.sleep(0.1)
    print(f"Query {i+1}: {query}")
EOF
```

---

## 24-Hour Monitoring Checklist

- [ ] **Hour 1:** Cache hit rates should start increasing
- [ ] **Hour 2:** Load distribution visible across 8 instances
- [ ] **Hour 4:** Latency should be <100ms for P50
- [ ] **Hour 8:** Cache hit rates should reach >90%
- [ ] **Hour 24:** All metrics stable, performance baseline established

### Key Metrics to Watch

```
✓ Load Balancer Distribution
  - Should see requests across multiple instances
  - No single instance at 100% utilization
  - No unhealthy instances
  
✓ Cache Performance
  - Embedding cache hit rate: 70-80% expected
  - Inference cache hit rate: 40-50% expected  
  - Chunks cache hit rate: 90%+ expected
  - Overall: trending toward 95%+
  
✓ Latency
  - P50 should be <100ms
  - P95 should be <130ms
  - P99 should be <200ms
  
✓ Throughput
  - Should see 3x improvement (30+ QPS)
  - Concurrent users should increase to 30+
```

---

## Monitoring Endpoints Reference

### Load Balancer Stats
```bash
GET /api/load-balancer-stats

Response includes:
- Per-instance metrics (healthy status, request count, avg response time)
- Overall health summary
- Load scores for each instance
```

### Cache Stats
```bash
GET /api/advanced-cache-stats

Response includes:
- Embedding cache: hits, misses, hit_rate
- Inference cache: hits, misses, hit_rate
- Chunks cache: hits, misses, hit_rate
- Overall: total_hits, total_misses, overall_hit_rate
```

### Instance Health
```bash
GET /api/ollama-health

Response includes:
- List of all instances with health status
- Response times
- Load scores
- Last check timestamp
```

---

## Grafana Dashboard Import Steps

### Via UI:
1. **Open Grafana:** http://localhost:3000
2. **Login** with Grafana credentials
3. **Dashboards** → **New** → **Import**
4. **Upload JSON:**
   - `monitoring/phase3_performance_dashboard.json`
   - `monitoring/phase3_health_dashboard.json`
   - `monitoring/phase3_business_dashboard.json`
5. **Select Prometheus** as datasource
6. **Save** each dashboard

### Via API:
```bash
# Get Grafana API token first
# Then use curl commands above

# Or use admin token if already set up
TOKEN="your-grafana-admin-token"
for file in monitoring/phase3_*.json; do
  curl -X POST http://localhost:3000/api/dashboards/db \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d @$file
done
```

---

## Expected Performance Timeline

### Immediately After Deployment
- Cache hit rate: 0% (warming up)
- Load distributed: minimal requests
- Latency: baseline (not yet optimized)

### After 30 minutes
- Cache hit rate: 20-40% (caching popular queries)
- Load distributed across 4-6 instances
- Latency: stable, no degradation

### After 4 hours
- Cache hit rate: 70-90% (most queries cached)
- Load distributed evenly across 8 instances
- Latency: <100ms P50, <130ms P95

### After 24 hours
- Cache hit rate: 95%+ (steady state)
- Load balanced: even distribution
- Latency: stable at targets
- No errors or service degradation

---

## Troubleshooting

### Issue: Load balancer not distributing requests

**Check:**
```bash
curl http://localhost:8008/api/load-balancer-stats | jq .instances
```

**Expected:** All 8 instances with request counts increasing

### Issue: Cache hit rate not increasing

**Check:**
```bash
curl http://localhost:8008/api/advanced-cache-stats | jq .cache
```

**Expected:** Hit counts increasing over time

### Issue: Some instances appearing unhealthy

**Check:**
```bash
docker ps | grep ollama-server
curl http://localhost:8008/api/ollama-health | jq .instances
```

**Fix:** Restart unhealthy containers

### Issue: High latency from endpoints

**Check:**
```bash
docker logs reranker | tail -20
curl http://localhost:8008/health
```

**Expected:** Response times <5ms for stats endpoints

---

## Commands for Common Tasks

### View Real-time Load Balancer Stats
```bash
watch -n 1 'curl -s http://localhost:8008/api/load-balancer-stats | jq'
```

### View Real-time Cache Stats
```bash
watch -n 1 'curl -s http://localhost:8008/api/advanced-cache-stats | jq'
```

### Check Reranker Health
```bash
curl http://localhost:8008/health | jq
```

### View Reranker Logs
```bash
docker logs -f reranker --tail 50
```

### Stop/Start Reranker (if needed)
```bash
docker compose restart reranker
```

### Full System Status
```bash
docker compose ps
```

---

## Success Criteria for Phase 3 Tier 1

- [ ] All 8 instances healthy and responding
- [ ] Cache hit rates trending toward 95%+
- [ ] P50 latency <100ms
- [ ] P95 latency <130ms
- [ ] Throughput 30+ QPS
- [ ] Load distributed evenly across instances
- [ ] No errors in production logs
- [ ] Grafana dashboards displaying real-time metrics
- [ ] 24-hour stability achieved

---

## Phase 3 Tier 2 (Future - Already Designed)

Once Phase 3 Tier 1 is stable:
1. **Query Optimization** - Semantic query expansion
2. **Hybrid Search** - Vector + BM25 combination
3. **Semantic Chunking** - Structure-aware document chunking
4. **Web Search Integration** - Confidence-based fallback

Estimated completion: 2-3 hours

---

## Contact & Support

For issues or questions about Phase 3 Tier 1:

1. Check logs: `docker logs reranker`
2. Check endpoints: `/api/load-balancer-stats`, `/api/advanced-cache-stats`
3. Review dashboards: Grafana → Phase 3 dashboards
4. Check documentation: `PHASE3_TIER1_IMPLEMENTATION.md`

---

**Last Updated:** November 13, 2025  
**Phase:** Phase 3 Tier 1 - Production Deployment  
**Status:** ✅ LIVE
