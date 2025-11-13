# Quick Reference: Implementation Guide for Latency & Accuracy Improvements

**Document:** Practical implementation steps for each recommendation  
**Date:** November 12, 2025  
**Target:** Phase 1 (Quick Wins) - Complete in 1-2 weeks

---

## Quick Priority Matrix

| Recommendation | Impact | Effort | Time | Start |
|---|---|---|---|---|
| **Streaming Responses** | ⭐⭐⭐⭐⭐ | 🟢 Medium | 2-3 days | **Week 1** |
| **Response Caching** | ⭐⭐⭐⭐ | 🟢 Medium | 2-3 days | **Week 1** |
| **Hybrid Search** | ⭐⭐⭐⭐ | 🟢 Low | 1-2 days | **Week 2** |
| **Semantic Chunking** | ⭐⭐⭐⭐ | 🟡 Medium | 2-3 days | **Week 2** |
| **Query Optimization** | ⭐⭐⭐ | 🟢 Low | 1 day | **Week 1** |
| **Domain Fine-tuning** | ⭐⭐⭐⭐⭐ | 🔴 High | 5-7 days | **Week 3+** |

---

## Implementation Checklist

### Week 1: Foundation (Quick Wins)

#### Task 1.1: Streaming Responses [2-3 days]

**Files to Modify:**
- `reranker/rag_chat.py` — Add streaming support
- `frontend/chat.js` — Update frontend for streaming
- `reranker/app.py` — Create streaming endpoint

**Checklist:**
- [ ] Enable streaming in Ollama HTTP client
- [ ] Convert response to server-sent events (SSE)
- [ ] Update frontend to receive and display tokens
- [ ] Test latency improvement (first token arrival)
- [ ] Load test with streaming enabled
- [ ] Roll back plan if needed

**Expected Result:** 40% perceived latency improvement

---

#### Task 1.2: Response Caching [2-3 days]

**Files to Modify:**
- `reranker/rag_chat.py` — Add cache layer
- `config.py` — Cache configuration (Redis URL, TTL)
- `utils/redis_cache.py` — Extend cache functionality

**Checklist:**
- [ ] Set up Redis connection (if not existing)
- [ ] Implement query fingerprinting (normalize query)
- [ ] Add cache get/set/invalidate logic
- [ ] Set TTL for different query types (1hr for tech, 30min for general)
- [ ] Implement cache invalidation on document updates
- [ ] Test cache hit rate (aim for 20-30%)
- [ ] Monitor cache memory usage
- [ ] Load test with cache

**Expected Result:** 15-20% average latency improvement

---

#### Task 1.3: Query Optimization [1 day]

**Files to Modify:**
- `reranker/rag_chat.py` — Add query preprocessing
- Create `reranker/query_optimizer.py` — New module

**Checklist:**
- [ ] Deduplicate repeated phrases
- [ ] Expand common acronyms (RNI → Radio Network Interface)
- [ ] Normalize whitespace and punctuation
- [ ] Extract and tag entities
- [ ] Test with sample queries
- [ ] Verify it doesn't break existing logic

**Expected Result:** 3-5% latency improvement, +5-10% accuracy

---

### Week 2: Core Improvements

#### Task 2.1: Hybrid Search Integration [1-2 days]

**Files to Use:**
- `scripts/analysis/hybrid_search.py` — Already exists!
- Migrate to: `reranker/hybrid_search.py`

**Checklist:**
- [ ] Copy hybrid_search.py to reranker/
- [ ] Integrate with RAGChatService
- [ ] Add BM25 index to PostgreSQL schema
- [ ] Implement vector + BM25 merging logic
- [ ] A/B test: current vs. hybrid search
- [ ] Measure precision/recall improvement
- [ ] Deploy to production

**Expected Result:** +20-30% accuracy improvement

---

#### Task 2.2: Semantic Chunking Deployment [2-3 days]

**Files to Use:**
- `scripts/analysis/semantic_chunking.py` — Already exists!
- Migrate to: `pdf_processor/semantic_chunking.py`

**Checklist:**
- [ ] Copy semantic_chunking.py to pdf_processor/
- [ ] Update utils.py to use semantic chunking
- [ ] Add feature flag: `ENABLE_SEMANTIC_CHUNKING`
- [ ] Reprocess existing documents (run in background)
- [ ] Compare chunk quality with old approach
- [ ] Monitor retrieval metrics
- [ ] Enable by default once validated

