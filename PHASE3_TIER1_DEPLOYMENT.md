# Phase 3 Tier 1 - Deployment & Testing Guide

## Quick Start: Deploy Phase 3 Tier 1

### Prerequisites
```bash
# 1. Ensure all 8 Ollama instances are running
docker compose ps | grep ollama

# 2. Verify Redis is running (both DB 0 and DB 1)
docker compose ps | grep redis
redis-cli PING

# 3. Verify Prometheus is collecting metrics
curl http://localhost:9090/api/v1/query?query=up

# 4. Ensure Grafana is accessible
curl http://localhost:3000/
```

## Deployment Steps

### Step 1: Build New Reranker Image
```bash
docker compose build reranker --no-cache
```

Expected output:
```
Building reranker
...
Successfully built <image-id>
Successfully tagged technical-service-assistant-reranker:latest
```

### Step 2: Start the Stack
```bash
# Bring up all services
docker compose up -d

# Wait for health checks
sleep 10

# Verify services
docker compose ps
```

Expected output (all services UP):
```
NAME                      STATE
ollama-server-1           Up
ollama-server-2           Up
...
ollama-server-8           Up
reranker                  Up
redis                     Up
postgres                  Up
prometheus                Up
grafana                   Up
```

### Step 3: Verify Tier 1 Components

#### Check Load Balancer Initialization
```bash
docker logs reranker 2>&1 | grep -i "load.*balanc"
```

Expected output:
```
Using all 8 Ollama instances for load balancing
Initialized load balancer (load balancer connected)
```

#### Check Advanced Cache Initialization
```bash
docker logs reranker 2>&1 | grep -i "advanced.*cache"
```

Expected output:
```
Advanced cache initialized (Redis DB 1 connected)
```

#### Test Load Balancer Stats Endpoint
```bash
curl -s http://localhost:8008/api/load-balancer-stats | jq .
```

Expected output:
```json
{
  "success": true,
  "instances": {
    "http://ollama-server-1:11434": {
      "healthy": true,
      "total_requests": 0,
      "successful_requests": 0,
      "failed_requests": 0,
      "average_response_time": "0.00ms",
      "success_rate": "N/A%",
      "load_score": "0.00"
    },
    ...
  },
  "overall": {
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "overall_success_rate": "N/A%",
    "healthy_instances": 8,
    "total_instances": 8
  }
}
```

#### Test Advanced Cache Stats Endpoint
```bash
curl -s http://localhost:8008/api/advanced-cache-stats | jq .
```

Expected output:
```json
{
  "success": true,
  "cache": {
    "enabled": true,
    "embedding": {
      "hits": 0,
      "misses": 0,
      "total": 0,
      "hit_rate": "N/A%"
    },
    "inference": {
      "hits": 0,
      "misses": 0,
      "total": 0,
      "hit_rate": "N/A%"
    },
    "chunks": {
      "hits": 0,
      "misses": 0,
      "total": 0,
      "hit_rate": "N/A%"
    },
    "overall": {
      "total_hits": 0,
      "total_misses": 0,
      "overall_hit_rate": "N/A%"
    }
  }
}
```

---

## Testing Phase

### Test 1: Load Balancer Distribution

Run a test to generate requests and verify load distribution:

```bash
# Generate 100 requests
for i in {1..100}; do
  curl -s -X POST http://localhost:8008/api/chat \
    -H "Content-Type: application/json" \
    -d '{
      "query": "What is Python?",
      "model": "auto",
      "use_context": false,
      "stream": false
    }' > /dev/null &
done

wait

# Check distribution
sleep 5
curl -s http://localhost:8008/api/load-balancer-stats | jq '.overall'
```

Expected output:
```json
{
  "total_requests": 100,
  "successful_requests": 100,
  "failed_requests": 0,
  "overall_success_rate": "100.0%",
  "healthy_instances": 8,
  "total_instances": 8
}
```

Per-instance distribution should be roughly equal (e.g., 12-13 requests per instance).

### Test 2: Embedding Cache Effectiveness

```bash
# Run same query multiple times
QUERY="How do I optimize database queries?"

echo "First run (cache miss):"
time curl -s -X POST http://localhost:8008/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$QUERY\", \"use_context\": true, \"stream\": false}" | jq '.response' | head -c 100

sleep 2

echo -e "\n\nSecond run (cache hit):"
time curl -s -X POST http://localhost:8008/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$QUERY\", \"use_context\": true, \"stream\": false}" | jq '.response' | head -c 100

# Check cache stats
echo -e "\n\nCache stats after 2 queries:"
curl -s http://localhost:8008/api/advanced-cache-stats | jq '.cache.embedding'
```

Expected output:
```
First run (cache miss):
real    0m1.234s  (full latency)

Second run (cache hit):
real    0m0.089s  (much faster - embedding cached)

Cache stats:
{
  "hits": 1,
  "misses": 1,
  "total": 2,
  "hit_rate": "50.0%"
}
```

### Test 3: Latency Improvement Measurement

Use the Phase 1 validation test to measure improvements:

```bash
# Run Phase 1 validation (20 queries)
python phase1_validation_test.py 2>&1 | tee /tmp/phase3_tier1_results.log

# Extract metrics
grep -E "Mean|P50|P95|hit_rate" /tmp/phase3_tier1_results.log
```

