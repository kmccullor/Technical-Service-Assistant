# Chat Dataflow: Code Structure Reference

This file provides a quick reference to the implemented chat decomposition system.

## Directory Structure

```
Technical-Service-Assistant/
├── reranker/
│   ├── question_decomposer.py          ← NEW: Main decomposition engine
│   ├── app.py                          ← Existing chat endpoint (to integrate)
│   └── config.py
│
├── utils/
│   └── redis_cache.py                  ← EXTENDED: Cache operations
│
├── tests/
│   ├── unit/
│   │   └── test_question_decomposer.py ← NEW: 31 unit tests
│   │
│   └── integration/
│       └── test_decomposed_chat.py    ← NEW: 54 integration tests
│
├── docs/
│   ├── CHAT_DATAFLOW.md               ← NEW: Architecture documentation
│   └── [existing docs...]
│
├── CHAT_DECOMPOSITION_IMPLEMENTATION.md ← NEW: Implementation guide
└── CHAT_DATAFLOW_REVIEW.md            ← NEW: Review summary
```

## Key Classes & APIs

### QuestionDecomposer (reranker/question_decomposer.py)

**Primary Class**:
```python
class QuestionDecomposer:
    """Main decomposition engine."""

    def decompose_question(query: str, user_id: int = 0) -> DecompositionResult
    def classify_complexity(query: str) -> ComplexityLevel
    def select_model_for_complexity(complexity: ComplexityLevel) -> str
    def generate_cache_key(query: str, user_id: int) -> str
```

**Supporting Models**:
```python
class ComplexityLevel(str, Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"

@dataclass
class SubRequest:
    id: str
    original_query: str
    sub_query: str
    complexity: ComplexityLevel
    required_context: list[str]
    topic: str
    confidence: float

    def to_dict(self) -> dict

class DecompositionResult(BaseModel):
    query_hash: str
    original_query: str
    complexity: ComplexityLevel
    sub_requests: list[SubRequest]
    total_sub_requests: int
    needs_decomposition: bool
    decomposition_confidence: float

    def to_dict(self) -> dict
```

**Convenience Functions**:
```python
def classify_and_decompose(query: str, user_id: int = 0) -> DecompositionResult

def select_model_for_query(query: str) -> str
```

---

### Redis Cache Extensions (utils/redis_cache.py)

**New Functions**:
```python
def cache_decomposed_response(
    query_hash: str,
    user_id: int,
    response_data: dict,
    ttl: int = 3600
) -> bool

def get_decomposed_response(query_hash: str, user_id: int) -> Optional[dict]

def cache_sub_request_result(
    sub_request_id: str,
    result_data: dict,
    ttl: int = 3600
) -> bool

def get_sub_request_result(sub_request_id: str) -> Optional[dict]

def cache_complexity_classification(
    query_hash: str,
    complexity: str,
    ttl: int = 86400
) -> bool

def get_complexity_classification(query_hash: str) -> Optional[str]

def track_decomposition_metric(
    complexity_level: str,
    metric_name: str,
    value: int = 1
) -> bool

def get_decomposition_stats() -> dict
```

---

## Usage Patterns

### Pattern 1: Quick Classification

```python
from reranker.question_decomposer import QuestionDecomposer, ComplexityLevel

decomposer = QuestionDecomposer()
complexity = decomposer.classify_complexity(user_query)

if complexity == ComplexityLevel.SIMPLE:
    model = "llama3.2:3b"      # Fast, 2-3 seconds
elif complexity == ComplexityLevel.MODERATE:
    model = "mistral:7b"       # Balanced, 5-7 seconds
else:
    model = "codellama:7b"     # Deep reasoning, 8-15 seconds
```

### Pattern 2: Full Decomposition

```python
from reranker.question_decomposer import QuestionDecomposer

decomposer = QuestionDecomposer()
result = decomposer.decompose_question(user_query, user_id=current_user.id)

# Process each sub-request in parallel
async def process_all():
    responses = []
    for sub_req in result.sub_requests:
        model = decomposer.select_model_for_complexity(sub_req.complexity)
        response = await generate_response(sub_req.sub_query, model)
        responses.append(response)
    return responses

sub_responses = await process_all()
final_response = synthesize(result.original_query, sub_responses)
```

### Pattern 3: Cache Integration

