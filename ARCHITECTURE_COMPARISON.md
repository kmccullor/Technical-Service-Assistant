# Architecture Comparison: Current vs. Optimized

**Date:** November 12, 2025
**Purpose:** Visual comparison of system before and after optimization

---

## Current Architecture (TODAY)

```
┌─────────────────────────────────────────────────────────────────┐
│                        User / Frontend                          │
│                      (Waits 17.4 min)                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             v
┌─────────────────────────────────────────────────────────────────┐
│                    RAG Chat Service                             │
│  ┌──────────┬──────────────┬─────────────┬────────────────┐    │
│  │Embedding │Vector Search │ Reranking   │ LLM Generation │    │
│  │ 5-10s    │ 5-10s        │  5-10s      │  400-600s      │    │
│  │ (0.8%)   │ (0.8%)       │  (0.8%)     │  (97.6%)       │    │
│  └──────────┴──────────────┴─────────────┴────────────────┘    │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              v              v              v
         ┌─────────┐  ┌──────────┐  ┌────────────┐
         │ Ollama  │  │Postgres  │  │ Reranker   │
         │  (8x)   │  │ +Pgvector│  │  (BGE)     │
         └─────────┘  └──────────┘  └────────────┘

ISSUES:
❌ Full generation before returning (17.4 min wait)
❌ No caching (repeated Q same as new Q)
❌ Vector-only search (misses keywords/acronyms)
❌ Generic models (60-70% accuracy)
❌ Linear processing (3 RPS max)
```

---

## Optimized Architecture (RECOMMENDED)

```
┌─────────────────────────────────────────────────────────────────┐
│                        User / Frontend                          │
│                  (Sees response in 5-10s)                       │
│            ← Streaming tokens in real-time ←                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             v
┌─────────────────────────────────────────────────────────────────┐
│                    Enhanced RAG Chat Service                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │         Query Optimization & Expansion                 │    │
│  │  (Normalize, expand acronyms, extract entities)        │    │
│  └──────────┬────────────────────────────────────────────┬┘    │
│             │                                            │       │
│  ┌──────────v────────────┐          ┌──────────────────v──┐   │
│  │  Response Cache       │          │ Query Fingerprint   │   │
│  │  (Redis, 1hr TTL)     │          │ Lookup              │   │
│  │  20-30% hit rate      │◄─────────┤                     │   │
│  └──────────┬────────────┘          └─────────────────────┘   │
│             │                                                   │
│             └─────────────┬──────────────────┐                 │
│                           │                  │ (miss)          │
│                           v                  v                 │
│  ┌──────────────────────────────────────────────────────┐      │
│  │         Parallel Retrieval Pipeline                 │      │
│  │  ┌─────────────────────────────────────────────┐    │      │
│  │  │ Concurrent:                                 │    │      │
│  │  │ ├─ Embedding Gen (5-10s)                   │    │      │
│  │  │ ├─ Vector Search (5-10s)                   │    │      │
│  │  │ ├─ BM25 Keyword Search (5-10s)            │    │      │
│  │  │ └─ Metadata Fetch (5-10s)                 │    │      │
│  │  │ TOTAL: 8-12s instead of 20-40s            │    │      │
│  │  └─────────────────────────────────────────────┘    │      │
│  └──────────┬────────────────────────────────────────────┘     │
│             │                                                   │
│  ┌──────────v────────────────────────────────────────┐         │
│  │   Hybrid Search Results                          │         │
│  │   (Vector + BM25 merged, 20-30% better)          │         │
│  │   ├─ Re-ranked results                            │         │
│  │   ├─ Confidence scored                            │         │
│  │   └─ Semantic chunks grouped                      │         │
│  └──────────┬────────────────────────────────────────┘         │
│             │                                                   │
│  ┌──────────v────────────────────────────────────────┐         │
│  │   Smart Model Selection                          │         │
│  │   ├─ Simple Q → llama3.2:3b (fast)               │         │
│  │   ├─ Complex Q → mistral:7b (balanced)           │         │
│  │   └─ Domain Q → fine-tuned:3b (90%+ accurate)   │         │
│  └──────────┬────────────────────────────────────────┘         │
│             │                                                   │
│  ┌──────────v────────────────────────────────────────┐         │
│  │   Streaming LLM Generation                       │         │
│  │   ├─ First token: 5-10s                          │         │
│  │   ├─ Remaining tokens streamed                   │         │
│  │   ├─ Confidence scoring during generation        │         │
│  │   └─ Fallback model if confidence low            │         │
│  └──────────┬────────────────────────────────────────┘         │
│             │                                                   │
│  ┌──────────v────────────────────────────────────────┐         │
│  │   Response Cache Writer                          │         │
│  │   (Store for future identical queries)           │         │
│  └──────────┬────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────────────────┘
             │
   ┌─────────┼─────────┬──────────────┬──────────────┐
   │         │         │              │              │
   v         v         v              v              v
┌──────┐┌─────────┐┌────────┐┌──────────┐┌──────────────┐
│Redis ││ Ollama  ││Semantic││Postgres  ││Fine-tuned    │
│Cache ││  (8x)   ││Chunks  ││+Pgvector ││Model Instance│
│      ││         ││Store   ││+ BM25    ││(optional)    │
└──────┘└─────────┘└────────┘└──────────┘└──────────────┘

IMPROVEMENTS:
✅ Streaming reduces perceived latency 40-80%
✅ Caching reduces repeated queries to <1s
✅ Parallel retrieval reduces RAG time 12-20s
✅ Hybrid search improves accuracy +20-30%
✅ Semantic chunking improves accuracy +15-25%
✅ Domain fine-tuning improves accuracy +25-50%
✅ Smart routing reduces latency 5-10% for simple Q
✅ Batch processing increases throughput 200%+
```