Expected improvements over baseline (122ms P50):
- P50: 122ms → <100ms (18% improvement)
- P95: ~150ms → <130ms (13% improvement)
- Cache hit rate: 92.68% → 97%+ (5% improvement)

### Test 4: Grafana Dashboard Import

Import the three dashboards into Grafana:

```bash
# Get Grafana API token (admin:admin for default)
GRAFANA_URL="http://localhost:3000"
API_TOKEN=$(curl -s -X POST $GRAFANA_URL/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user":"admin","password":"admin"}' | jq -r '.token')

# Import Performance Dashboard
curl -s -X POST $GRAFANA_URL/api/dashboards/db \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_TOKEN" \
  -d @monitoring/phase3_performance_dashboard.json

# Import Health Dashboard
curl -s -X POST $GRAFANA_URL/api/dashboards/db \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_TOKEN" \
  -d @monitoring/phase3_health_dashboard.json

# Import Business Dashboard
curl -s -X POST $GRAFANA_URL/api/dashboards/db \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_TOKEN" \
  -d @monitoring/phase3_business_dashboard.json

echo "✅ Dashboards imported successfully"
```

Then access Grafana:
- Open http://localhost:3000/
- Click "Dashboards" → "Browse"
- Find "Phase 3 Tier 1 - Performance Monitoring"
- Verify metrics are flowing (not "No data")

---

## Post-Deployment Monitoring (24-hour window)

### Hour 1: Immediate Verification
```bash
# 1. Check all instances are healthy
curl -s http://localhost:8008/api/load-balancer-stats | jq '.overall.healthy_instances'

# 2. Monitor initial cache hits
watch -n 5 'curl -s http://localhost:8008/api/advanced-cache-stats | jq ".cache.overall.overall_hit_rate"'

# 3. Check error rate
docker logs reranker 2>&1 | grep -i error | wc -l
```

### Hours 1-8: Baseline Establishment
- Cache hit rate should climb as queries repeat: 0% → 50% → 80% → 95%+
- Load distribution should balance across 8 instances
- P50 latency should stabilize around 95-100ms
- No errors should appear in logs

### Hours 8-24: Sustained Operation
- Monitor via Grafana dashboards
- Verify cache hit rate maintains 95%+
- Verify error rate stays <0.1%
- Verify P50 latency stays <100ms

### Daily Health Check
```bash
# Run this command daily
./scripts/phase3_tier1_health_check.sh
```

---

## Troubleshooting

### Issue: Load Balancer Not Initializing
```bash
docker logs reranker 2>&1 | grep -A5 "load.*balanc"
```

Solution: Check that all 8 Ollama instances are running:
```bash
docker compose ps | grep ollama | wc -l
# Should show 8
```

### Issue: Advanced Cache Not Working
```bash
docker logs reranker 2>&1 | grep -A5 "advanced.*cache"
```

Solution: Verify Redis is running on DB 1:
```bash
redis-cli -n 1 PING
# Should return PONG
```

### Issue: High Error Rate After Deployment
Check recent logs:
```bash
docker logs reranker 2>&1 | tail -100 | grep -i error
```

Solution: Likely cause is memory pressure. Restart stack:
```bash
docker compose down
docker compose up -d
```

### Issue: Latency Not Improving
Check if load distribution is unbalanced:
```bash
curl -s http://localhost:8008/api/load-balancer-stats | jq '.instances | to_entries[] | {instance: .key, requests: .value.total_requests}'
```

Solution: If one instance has majority of requests, it may be unhealthy. Check:
```bash
docker logs <unhealthy-instance> 2>&1 | tail -20
```

---

## Rollback Procedure

If Tier 1 causes issues, rollback to Phase 2:

```bash
# 1. Stop stack
docker compose down

# 2. Revert to previous reranker image (if available)
# or rebuild without latest changes
git checkout HEAD~1 reranker/load_balancer.py reranker/advanced_cache.py reranker/rag_chat.py

# 3. Rebuild
docker compose build reranker

# 4. Restart
docker compose up -d

# 5. Verify health
curl http://localhost:8008/health
```

Note: All changes are backward compatible and don't modify data structures, so rollback is safe.

---

## Success Criteria

✅ **Tier 1 deployment successful when:**

- [ ] All 8 Ollama instances show healthy
- [ ] Load distribution balanced (within ±10% per instance)
- [ ] Cache hit rate reaches 95%+ within 1 hour
- [ ] P50 latency <100ms (↓ from 122ms)
- [ ] P95 latency <130ms (↓ from ~150ms)
- [ ] Error rate <0.1%
- [ ] Three dashboards show data flowing
- [ ] No critical errors in logs
- [ ] All endpoints responding normally

---

## Next Steps

After 24-hour validation:

1. Document final metrics in PHASE3_TIER1_RESULTS.md
2. Review dashboard data for anomalies
3. Collect feedback from team
4. Begin Phase 3 Tier 2 planning (API auth, connection pooling, index tuning)

---

## Command Summary

```bash
# Quick validation script
echo "=== Tier 1 Deployment Validation ===" && \
docker compose ps | grep -E "ollama|reranker|redis" && \
echo && \
echo "Load Balancer Health:" && \
curl -s http://localhost:8008/api/load-balancer-stats | jq '.overall' && \
echo && \
echo "Advanced Cache Status:" && \
curl -s http://localhost:8008/api/advanced-cache-stats | jq '.cache.overall'
```

Save as `scripts/phase3_tier1_validation.sh` and run anytime to verify status.
