# Troubleshooting Guide

Common issues encountered while running or extending the AI PDF Vector Stack, with root causes and remediation steps.

## Table of Contents
1. Container & service issues
2. **Intelligent Routing Issues (NEW)**
3. Embedding / model issues
4. Extraction & chunking issues
5. Database issues
6. Reranking issues
7. Performance considerations
8. Logging & diagnostics

---
## 1. Container & Service Issues
| Symptom | Possible Cause | Resolution |
|---------|----------------|-----------|
| `pgvector` unhealthy | Init script failure, port conflict | Inspect `docker logs pgvector`; confirm port 5432 free; validate `init.sql` syntax |
| Ollama container exits repeatedly | CPU instructions unsupported / resource limits | Check host capabilities; reduce parallel containers; ensure virtualization supports AVX |
| `pdf_processor` stops processing | Unhandled exception during one PDF | Inspect container logs; add try/except around failing stage; move problematic PDF aside |
| Reranker 500 errors | Model not downloaded | Warm start by hitting endpoint once; ensure network if pulling from HF |
| Frontend stuck on "Connecting..." | Reranker exposed only `/health` (no `/api/health` alias) so `/api/health` 404 via nginx | Add alias endpoints `/api/health` & `/api/health/details` in `reranker/app.py` (thin wrappers returning existing health); rebuild: `docker compose build reranker && docker compose up -d reranker`; confirm `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8008/api/health` returns 200 |
| Frontend still stuck after alias added | Corrupted / stale `unified-chat.js` (partial overwrite left invalid trailing class code -> SyntaxError halts script before status update) | Fully replace `frontend/unified-chat.js` with clean minimal bootstrap (IIFE) and hard‑reload (Ctrl+Shift+R). Check browser console for SyntaxError lines referencing removed legacy methods. |
| Frontend shows Unauthorized / 401 in console | `API_KEY` set in backend but frontend not sending `X-API-Key` | Inject `<meta name="api-key" content="${API_KEY}">` at build or set `window.APP_API_KEY` before `app.js`; ensure wrapper adds header; refresh |
| Frontend hybrid search calls fail with 404 | Path mismatch (backend defines `/search` not `/api/search`) | Use `/api/hybrid-search` for hybrid mode and rely on nginx `/api/` proxy; ensure backend endpoints exist; add missing aliases if needed |
| Users cannot login (401 Unauthorized) | **RESOLVED**: Authentication using mock database instead of real PostgreSQL | ✅ **FIXED**: Updated `reranker/auth_endpoints.py` to query real database with bcrypt password verification |
| Document downloads fail with 404 | **RESOLVED**: URL pattern mismatch between frontend (`/api/documents/{id}/download`) and backend (`/api/documents/download/{id}`) | ✅ **FIXED**: Added alternative route `/api/documents/{document_id}/download` for frontend compatibility |
| Reranker container restarts repeatedly | **RESOLVED**: Import errors in `app.py` and `reranker_config.py` | ✅ **FIXED**: Commented out problematic imports causing module loading failures |

## 2. Docker RAG & Load Balancing Issues (RESOLVED)
| Symptom | Cause | Resolution |
|---------|-------|-----------|
| Low confidence scores (0.6% instead of 80%+) | **RESOLVED**: Reranking disabled in Docker container | ✅ **FIXED**: Set `RERANKER_ENABLED=true` and `CONFIDENCE_THRESHOLD=0.2` in docker-compose.yml |
| Database connection refused (ECONNREFUSED ::1:5432) | **RESOLVED**: `.env.local` used localhost instead of container names | ✅ **FIXED**: Updated `DATABASE_URL="postgresql://postgres:postgres@pgvector:5432/vector_db"` |
| Load balancer using single instance | **RESOLVED**: Hardcoded localhost URLs in load-balancer.ts | ✅ **FIXED**: Load balancer now reads `OLLAMA_INSTANCES` environment variable |
| `/api/intelligent-route` not found | Endpoints not registered | Check `curl http://localhost:8008/docs`; rebuild reranker container |
| Wrong model selected | Classification logic needs tuning | Review `classify_question()` keywords in `reranker/app.py` |
| Always routes to primary instance | Health check failing for other instances | Check `curl http://localhost:8008/api/ollama-health`; verify all 4 instances healthy |

### Docker RAG Diagnostics (VALIDATED WORKING – Service Renamed)
```bash
# Test Docker container load balancing (WORKING)
docker logs technical-service-assistant | grep "Selected instance"

# Test high confidence RAG (WORKING)
curl -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is load balancing?"}]}'

# Verify environment variables (WORKING)
docker exec technical-service-assistant env | grep -E "(DATABASE_URL|OLLAMA_INSTANCES|RERANKER_ENABLED)"

# Test database connectivity (WORKING)
docker exec technical-service-assistant nc -zv pgvector 5432
```

### Legacy Diagnostics
```bash
# Test intelligent routing endpoints
curl -X GET http://localhost:8008/api/ollama-health | jq .
curl -X POST http://localhost:8008/api/intelligent-route \
  -H "Content-Type: application/json" \
  -d '{"query": "Write Python code"}' | jq .

# Should show: selected_model="deepseek-coder:6.7b", question_type="code"

# Test load balancing
for i in {1..5}; do
  curl -s -X POST http://localhost:8008/api/intelligent-route \
    -H "Content-Type: application/json" \
    -d '{"query": "test"}' | jq -r .selected_instance
done
# Should show different instances: primary, secondary, tertiary, quaternary
```