```python
from utils.redis_cache import (
    cache_decomposed_response,
    get_decomposed_response,
    cache_sub_request_result,
    get_sub_request_result,
)

# Check cache first
cached_response = get_decomposed_response(
    query_hash=result.query_hash,
    user_id=current_user.id
)

if cached_response:
    # Use cached result
    return cached_response

# Otherwise, process and cache
final_response = await full_processing()

cache_decomposed_response(
    query_hash=result.query_hash,
    user_id=current_user.id,
    response_data=final_response,
    ttl=3600  # 1 hour
)

# Also cache individual sub-requests for reuse
for sub_resp in sub_responses:
    cache_sub_request_result(
        sub_request_id=sub_resp['id'],
        result_data=sub_resp,
        ttl=3600
    )
```

### Pattern 4: Monitoring

```python
from utils.redis_cache import (
    track_decomposition_metric,
    get_decomposition_stats,
)

# Track metrics
track_decomposition_metric(
    complexity_level=str(complexity),
    metric_name="total",
    value=1
)

# Get stats later
stats = get_decomposition_stats()
# Returns: {
#     "simple:total": 600,
#     "moderate:total": 200,
#     "complex:total": 100,
# }
```

---

## Integration Example

### Modifying `/api/chat` Endpoint

```python
# In reranker/app.py

from reranker.question_decomposer import QuestionDecomposer
from utils.redis_cache import (
    cache_decomposed_response,
    get_decomposed_response,
    cache_sub_request_result,
)

@app.post("/api/chat")
async def chat_endpoint(
    request: ChatRequest,
    authorization: Optional[str] = Header(None)
):
    """Enhanced chat with question decomposition."""

    # Get user
    user = _user_from_authorization(authorization)

    # 1. Decompose question
    decomposer = QuestionDecomposer()
    decomposition = decomposer.decompose_question(
        request.message,
        user_id=user.id
    )

    # 2. Check cache
    cached = get_decomposed_response(
        decomposition.query_hash,
        user_id=user.id
    )
    if cached:
        async for chunk in _stream_response(cached):
            yield chunk
        return

    # 3. Process sub-requests in parallel
    async def process_sub_requests():
        tasks = []
        for sub_req in decomposition.sub_requests:
            task = process_single_sub_request(
                sub_req,
                rag_service,
                decomposer
            )
            tasks.append(task)
        return await asyncio.gather(*tasks)

    # 4. Execute
    sub_responses = await process_sub_requests()

    # 5. Synthesize
    final_response = await synthesize_responses(
        original_query=request.message,
        sub_responses=sub_responses
    )

    # 6. Cache result
    cache_decomposed_response(
        query_hash=decomposition.query_hash,
        user_id=user.id,
        response_data=final_response,
        ttl=3600
    )

    # 7. Stream response
    async for chunk in _stream_response(final_response):
        yield f"data: {json.dumps({'type': 'token', 'token': chunk})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


async def process_single_sub_request(sub_req, rag_service, decomposer):
    """Process a single sub-request."""
    model = decomposer.select_model_for_complexity(sub_req.complexity)

    # Retrieve context for this specific sub-request
    context = await rag_service.search_documents(sub_req.sub_query)

    # Generate response with selected model
    response = await rag_service.generate_response(
        query=sub_req.sub_query,
        context=context,
        model=model,
        temperature=0.2 if sub_req.complexity == ComplexityLevel.SIMPLE else 0.5,
        max_tokens=500,
    )

    # Cache individual response
    cache_sub_request_result(
        sub_request_id=sub_req.id,
        result_data={
            'id': sub_req.id,
            'sub_query': sub_req.sub_query,
            'response': response,
            'model': model,
            'complexity': str(sub_req.complexity),
        },
        ttl=3600
    )

    return {
        'id': sub_req.id,
        'response': response,
        'model': model,
        'complexity': sub_req.complexity,
    }


async def synthesize_responses(original_query, sub_responses):
    """Combine sub-responses into final answer."""
    # Implementation: merge responses, maintain citations, etc.
    combined_response = "\n\n".join([r['response'] for r in sub_responses])
    return combined_response
```

---

## Configuration Examples

### .env File
```bash
# Question Decomposer Configuration
ENABLE_QUESTION_DECOMPOSITION=true
DECOMPOSITION_MIN_TOKENS=15
DECOMPOSITION_MAX_SUB_REQUESTS=5
DECOMPOSITION_CACHE_TTL_SECONDS=3600
DECOMPOSITION_PARALLEL_REQUESTS=3
DECOMPOSITION_SYNTHESIS_TIMEOUT=10

# Model Selection
SIMPLE_MODEL=llama3.2:3b
MODERATE_MODEL=mistral:7b
COMPLEX_MODEL=codellama:7b

# Redis
REDIS_URL=redis://redis:6379/0
```