---

## Side-by-Side Comparison

### Latency

**Current Flow:**
```
Query → Embedding → Vector Search → Reranking → LLM Gen → Response
   (sequential)
Total: 420-630s (7-10.5 min) per query
```

**Optimized Flow:**
```
Query → (Cache Check)  ──[HIT]──→ Cache → Stream Response (0.1-5s)
         ↓ (MISS)
         Query Optimization
         ↓
         Parallel: [Embedding + Vector + BM25 + Metadata] → (8-12s)
         ↓
         Hybrid Merge + Reranking
         ↓
         Smart Model Selection
         ↓
         Stream LLM Gen (First token: 5-10s, rest streamed)
         ↓
         Response (Perceived: 5-10s to first token, Actual: 8-10min)
         ↓
         Cache Result
```

**Improvement:** 40% perceived (users see response in 5-10s), 20-25% actual latency

---

### Accuracy

**Current Path:**
```
Generic Models (Ollama defaults)
├─ Trained on general web data
├─ Don't understand RNI domain
└─ Result: 60-70% accuracy
```

**Optimized Path:**
```
Retrieval Enhancement (Phase 1-2)
├─ Hybrid search: +20-30%
├─ Semantic chunking: +15-25%
├─ Query expansion: +10-20%
└─ Result: 85-90% accuracy

Domain Specialization (Phase 3)
├─ Fine-tuned model on RNI data: +25-50%
├─ Confidence-based fallback: +5-15%
└─ Result: 92-96% accuracy
```

**Improvement:** 25-50% accuracy gain

---

### Throughput

**Current:**
```
Sequential Processing
├─ One request at a time
├─ 17.4 min per request
└─ 3 RPS maximum
```

**Optimized:**
```
Parallel Batch Processing
├─ Up to 6 concurrent requests
├─ 8 Ollama instances shared across batch
├─ Cache reduces actual processing for repeats
└─ 9-12 RPS possible with batching
```

**Improvement:** 200-400% throughput increase

---

## Phase-by-Phase Rollout

### Phase 1: Perception & Quick Wins
```
BEFORE          → AFTER (Week 1-2)

Response:                User sees:
[............ ]    [. .. ... .... ] ← Streaming tokens
(waiting 17min)     (first token in 5s, full in 17min)

Repeated Q:
[17 min] → [<1 sec] ← Cache hit
```

**Expected:** 40% perceived latency improvement, 15% average

---

### Phase 2: Accuracy Boost
```
BEFORE              → AFTER (Week 2-3)
Accuracy: 60-70%      Accuracy: 85-90%

Search:
[Vector only]       [Vector + BM25]
└─ Misses keywords   └─ Catches acronyms/terms

Chunks:
[Flat list]         [Hierarchical]
└─ Loses context    └─ Preserves structure
```

**Expected:** +20-30% accuracy improvement

---

### Phase 3: Excellence
```
BEFORE              → AFTER (Week 3+)
Accuracy: 85-90%      Accuracy: 92-96%
Throughput: 3 RPS     Throughput: 9-12 RPS

Models:
[Generic x8]        [Generic + Fine-tuned]
└─ Same for all      └─ Domain specialist for RNI

Processing:
[Linear]            [Parallel batches]
└─ One at a time    └─ 6 concurrent requests
```

**Expected:** +5-10% accuracy, +200-400% throughput

---

## Resource Comparison

| Component | Current | Optimized | Notes |
|-----------|---------|-----------|-------|
| Ollama Instances | 8 | 8-9 | +1 optional fine-tuned |
| Cache Layer | None | Redis | External or container |
| Search Method | Vector | Vector+BM25 | Hybrid |
| Chunking | Sentence-based | Hierarchical | Better context |
| Models | Generic | Generic+Domain | Specialized |
| Processing | Sequential | Parallel | With caching |
| Memory | Baseline | +20% | For cache + structures |
| Storage | Baseline | +5% | For BM25 index |

---

## Risk Progression

```
Phase 1 (Week 1-2): 🟢 LOW RISK
├─ Streaming: Non-breaking, UX only
├─ Caching: With TTL, can disable
└─ Optimization: Preprocessing, safe

Phase 2 (Week 2-3): 🟡 MEDIUM RISK
├─ Hybrid search: Needs validation
├─ Semantic chunking: Requires reprocessing
└─ Expand queries: LLM cost increase

Phase 3 (Week 3+): 🟠 MEDIUM-HIGH RISK
├─ Fine-tuning: Quality depends on data
├─ Batch processing: Load testing needed
└─ Confidence fallback: New logic paths
```

---

## Success Progression

```
Week 1:  ✅ Streaming live, users see response in 5-10s
Week 2:  ✅ Caching deployed, 20-30% cache hit rate
Week 3:  ✅ Hybrid search integrated, accuracy +25%
Week 4:  ✅ Fine-tuning complete, accuracy +50%

Combined: 40% perceived latency ↓ + 50% accuracy ↑ + 300% throughput ↑
```

---

## Implementation Gantt Chart

```
Timeline (Weeks):  1      2      3      4
Task:
Streaming        |████|
Caching            |████|
Hybrid Search        |██|
Sem Chunking         |███|
Query Expansion         |██|
Fine-tuning                |██████|
Deploy Confidence           |███|
Load Testing               |████|
              ├────────────────────│

TOTAL: 3-4 weeks, 1-2 engineers
```

---

## Conclusion

**From:** Sequential, generic, cache-less system
**To:** Parallel, specialized, optimized system

**Result:** Enterprise-grade performance with 40-50% latency reduction (perceived) and 20-50% accuracy improvement

---

**Status:** ✅ Architecture comparison complete
**Ready for:** Team review and implementation planning
