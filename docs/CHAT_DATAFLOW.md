# Chat Dataflow Architecture: Question Decomposition & Intelligent Routing

## Overview

This document describes the enhanced chat dataflow that decomposes complex questions into simpler sub-requests, routes each to appropriately-sized models, and caches results in Redis for fast retrieval.

### Current Flow (Pre-Enhancement)
```
User Query
    ↓
RAG Service (single-pass)
    ├→ Search Documents (hybrid search)
    ├→ Select Model (question classification)
    └→ Generate Response (streaming)
        ↓
    Response + Sources
```

### Enhanced Flow (With Decomposition & Routing)
```
User Query
    ↓
Question Decomposer
    ├→ Classify Complexity (simple/moderate/complex)
    ├→ Decompose into Sub-Requests
    └→ Check Redis Cache (short-term memory)
        ↓
    [For each sub-request:]
        ├→ Model Selection (size-based routing)
        ├→ Context Retrieval (RAG)
        ├→ Generation (streaming)
        └→ Cache Result in Redis (TTL: 1 hour)
            ↓
        Sub-Request Response
        ↓
    Aggregate & Synthesize
        ↓
    Final Response + Sources
```

## Architecture Components

### 1. Question Decomposer

**Purpose**: Analyze user query and break it into logical sub-requests

**Location**: `reranker/question_decomposer.py`

**Key Methods**:
- `decompose_question(query: str) -> List[SubRequest]`
  - Analyzes query for multiple questions/topics
  - Returns structured sub-requests
  
- `classify_complexity(query: str) -> ComplexityLevel` → `SIMPLE | MODERATE | COMPLEX`
  - Token count analysis
  - Keyword pattern matching ("compare", "analyze", "explain vs", etc.)
  - Question count detection
  - Topic breadth analysis

- `select_model_for_complexity(complexity: ComplexityLevel) -> str`
  - SIMPLE → `llama3.2:3b` (fast, low resource)
  - MODERATE → `mistral:7b` (balanced)
  - COMPLEX → `codellama:7b` or `llama3.2:70b` (deep reasoning)

- `generate_cache_key(query: str, user_id: int) -> str`
  - Deterministic key: `tsa:chat:decomposed:{hash(normalized_query)}:{user_id}`
  - TTL: 1 hour (user session level)

### 2. Sub-Request Model

```python
class SubRequest(BaseModel):
    id: str                      # UUID for tracking
    original_query: str          # Full user query
    sub_query: str              # Isolated sub-question
    complexity: ComplexityLevel  # Classification
    required_context: List[str]  # Context hints
    
class SubResponse(BaseModel):
    sub_request_id: str
    response: str
    sources: List[Citation]
    model_used: str
    generation_time_ms: int
    confidence: float
```

### 3. Redis Short-Term Memory

**Schema**:
```
# Decomposed request cache (expires in 1 hour)
tsa:chat:decomposed:{query_hash}:{user_id} → JSON(decomposition metadata)

# Sub-request results (expires in 1 hour)
tsa:chat:subresp:{sub_request_id} → JSON(SubResponse)

# Query complexity classification cache (expires in 24 hours)
tsa:chat:complexity:{query_hash} → ComplexityLevel

# Metrics tracking
tsa:chat:decomposition_count → Counter
tsa:chat:sub_requests_total → Counter
tsa:chat:cache_hits_decomp → Counter
```

**TTL Strategy**:
- Sub-request results: 3600 seconds (1 hour)
- Decomposition metadata: 3600 seconds (1 hour) 
- Complexity classification: 86400 seconds (24 hours)
- Reasoning: Short-term memory reflects current session/context, not long-term knowledge

### 4. Model Routing Strategy

| Complexity | Model | Reason | Resources |
|------------|-------|--------|-----------|
| SIMPLE | `llama3.2:3b` | Fast response, low latency, sufficient for factual queries | 3B params, <4s/query |
| MODERATE | `mistral:7b` | Balanced reasoning, ~5-10s per query | 7B params, <8s/query |
| COMPLEX | `codellama:7b` or `llama3.2:70b` | Deep reasoning, multi-step logic, trade-offs | 7-70B params, <15s/query |

**Routing Logic**:
1. Extract complexity classification from decomposition
2. For each sub-request, use appropriate model from pool
3. Load balance across healthy instances (via existing intelligent router)
4. Cache results per model for reuse

### 5. Complexity Classification Algorithm

**Input Signals**:
1. **Token Count**
   - Simple: < 15 tokens
   - Moderate: 15-50 tokens
   - Complex: > 50 tokens

2. **Keyword Patterns**
   ```
   SIMPLE_KEYWORDS: ["what is", "how do", "explain", "tell me about"]
   MODERATE_KEYWORDS: ["compare", "analyze", "summarize", "discuss"]
   COMPLEX_KEYWORDS: ["evaluate", "design", "implement", "troubleshoot", "why"]
   ```

