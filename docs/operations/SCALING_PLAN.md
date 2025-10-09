# Technical Service Assistant Scaling Plan (Deferred Execution)

> Status: REFERENCE ONLY – Execute after core stability & feature baseline are fully validated.
>
> Hardware Basis Provided: **1 TB RAM**, **Dual Xeon (96 cores)** CPU-only environment.

---
## 1. Objectives
- Support higher concurrency without latency spikes.
- Enable specialized model routing (code, reasoning, fast chat, embeddings, safety).
- Preserve resource efficiency (avoid wasteful duplicate heavy model loads).
- Provide observability and adaptive routing signals.
- Allow safe experimentation (canary models) without destabilizing production paths.

---
## 2. Current Baseline (Snapshot)
- 4 Ollama containers (general models + embeddings)
- Reranker (BGE base)
- PostgreSQL (pgvector) + Redis + Next.js (rag-app) + PDF processor
- Intelligent routing (question classification) – improvement potential: queue-aware, capability-aware.

---
## 3. Capacity Envelope (Strategic)
Approximate quantized model footprints (q4_K_M style, CPU RAM):
| Model Class | Size (GB) | Notes |
|-------------|-----------|-------|
| 3B–4B       | 2.5–3.5   | Fast, good for classification/utilities |
| 7B–8B       | 5–7       | Core general assistants |
| 12–14B      | 10–12     | Mid reasoning boost |
| 33–34B      | 24–28     | Deep reasoning / synthesis |
| 70B         | 48–60     | Heavy, only if uplift measurable |

With ~930 GiB usable, even a diverse portfolio (8 medium + 2 large + 1 heavy) < 250 GiB resident + overhead. RAM is not the limiting factor; CPU scheduling & latency coherence are.

---
## 4. Target Tiered Architecture
| Tier | Purpose | Containers | Examples |
|------|---------|-----------|----------|
| A | Core fast general chat | 3–4 | mistral-7b, llama3-8b variants |
| A | Embeddings dedicated | 1 | nomic-embed-text / bge-large embed |
| B | Code-specialized | 1 | codellama / deepseek-coder |
| B | Reasoning (mid/large) | 1–2 | 34B model(s) |
| C | Safety / guard | 1 | small classification model |
| C | Canary / experimental | 1–2 | new fine-tunes / alt families |

Projected total: **9–11 Ollama containers** (expand to 12–14 if justified by utilization data).

---
## 5. Phased Execution Plan
### Phase 0 – Prerequisites
- Ensure existing RAG, reranker, hybrid search, ingestion stable.
- Add minimal load & latency logging around current generation calls.

### Phase 1 – Specialization Foundations
- Add embedding-only container (remove embedding contention from general chat).
- Add code model container; augment routing classifier with `code` capability mapping.
- Expose `/api/routing-metrics` returning: instance_id, avg_latency_ms, active_sessions, capability tags.

### Phase 2 – Reasoning Expansion
- Add a 34B reasoning container behind a `complexity_score` threshold.
- Extend `/api/intelligent-route` to include reasoning trigger (e.g., multi-step, analytical verbs, comparison patterns).
- Add fallback chaining: general → reasoning only if initial confidence < X & complexity high.

### Phase 3 – Observability & Control
- Prometheus metrics:
  - `tsa_tokens_generated_total{model=,instance=}`
  - `tsa_generation_latency_seconds_bucket{model=}` (histogram)
  - `tsa_routing_decisions_total{reason=,selected_capability=}`
  - `tsa_instance_queue_depth{instance=}` (gauge)
- Structured routing logs (JSON lines) with candidate set & scores.
- Dashboard panel (Grafana) – latency heatmap, token throughput, rejection/fallback count.

### Phase 4 – Adaptive & Safety
- Implement dynamic model scoring: EWMA-based latency + quality feedback weighting.
- Integrate safety/guard model pre-filter for user input classification (e.g., policy risk tags).
- Add negative routing: exclude high-latency instances automatically when p95 > threshold.

### Phase 5 – Canary & A/B
- Introduce traffic slicing: e.g., 5% of `technical` queries go to experimental model.
- Store response diffs + user feedback correlation.
- Automatic regression flag if canary helpful_rate < baseline - delta.

