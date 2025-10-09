# Reranker Service

FastAPI microservice providing:
1. Passage reranking given a query (cross-encoder style) using FlagEmbedding models.
2. Combined retrieval + chat endpoint (experimental convenience) that performs: embed query -> similarity search -> rerank -> context assembly -> LLM answer.

## Endpoints
### POST /rerank
Request:
```json
{
  "query": "what is the warranty?",
  "passages": ["The warranty period is 12 months.", "Unrelated."],
  "top_k": 5
}
```
Response:
```json
{
  "reranked": ["The warranty period is 12 months."],
  "scores": [0.81234]
}
```
Notes:
- `top_k` defaults to `RERANK_TOP_K` from env if omitted.
- Authorization: add header `X-API-Key: <API_KEY>` if `API_KEY` is set.

### POST /chat (experimental)
High-level retrieval + answer wrapper.
Request:
```json
{ "message": "Summarize the warranty terms" }
```
Response:
```json
{ "reply": "The warranty lasts 12 months covering ..." }
```
Pipeline steps:
1. Query embedding generated (Ollama embeddings endpoint)
2. Vector similarity search on `document_chunks`
3. Rerank top candidates (`RERANK_TOP_K`)
4. Construct context prompt
5. Call Ollama chat model (`CHAT_MODEL`)

### GET /health
Lightweight status.
### GET /health/details
Extended checks (DB, model load) – requires API key if set.

## Environment Variables (via shared `config.py`)
| Var | Description |
|-----|-------------|
| RERANK_MODEL | FlagEmbedding model id (e.g., `BAAI/bge-reranker-base`) |
| EMBEDDING_MODEL | Embedding model for query vectorization |
| CHAT_MODEL | Generation model for chat endpoint |
| DB_HOST/DB_* | Database connectivity |
| RERANK_TOP_K | Reranked passage limit |
| RETRIEVAL_CANDIDATES | Initial vector similarity candidate pool |
| API_KEY | Optional auth token required in `X-API-Key` header |

## Local Development
```bash
pip install -r reranker/requirements.txt
python reranker/app.py  # or uvicorn reranker.app:app --reload
```
Curl example:
```bash
curl -X POST http://localhost:8008/rerank \
  -H 'Content-Type: application/json' \
  -d '{"query":"test","passages":["a","b"]}'
```

## Future Improvements
- Streaming answer support.
- Rerank quality metrics integration with `scripts/eval_suite.py`.
- Batch rerank endpoint.
- Multi-model ensemble experimentation.

---
Update this file if the API surface or pipeline changes.