**Expected Result:** +15-25% accuracy improvement

---

#### Task 2.3: Parallel RAG Retrieval [1-2 days]

**Files to Modify:**
- `reranker/rag_chat.py` — Parallelize retrieval stages

**Checklist:**
- [ ] Refactor retrieval to use asyncio.gather
- [ ] Parallelize: embedding generation + vector search + metadata fetch
- [ ] Add timeout handling for parallel operations
- [ ] Test latency (expect 12-20s → 8-12s for RAG phase)
- [ ] Monitor resource utilization
- [ ] Validate accuracy unchanged

**Expected Result:** 2% latency improvement

---

### Week 3+: Advanced Features

#### Task 3.1: Domain Fine-tuning [5-7 days]

**Prerequisites:**
- GPU access (40GB VRAM for 7B model training)
- Training data (500+ RNI Q&A pairs)
- LoRA fine-tuning setup

**Checklist:**
- [ ] Collect RNI domain dataset (500+ Q&A)
- [ ] Format for fine-tuning (JSONL)
- [ ] Set up LoRA fine-tuning environment
- [ ] Fine-tune llama3.2:3b on RNI data (4-8 hours)
- [ ] Deploy fine-tuned model to separate Ollama instance
- [ ] A/B test fine-tuned vs. generic
- [ ] Measure accuracy improvement
- [ ] Integrate into model selection

**Expected Result:** +25-50% accuracy improvement

---

#### Task 3.2: Confidence Scoring [2-3 days]

**Files to Create:**
- `reranker/confidence_scorer.py` — New module

**Checklist:**
- [ ] Implement confidence scoring algorithm
- [ ] Score responses based on:
  - Context relevance
  - Model certainty
  - Query-response alignment
- [ ] Add fallback logic (try alternative if low confidence)
- [ ] Return confidence in API response
- [ ] Display in UI
- [ ] Monitor accuracy of confidence scores

**Expected Result:** +5-15% accuracy improvement

---

#### Task 3.3: Query Expansion [2-3 days]

**Files to Create:**
- `reranker/query_expander.py` — New module

**Checklist:**
- [ ] Implement query expansion with LLM
- [ ] Generate query variants (direct, expanded, synonyms)
- [ ] Search with each variant
- [ ] Merge and deduplicate results
- [ ] Measure recall improvement
- [ ] Monitor LLM cost (one extra LLM call per query)

**Expected Result:** +10-20% accuracy improvement

---

## Code Examples

### Streaming Response (Python/FastAPI)

```python
from fastapi.responses import StreamingResponse
import asyncio

@router.post("/api/chat-stream")
async def chat_stream(request: RAGChatRequest):
    async def generate():
        # Get context
        context = await get_rag_context(request.query)
        
        # Stream from Ollama
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{ollama_url}/api/generate",
                json={
                    "model": request.model,
                    "prompt": f"Context: {context}\n\nQuestion: {request.query}",
                    "stream": True
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        chunk = json.loads(line)
                        if chunk.get("response"):
                            yield f"data: {chunk['response']}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

### Response Caching

```python
from functools import wraps
import hashlib

def cache_response(ttl_seconds=3600):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, request: RAGChatRequest):
            # Generate cache key
            cache_key = hashlib.md5(
                f"{request.query}:{request.model}".encode()
            ).hexdigest()
            
            # Check cache
            cached = await self.cache.get(cache_key)
            if cached:
                logger.info(f"Cache hit: {cache_key}")
                return cached
            
            # Generate response
            response = await func(self, request)
            
            # Cache it
            await self.cache.set(cache_key, response, ex=ttl_seconds)
            return response
        
        return wrapper
    return decorator
```

### Hybrid Search

```python
async def hybrid_search(query: str, k: int = 10):
    # Vector search
    embedding = await get_embedding(query)
    vector_results = await vector_search(embedding, k=50)
    
    # BM25 keyword search
    bm25_results = await bm25_search(query, k=50)
    
    # Merge results (prefer documents in both)
    combined = {}
    for doc in vector_results:
        combined[doc['id']] = doc.copy()
        combined[doc['id']]['score'] = doc.get('score', 0) * 0.6
    
    for doc in bm25_results:
        if doc['id'] in combined:
            combined[doc['id']]['score'] += doc.get('score', 0) * 0.4
        else:
            combined[doc['id']] = doc.copy()
            combined[doc['id']]['score'] = doc.get('score', 0) * 0.4
    
    # Sort and return top-k
    sorted_results = sorted(
        combined.values(),
        key=lambda x: x['score'],
        reverse=True
    )
    return sorted_results[:k]