3. **Structure**
   - Question count (multiple = complex)
   - Conditional clauses ("if", "when", "given")
   - Logical operators ("and", "or", "not")

4. **Context Requirements**
   - Entity count (people, systems, metrics)
   - Code snippet presence
   - Table/chart reference

### 6. Integration Points

#### Chat Endpoint Flow (`/api/chat`)
```python
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest, authorization: Optional[str] = Header(None)):
    """Streaming chat with question decomposition and model routing."""
    
    # 1. Decompose question
    decomposer = QuestionDecomposer()
    decomposition = await decomposer.analyze(request.message, user.id)
    
    # 2. Check Redis cache
    cached_response = await redis_cache.get_decomposed_response(
        decomposition.query_hash, user.id
    )
    if cached_response:
        yield cached_response  # Return from cache
        return
    
    # 3. Process each sub-request
    sub_responses = []
    for sub_req in decomposition.sub_requests:
        model = decomposer.select_model_for_complexity(sub_req.complexity)
        
        # Retrieve context for this sub-request
        context = await rag_service.retrieve(sub_req.sub_query)
        
        # Generate response with selected model
        response = await rag_service.generate(
            sub_req.sub_query,
            context,
            model=model,
            temperature=_temp_for_complexity(sub_req.complexity)
        )
        
        # Cache sub-response
        sub_resp = SubResponse(...)
        await redis_cache.cache_sub_request(sub_resp, ttl=3600)
        sub_responses.append(sub_resp)
    
    # 4. Synthesize final response
    final_response = await synthesize_responses(
        original_query=request.message,
        sub_responses=sub_responses
    )
    
    # 5. Cache final response
    await redis_cache.cache_decomposed_response(
        decomposition.query_hash,
        user.id,
        final_response,
        ttl=3600
    )
    
    # 6. Stream response
    async for chunk in _token_stream_chunks(final_response):
        yield f"data: {json.dumps({'type': 'token', 'token': chunk})}\n\n"
```

## Benefits

### Performance
- **Sub-request parallelization**: Process 3-5 sub-requests concurrently
- **Model efficiency**: Route simple queries to 3B models (~2s vs 8s for 7B)
- **Cache hit rate**: ~40-60% for follow-up questions in same session
- **Response time**: 20-30% faster for decomposable queries

### Quality
- **Focused retrieval**: Context retrieval per sub-topic improves relevance
- **Appropriate reasoning depth**: Small models for simple questions prevent over-thinking
- **Better citations**: Per-sub-request sources are more granular and useful

### Scalability
- **Resource efficiency**: Small models handle 60-70% of queries, freeing large models
- **Throughput**: Higher concurrent query capacity with smaller model usage
- **Cost**: Reduced compute footprint via optimal model selection

## Example Flows

### Example 1: Simple Query (No Decomposition)
```
User: "What is FlexNet technology?"

Decomposition:
  - Complexity: SIMPLE
  - Sub-requests: 1 (no decomposition needed)
  
Model Routing:
  - Model: llama3.2:3b
  - Rationale: Factual, single-topic query
  
Cache:
  - Cache key: tsa:chat:decomposed:abc123:user_42
  - Result: Cached for 1 hour
  
Response Time: ~2-3 seconds
```

### Example 2: Moderate Query (Two-Part)
```
User: "Compare Sensus FlexNet and LTE communication methods. What are the tradeoffs?"

Decomposition:
  - Complexity: MODERATE
  - Sub-requests:
    1. "What is Sensus FlexNet communication?" (SIMPLE)
    2. "What is LTE communication?" (SIMPLE)
    3. "Compare FlexNet vs LTE tradeoffs" (MODERATE)

Model Routing:
  - Sub-request 1: llama3.2:3b (3 seconds)
  - Sub-request 2: llama3.2:3b (3 seconds)
  - Sub-request 3: mistral:7b (6 seconds)
  - Synthesis: mistral:7b (4 seconds)

Parallelization:
  - Sub-requests 1-2 can run concurrently: 3 seconds
  - Sub-request 3: 6 seconds
  - Synthesis: 4 seconds
  - Total: ~13 seconds (vs 18-20 without decomposition)

Cache:
  - Each sub-response cached independently
  - Follow-up "What about latency differences?" reuses cached responses
```

### Example 3: Complex Query (Multi-Topic)
```
User: "Design a monitoring strategy for AMI meter rollout across 50,000 endpoints, including 
       error detection, performance thresholds, and escalation procedures."

Decomposition:
  - Complexity: COMPLEX
  - Sub-requests:
    1. "What should be monitored for AMI meter rollout?" (MODERATE)
    2. "How to detect errors in AMI deployment?" (MODERATE)
    3. "What are good performance thresholds?" (COMPLEX)
    4. "Design escalation procedures for issues" (COMPLEX)

Model Routing:
  - Sub-requests 1-2: mistral:7b (6-7s each)
  - Sub-requests 3-4: llama3.2:70b (12-15s each, deep reasoning)
  - Synthesis: llama3.2:70b (5s)

Parallelization:
  - Sub-requests 1-2: 7 seconds (concurrent)
  - Sub-requests 3-4: 15 seconds (concurrent)
  - Synthesis: 5 seconds
  - Total: ~27 seconds

Cache Benefits:
  - "Tell me more about the error detection strategy" → uses cached sub-request 2
  - "What if we change threshold to X?" → minimal recomputation needed
```