## 3. Embedding / Model Issues
| Symptom | Cause | Resolution |
|---------|-------|-----------|
| Embedding array length inconsistent | Model changed mid-run | Lock model tag (`nomic-embed-text:v1.5`); **NEVER use `:latest` in production** |
| Empty embedding response | Wrong endpoint / body shape | `curl <host>:<port>/api/tags`; verify JSON keys `model`, `prompt` |
| Slow embedding generation | Oversized chunks | Lower chunk size or adjust overlap; profile average tokens |

## 3. Extraction & Chunking Issues
| Symptom | Cause | Resolution |
|---------|-------|-----------|
| Missing text in output | Scanned PDF w/out OCR | Integrate OCR layer (e.g., Tesseract) pre-extraction |
| Garbled characters | Encoding or malformed PDF | Try alternative parser; fall back to OCR |
| Tables not detected | Camelot flavor mismatch | Try `flavor='stream'` vs `lattice`; ensure Ghostscript installed |
| Overlapping or duplicated chunk content | Edge case in simple regex sentence splitter | Switch to NLTK punkt; pre-download resource in image |

## 4. Database Issues
| Symptom | Cause | Resolution |
|---------|-------|-----------|
| INSERT failures (embedding) | JSON quoting or vector cast mismatch | Standardize server-side parameterization; ensure embedding stored as correct type (extension) |
| Slow similarity search | Missing index | Create `ivfflat` or `hnsw` index on embedding column once stable |
| Bloat / large table | Unbounded ingestion | Implement retention or partitioning; archive stale documents |

## 5. Reranking Issues
| Symptom | Cause | Resolution |
|---------|-------|-----------|
| Poor rerank quality | Model not suited for domain | Evaluate alternative reranker (e.g., `bge-reranker-v2`) |
| Timeout | Large candidate set | Lower `RETRIEVAL_CANDIDATES`; paginate queries |

## 6. Performance Considerations
- Batch embeddings where supported (future optimization; currently single-chunk calls).
- Preload models at container start to avoid first-request latency.
- Use HNSW / IVFFlat indexes for large corpora (trade-off: build time vs query speed).
- Minimize chunk overlap for long documents to reduce vector count.

## 7. Logging & Diagnostics
- Application logs: `logs/` (embedding errors, stack traces with timestamp & model name).
- Container logs: `docker logs <name>`.
- Add `LOG_LEVEL=DEBUG` for verbose output.
- Consider structured JSON logs for ingestion events (future task).

## Escalation Checklist
1. Reproduce on minimal PDF.
2. Capture exact command & environment variables.
3. Gather logs (worker + model container + DB errors).
4. Note recent code or model changes.
5. Open an issue with reproduction steps & logs snippet.

---
Contributions to expand this guide are welcome. Keep entries concise and actionable.

---
### Frontend Connectivity Issues (Detailed Diagnostics)
If the UI badge remains on "Connecting..." or status dot stays red:

1. Quick Alias Check
  ```bash
  curl -i http://localhost:8008/api/health | head -n1   # Expect HTTP/1.1 200
  ```
  - If 404: backend missing alias → implement `/api/health` alias.

2. Verify Root Health Still Works
  ```bash
  curl -i http://localhost:8008/health | head -n1
  ```

3. Inspect Network Tab
  - Look for repeated `/api/health` 404 or 401.
  - 404 → alias missing; 401 → API key mismatch.

4. API Key Flow
  - Backend enforces only if `API_KEY` env var is set.
  - If enforcing: ensure frontend sends `X-API-Key` (check request headers in dev tools).
  - Interactive fallback: runtime prompt (implemented in `frontend/app.js`) will store key in `sessionStorage` and retry.

5. Confirm Hybrid Search Reachability
  ```bash
  curl -i -X POST http://localhost:8008/api/hybrid-search \
    -H 'Content-Type: application/json' \
    -d '{"query":"ping","confidence_threshold":0.3,"enable_web_search":false,"max_context_chunks":3}'
  ```
  - 200 + JSON → backend reachable.
  - 422 → validation error (payload shape) – adjust fields.
  - 500 → inspect `docker logs reranker`.

6. Rebuild & Restart (if code changes just applied)
  ```bash
  docker compose build reranker
  docker compose up -d reranker
  ```

7. Fallback Checklist
  - Clear browser cache (DevTools > Disable cache checked while reloading).
  - Hard reload (Ctrl+Shift+R).
  - Ensure no service is binding host port 3000 already (Next.js RAG app).

Outcome: Once `/api/health` returns 200 and the frontend's `diagnosticConnectivityTest()` logs status 200, status dot should turn green and queries proceed.

### JavaScript Global Error Banner (New)
The rebuilt `unified-chat.js` installs `window` handlers for `error` & `unhandledrejection`.

If a runtime exception occurs during initialization, a fixed red banner appears at the top: `⚠️ UI Error: <message>`.

Use this to rapidly identify remaining issues (e.g., missing endpoint, CORS/network failures surfaced as uncaught promise rejections). If no banner and status remains red, re-check network tab for failing `/api/health` or 401 responses.
