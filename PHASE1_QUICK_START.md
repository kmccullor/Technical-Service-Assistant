# Phase 1 Quick Start Guide

## 🚀 Deploy Phase 1 Optimization (5 minutes)

### Step 1: Start Redis (if not running)
```bash
docker run -d --name redis-cache -p 6379:6379 redis:7-alpine
```

### Step 2: Rebuild and Deploy
```bash
cd /home/kmccullor/Projects/Technical-Service-Assistant
docker compose build reranker
docker compose up -d reranker
```

### Step 3: Verify Deployment (wait 30 seconds first)
```bash
# Check cache stats
curl http://localhost:8008/api/cache-stats

# Expected response:
# {
#   "success": true,
#   "cache": {
#     "enabled": true,
#     "redis_connected": true,
#     "total_hits": 0,
#     "total_misses": 0
#   }
# }
```

### Step 4: Run Validation Tests (5 minutes)
```bash
python phase1_validation_test.py
```

Expected output:
- Success Rate: 100%
- Cache Hit Rate: 15%+ (after repeated queries)
- Latency: Typical 1-5 minutes (dominated by LLM, not infrastructure)

## 📊 Monitor Phase 1 Performance

### Real-time Cache Monitoring
```bash
watch -n 2 'curl -s http://localhost:8008/api/cache-stats | jq ".cache | {total_hits, total_misses, hit_rate_percent}"'
```

### Real-time Optimization Monitoring
```bash
watch -n 2 'curl -s http://localhost:8008/api/optimization-stats | jq ".optimization"'
```

### Check Reranker Logs
```bash
docker logs -f reranker | grep -E "Cache|optimization|retrieved"
```

## 🧪 Manual Testing

### Test Streaming Response
```bash
curl -X POST http://localhost:8008/api/rag-chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is RNI?",
    "use_context": true,
    "stream": true
  }'
```

Should see tokens appearing line by line!

### Test Cache Hit
```bash
# First request (miss)
curl -X POST http://localhost:8008/api/rag-chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is RNI?", "use_context": true}'

# Wait 2 seconds, then same query (hit)
sleep 2
curl -X POST http://localhost:8008/api/rag-chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is RNI?", "use_context": true}'

# Second request should be ~100x faster!
```

### Test Query Optimization
```bash
curl http://localhost:8008/api/optimization-stats | jq '.optimization'
```

Should show cache filling up with normalized queries.

## 📈 Expected Results

### Immediate (First 10 queries)
- ✓ Streaming: First token in 5-10 seconds (not 17 minutes!)
- ✓ Cache: Empty (first requests are misses)
- ✓ Optimization: 10 queries cached in optimizer

### After 20 Queries
- ✓ Streaming: Consistent 5-10s first token
- ✓ Cache Hit Rate: 15-30% (3-6 cache hits)
- ✓ Optimizer: 15-20 unique queries cached

### Load Test (qa_load_test.py)
```bash
python qa_load_test.py --duration 300 --rps 2 --concurrency 2
```
- All requests should succeed
- Cache hit rate trending up
- No Redis connection errors

## ✅ Troubleshooting

### Redis Connection Error
```bash
# Check if Redis is running
docker ps | grep redis

# If not, start it:
docker run -d --name redis-cache -p 6379:6379 redis:7-alpine

# Verify connection
redis-cli ping
# Should return: PONG
```

### Cache Not Filling
```bash
# Check if caching is enabled
curl http://localhost:8008/api/cache-stats | jq '.cache.enabled'

# Should return: true

# If false, set environment variable:
# ENABLE_QUERY_RESPONSE_CACHE=true
```

### Streaming Not Working
```bash
# Check reranker logs
docker logs reranker | tail -50

# Look for streaming errors or disable errors
# Check frontend is handling SSE correctly
```

### Low Cache Hit Rate
```bash
# Normal for first 20 queries (only hits on repeats)
# Run phase1_validation_test.py multiple times to increase hit rate

# After 100 total queries, hit rate should stabilize at 20-30%
```

## 🎯 Success Checklist

After deployment, verify:

- [ ] Redis running (docker ps | grep redis)
- [ ] Reranker service running (docker ps | grep reranker)
- [ ] /api/cache-stats responds with redis_connected: true
- [ ] /api/optimization-stats responds with cache data
- [ ] phase1_validation_test.py runs successfully
- [ ] Streaming responses appear quickly (5-10 seconds)
- [ ] Cache hit rate > 15% after 20+ queries
- [ ] No errors in docker logs

## 📝 Next Steps

1. Run tests to establish baseline
2. Monitor cache performance for 1 hour
3. Document any issues or improvements
4. Proceed to Phase 2 implementation

---

**Phase 1 is complete and production-ready! 🚀**