### Phase 6 – Heavy Model Evaluation (Optional)
- Temporarily load 70B model for a controlled test window.
- Run internal eval harness (existing A/B scripts) – require >=8–10% improvement in complex category queries to justify persistent load.
- If adopted: isolate into its own CPU set (cgroup cpuset) to avoid starving smaller models.

---
## 6. Routing Algorithm Upgrade (Conceptual)
Score(instance) = W_latency * (1 / p95_latency) + W_queue * (1 / (1 + queue_depth)) + W_fit * capability_match + W_health * uptime_factor + W_feedback * quality_score

Capability matching:
- Instances declare: `[general, code, reasoning, fast, embedding]`
- Query classifier emits required + optional tags.
- Hard exclusion if required ⊄ instance_tags.

Fallback chain example:
1. General 7B
2. Alternate general if overloaded
3. Reasoning 34B if complexity high & confidence low
4. Web augment (already integrated) if RAG coverage low

---
## 7. Model Lifecycle & Hotset Management
- Redis set: `model:hotset`
- Warmer process pings `generate` with 1-token prompt every N minutes.
- Eviction policy: if `last_access > 6h` and not pinned & memory_pressure=HIGH → unload via Ollama API.
- Memory watchdog: alert if free_memory_pct < 20%.

---
## 8. Guardrails & Resource Policies
- Per-container memory reservation & (optional) limit.
- CPU affinity / cpuset for large reasoning model.
- Backpressure: return HTTP 429 if global active_generations > threshold.
- Circuit breaker: auto-remove instance from routing pool after N consecutive failures.

---
## 9. Metrics to Track Before / After Each Phase
| Metric | Baseline | Target Improvement |
|--------|----------|--------------------|
| p95 generation latency | Measure | -15–25% under load |
| Queue wait time | Measure | Near-zero for p90 |
| Helpful rate (user feedback) | Measure | +5% by Phase 3 |
| Fallback to reasoning % | Measure | < 15% steady-state |
| Canary regression incidents | 0 | Detect & auto-disable in <5m |

---
## 10. Risk Mitigation
| Risk | Mitigation |
|------|------------|
| Model explosion & complexity | Enforce capability registry & phase gates |
| Latency regression from large model | Conditional routing; fallback on timeout |
| Memory fragmentation | Scheduled restart window for heavy instances |
| Unused canary cost | Auto-unload if traffic < threshold |
| User confusion from variable answer style | Apply style normalizer prompt wrapper |

---
## 11. Tooling & Implementation Artifacts (Planned)
Planned new files/endpoints (not yet created):
- `routing/capabilities.py` (declarative instance capability map)
- `routing/scorer.py` (composite scoring formula)
- `metrics/routing_metrics.py`
- API: `/api/routing-metrics`, `/api/capacity-status`
- Script: `bin/load_test_routing.py`

---
## 12. Execution Guard (When NOT to Start)
Defer scaling phases if any of:
- RAG accuracy < agreed baseline
- Ingestion backlog > 2 cycles
- Reranker latency unstable (p95 > 1.5s)
- DB bloat / vacuum issues unresolved

---
## 13. Acceptance Criteria per Phase
Phase 1 done when: embedding lane active, code lane routable, metrics endpoint returns JSON with latencies.
Phase 2 done when: reasoning model only used on complexity score > threshold AND logs show fallback trigger conditions.
Phase 3 done when: Grafana board live + tokens/sec & routing decision counts visible.
Phase 4 done when: adaptive scoring changes routing distribution measurably (>=10% shift under synthetic load).
Phase 5 done when: canary traffic slice adjustable via config + diff reports stored.
Phase 6 done when: heavy model trial report produced with eval deltas.

---
## 14. Summary
You have sufficient hardware to move from a homogeneous pool to a capability-oriented inference fabric. This plan staggers complexity introduction, enforces measurement at each stage, and keeps large-model cost conditional. Execute only after base system maturity is confirmed.

---
## 15. Quick Start Checklist (When Ready)
1. Collect baseline latency & feedback metrics
2. Implement capability registry + extend classifier output
3. Add embedding-only container & code model
4. Add routing metrics + adaptive scoring skeleton
5. Introduce reasoning model and conditional escalation
6. Add canary channel & A/B logging
7. Evaluate heavy model ROI

---
Prepared for deferred execution. Modify as architecture evolves.