## Configuration & Tuning

### Environment Variables
```bash
# Question Decomposer
ENABLE_QUESTION_DECOMPOSITION=true          # Toggle feature
DECOMPOSITION_MIN_TOKENS=15                 # Min tokens to consider decomposition
DECOMPOSITION_MAX_SUB_REQUESTS=5            # Max sub-requests per query
DECOMPOSITION_CACHE_TTL_SECONDS=3600        # Cache lifetime (1 hour)

# Model Routing
SIMPLE_MODEL=llama3.2:3b                    # Small model
MODERATE_MODEL=mistral:7b                   # Medium model
COMPLEX_MODEL=llama3.2:70b                  # Large model (optional)

# Performance
DECOMPOSITION_PARALLEL_REQUESTS=3           # Concurrent sub-requests
DECOMPOSITION_SYNTHESIS_TIMEOUT=10          # Synthesis timeout (seconds)
```

### Tuning Thresholds
- Adjust `DECOMPOSITION_MIN_TOKENS` based on observed query distribution
- Monitor cache hit rates: target 40-60% for typical workloads
- Profile model selection: ensure small models handle 60-70% of queries
- Adjust `DECOMPOSITION_PARALLEL_REQUESTS` based on resource availability

## Testing Strategy

### Unit Tests
- `test_decomposition_simple_queries()`: Verify single-question queries not decomposed
- `test_decomposition_multi_part()`: Verify multi-question decomposition
- `test_complexity_classification()`: Verify SIMPLE/MODERATE/COMPLEX routing
- `test_model_selection_consistency()`: Ensure deterministic model selection
- `test_cache_key_determinism()`: Same query → same cache key

### Integration Tests
- `test_decomposed_chat_with_cache()`: Full chat flow with caching
- `test_cache_hit_on_follow_up()`: Verify follow-up questions use cache
- `test_parallel_sub_request_processing()`: Verify concurrent execution
- `test_model_switching_behavior()`: Ensure model selection works across instances

### Load Tests
- Profile response times: simple vs. moderate vs. complex queries
- Measure cache hit rate and throughput improvement
- Monitor resource usage: GPU, memory, CPU during decomposition

## Monitoring & Metrics

### Prometheus Metrics
```
tsa_chat_decomposition_total{complexity}          # Total decompositions by type
tsa_chat_sub_requests_total{complexity}           # Total sub-requests processed
tsa_chat_decomposition_cache_hits{complexity}     # Cache hit count
tsa_chat_model_routing_total{model,complexity}    # Model usage by complexity
tsa_chat_decomposition_time_ms{complexity}        # Decomposition latency
tsa_chat_sub_response_time_ms{model,complexity}   # Sub-request response time
tsa_chat_synthesis_time_ms{}                      # Response synthesis time
```

### Dashboards
- **Decomposition Breakdown**: % SIMPLE / MODERATE / COMPLEX queries
- **Model Utilization**: % of queries using 3B / 7B / 70B models
- **Cache Efficiency**: Hit rate, misses, TTL expirations
- **Performance**: Latency comparison (decomposed vs. baseline)
- **Quality**: Citation count, confidence scores per complexity level

## Future Enhancements

1. **Adaptive Decomposition**: Learn optimal decomposition patterns from user feedback
2. **Cross-Request Caching**: Share results across users for common sub-queries
3. **Streaming Synthesis**: Stream sub-request results as they complete (not wait for all)
4. **Dynamic Model Allocation**: Adjust SIMPLE/MODERATE/COMPLEX model assignments based on load
5. **Feedback Loop**: Track decomposition quality and refine thresholds over time
6. **Multi-Language Support**: Detect query language and route to language-specific models

## Rollout Plan

### Phase 1 (Week 1): Core Infrastructure
- [ ] Implement `question_decomposer.py` with basic decomposition
- [ ] Extend `redis_cache.py` with decomposition caching
- [ ] Add unit tests

### Phase 2 (Week 2): Chat Integration
- [ ] Integrate decomposer into `/api/chat` endpoint
- [ ] Implement model routing
- [ ] Add integration tests

### Phase 3 (Week 3): Optimization
- [ ] Profile and tune decomposition thresholds
- [ ] Measure cache hit rates and latency improvements
- [ ] Refine model selection heuristics

### Phase 4 (Week 4): Production
- [ ] Rollout with feature flag (ENABLE_QUESTION_DECOMPOSITION)
- [ ] Monitor metrics and alerts
- [ ] Gather user feedback for Phase 2 enhancements

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-11  
**Owner**: AI Infrastructure Team
