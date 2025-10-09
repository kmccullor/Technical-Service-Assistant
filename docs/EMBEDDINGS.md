# Embeddings & Evaluation

This document centralizes guidance on selecting, evaluating, and operating embedding models within the Technical Service Assistant.

## Default Model
- `nomic-embed-text:v1.5` (Ollama). Provides a general-purpose English embedding with balanced dimensionality & speed for CPU usage.

## Model Management
Multiple Ollama benchmark containers (ports 11434–11437) allow parallel experimentation without model eviction thrash. Use `distribute_models.py` / `migrate_models.py` to sync models.

## Adding a New Embedding Model
1. Pull model into one benchmark container:
   ```bash
   curl -X POST http://localhost:11435/api/pull -d '{"model": "<model-tag>"}'
   ```
2. Update env var `EMBEDDING_MODEL=<model-tag>` or pass dynamically in scripts.
3. Run benchmark script:
   ```bash
   python bin/analyze_embeddings.py --models <model-tag> nomic-embed-text:v1.5
   ```
4. Inspect output in `logs/` (HTML / JSON metrics) & decide adoption.

## Storage Considerations
- Use consistent model name stored with each chunk (column `model`) to support future re-embedding or hybrid search.
- Avoid mixing vectors from incompatible dimensionality inside one column.

## Re-Embedding Strategy
When switching models:
1. Create new column/table for fresh embeddings OR add `model` discriminator and run side-by-side.
2. Backfill asynchronously (queue or batch script).
3. Switch retrieval code to prefer latest model after verification.
4. Optionally prune old vectors once stable.

## Evaluation Dimensions
| Criterion | Why it matters | Implemented Metric |
|----------|----------------|--------------------|  
| Semantic fidelity | Topical closeness | Recall@K, nDCG |
| Early precision | Quality of top ranks | MRR |
| Speed | Ingestion / query throughput | Timing (embed/search/total) |
| Memory footprint | Storage growth | Vector count * dim (manual) |
| Robustness | Noisy OCR / tables | Manual review set |## Reranking Integration
- Primary retrieval: vector similarity (cosine distance).
- Secondary rerank: BGE reranker (cross-encoder style) to refine top candidates.
- Tune `RETRIEVAL_CANDIDATES` (wider = slower, potentially higher recall) and `RERANK_TOP_K` (narrower answer context) via evaluation harness.
- Evaluate rerank impact: `scripts/eval_suite.py --rerank-endpoint http://localhost:8008/rerank` compares vector-only vs reranked metrics and latency.

## Hybrid / Future Extensions
- Keyword BM25 blending (add textual index in Postgres).
- Table-aware embedding (structural tokens) & image caption embeddings.
- Per-document adaptive chunk size based on variance in sentence length.

## Benchmarks
See `embedding_model_test_results.md` for sample raw embedding outputs. For retrieval metrics use `scripts/eval_suite.py` (supports Recall@K, MRR, nDCG, timing metrics, optional rerank comparison). Run the sample with `make eval-sample`.

JSON output includes:
- `recall_at_k`, `mrr`, `ndcg`: quality metrics
- `avg_embedding_time`, `avg_search_time`, `avg_total_time`: performance timing (seconds)
- `rerank_metrics`: if `--rerank-endpoint` used, includes reranked quality metrics and `avg_rerank_time`

## Quality Checklist Before Adopting New Model
- [ ] Dimensionality verified & consistent
- [ ] Basic similarity sanity tests pass (obvious related pairs score higher)
- [ ] No major regressions vs baseline across chosen metrics
- [ ] Ingestion speed acceptable
- [ ] Query latency acceptable (P95 < target threshold)

## Open Questions / Research
- Optimal chunk overlap trade-off for this document domain
- Impact of sentence vs paragraph chunking on recall
- Benefits of multi-vector (ColBERT-style) representations

---
Contribute additional evaluation scripts or structured benchmark datasets to strengthen empirical selection.