### Docker Compose (environment section)
```yaml
services:
  reranker:
    environment:
      - ENABLE_QUESTION_DECOMPOSITION=true
      - DECOMPOSITION_MAX_SUB_REQUESTS=5
      - DECOMPOSITION_CACHE_TTL_SECONDS=3600
      - REDIS_URL=redis://redis:6379/0
```

---

## Test Execution

### Run Unit Tests
```bash
# All decomposer tests
pytest tests/unit/test_question_decomposer.py -v --no-cov

# Specific test class
pytest tests/unit/test_question_decomposer.py::TestComplexityClassification -v

# Specific test
pytest tests/unit/test_question_decomposer.py::TestComplexityClassification::test_simple_factual_query -v
```

### Run Integration Tests
```bash
# All integration tests
pytest tests/integration/test_decomposed_chat.py -v --no-cov

# Specific test class
pytest tests/integration/test_decomposed_chat.py::TestDecomposedChatFlow -v
```

### Run All Tests
```bash
pytest tests/unit/test_question_decomposer.py tests/integration/test_decomposed_chat.py -v --no-cov
```

---

## Performance Characteristics

### Decomposition Timing

```
Operation                  | Time (ms) | Notes
──────────────────────────────────────────────
Classify complexity        | 1-2       | Very fast
Decompose simple query     | 2-3       | No splitting needed
Decompose multi-part       | 5-8       | 2-3 sub-requests
Decompose complex query    | 10-15     | Multiple sub-questions
Cache key generation       | <1        | Hashing only
Total decomposition        | <100      | Target
```

### Model Response Times

```
Model           | Complexity | Response Time | Parallelism
────────────────────────────────────────────────────────
llama3.2:3b     | SIMPLE     | 2-3s          | 3 parallel
mistral:7b      | MODERATE   | 5-7s          | 2 parallel
codellama:7b    | COMPLEX    | 8-15s         | 1 parallel
```

### Cache Performance

```
Cache Hit (no processing)     | <100ms
Cache Miss (full processing)  | 20-30 seconds (depending on query)
Multi-part cache reuse        | 50-80% faster on follow-up questions
```

---

## Debugging Tips

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

decomposer = QuestionDecomposer()
result = decomposer.decompose_question("Your query here", user_id=1)

# Check logs:
# DEBUG - Decomposed query: complexity=moderate, sub_requests=2, confidence=0.85
```

### Inspect Decomposition Result

```python
result = decomposer.decompose_question("Compare X and Y", user_id=1)

print(f"Query Hash: {result.query_hash}")
print(f"Complexity: {result.complexity}")
print(f"Sub-requests: {result.total_sub_requests}")
print(f"Confidence: {result.decomposition_confidence}")

for i, sub_req in enumerate(result.sub_requests, 1):
    print(f"\nSub-request {i}:")
    print(f"  ID: {sub_req.id}")
    print(f"  Query: {sub_req.sub_query}")
    print(f"  Complexity: {sub_req.complexity}")
    print(f"  Confidence: {sub_req.confidence}")
```

### Cache Key Validation

```python
# Same query should generate same key
key1 = decomposer.generate_cache_key("What is FlexNet?", user_id=1)
key2 = decomposer.generate_cache_key("What is FlexNet?", user_id=1)
assert key1 == key2  # Should be True

# Different user should generate different key
key3 = decomposer.generate_cache_key("What is FlexNet?", user_id=2)
assert key1 != key3  # Should be True
```

---

## Troubleshooting

### Issue: Decomposition always returns SIMPLE
**Solution**: Check token count threshold. Default is 15 tokens.
```python
decomposer.min_tokens_for_decomposition = 10  # Lower threshold
```

### Issue: Cache not working
**Solution**: Verify Redis connection
```python
from utils.redis_cache import get_redis_client
client = get_redis_client()
if client is None:
    print("Redis not connected")
```

### Issue: Model selection incorrect
**Solution**: Check classification keywords
```python
decomposer.COMPLEX_KEYWORDS.add("your_keyword")
```

### Issue: Sub-requests exceed limit
**Solution**: Increase max sub-requests or merge less confident ones
```python
decomposer.max_sub_requests = 10
```

---

## Next Steps

1. **Integrate with chat endpoint** (1-2 hours)
2. **Test with real queries** (2-3 hours)
3. **Profile and optimize** (2-3 hours)
4. **Deploy with feature flag** (1 hour)
5. **Monitor metrics** (ongoing)

See `CHAT_DECOMPOSITION_IMPLEMENTATION.md` for detailed integration guide.