```

---

## Validation Tests

### Test Streaming Response

```bash
# Run: Test that first token arrives in <10 seconds
curl -N http://localhost:8008/api/chat-stream \
  -d '{"query":"What is FlexNet?"}' \
  -H "Content-Type: application/json" | head -1
```

### Test Caching

```bash
# Run same query twice, measure latency
time curl http://localhost:8008/api/chat -d '{"query":"What is RNI?"}' # ~17s
time curl http://localhost:8008/api/chat -d '{"query":"What is RNI?"}' # ~0.1s
```

### Test Hybrid Search

```python
# Compare vector vs. hybrid
from scripts.analysis.hybrid_search import hybrid_search

vector_results = await vector_search(query, k=10)
hybrid_results = await hybrid_search(query, k=10)

# Measure precision/recall improvement
precision_improvement = measure_precision(hybrid_results, gold_standard)
```

---

## Configuration Updates

### Add to config.py

```python
# Streaming
ENABLE_STREAMING: bool = True
STREAM_BUFFER_SIZE: int = 100  # tokens

# Caching
ENABLE_RESPONSE_CACHE: bool = True
CACHE_TTL_SECONDS: int = 3600
CACHE_REDIS_URL: str = "redis://localhost:6379"

# Chunking
ENABLE_SEMANTIC_CHUNKING: bool = True
CHUNK_STRATEGY: str = "semantic"  # or "sent_overlap"

# Retrieval
ENABLE_HYBRID_SEARCH: bool = True
BM25_WEIGHT: float = 0.3
VECTOR_WEIGHT: float = 0.7

# Query Processing
ENABLE_QUERY_OPTIMIZATION: bool = True
ENABLE_QUERY_EXPANSION: bool = False  # High cost
EXPANSION_DEPTH: int = 1
```

---

## Deployment Checklist

### Before Going Live

- [ ] All tests passing (unit + integration + e2e)
- [ ] Load test with new feature enabled
- [ ] Monitor latency and accuracy metrics
- [ ] Have rollback plan (feature flags)
- [ ] Document changes in CHANGELOG
- [ ] Update API documentation
- [ ] Notify team of changes

### During Deployment

- [ ] Enable feature flag for 10% of traffic
- [ ] Monitor error rate and latency
- [ ] Gradually increase to 50%, then 100%
- [ ] Have on-call support ready

### After Deployment

- [ ] Verify metrics improved as expected
- [ ] Collect user feedback
- [ ] Monitor for any regressions
- [ ] Plan next phase improvements

---

## Estimated Timelines

**Week 1 (Days 1-5):**
- Day 1-2: Streaming responses
- Day 2-3: Response caching
- Day 4-5: Query optimization + testing

**Week 2 (Days 6-10):**
- Day 6-7: Hybrid search integration
- Day 8-9: Semantic chunking
- Day 10: Integration testing

**Week 3+ (Days 11+):**
- Fine-tuning and advanced features
- A/B testing and validation
- Documentation and knowledge transfer

---

## Success Metrics

✅ **Latency:**
- [ ] Streaming first token: < 10 seconds
- [ ] Average E2E with cache: < 15 minutes
- [ ] Cache hit rate: > 20%

✅ **Accuracy:**
- [ ] Hybrid search precision: > 85%
- [ ] Semantic chunking quality: > 90%
- [ ] Domain-specific accuracy (fine-tuned): > 90%

✅ **Throughput:**
- [ ] Concurrent requests: 6-12
- [ ] RPS: 3-6 (sustained)

---

## Resources & References

**Existing Code:**
- `scripts/analysis/hybrid_search.py` (446 lines)
- `scripts/analysis/semantic_chunking.py` (476 lines)
- `scripts/analysis/enhanced_retrieval.py` (446 lines)

**Documentation:**
- `LATENCY_ACCURACY_IMPROVEMENTS.md` — Detailed recommendations
- `ARCHITECTURE.md` — System architecture
- `DEVELOPMENT.md` — Development setup

**Tools & Libraries:**
- Ollama streaming API (built-in)
- Redis (caching backend)
- BM25 (keyword search, via rank-bm25 package)
- LangChain (query expansion, semantic splitting)

---

**Status:** ✅ IMPLEMENTATION GUIDE COMPLETE  
**Next Step:** Start Week 1 tasks with streaming responses
