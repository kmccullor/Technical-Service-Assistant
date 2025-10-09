# Diagrams

Visual aids for understanding ingestion, retrieval, and reranking sequences. Render Mermaid locally (many IDEs/extensions support it) or convert to images for external docs.

## Ingestion (Worker Mode)
```mermaid
sequenceDiagram
    participant FS as Filesystem (uploads/)
    participant W as pdf_processor
    participant U as utils.py
    participant O as Ollama (Embeddings)
    participant DB as Postgres+PGVector

    FS->>W: New PDF detected (poll)
    W->>U: extract_text(pdf)
    U-->>W: text pages
    W->>U: chunk_text(text)
    U-->>W: chunks[]
    loop per chunk
      W->>O: POST /api/embeddings (model, chunk)
      O-->>W: vector[]
      W->>DB: INSERT chunk + vector
    end
    W->>FS: Move PDF to archive (optional)
```

## Retrieval + Rerank + Answer
```mermaid
sequenceDiagram
    participant User
    participant R as Retrieval Script
    participant O as Ollama (Embeddings)
    participant DB as Postgres+PGVector
    participant RR as Reranker API
    participant L as Ollama (LLM)

    User->>R: Query
    R->>O: Embed(query)
    O-->>R: query_vec
    R->>DB: Similarity search (LIMIT N)
    DB-->>R: candidate chunks
    R->>RR: /rerank (query, candidates)
    RR-->>R: reranked top_k
    R->>L: Chat(model, context + question)
    L-->>R: Answer
    R-->>User: Response
```

## Benchmarking Multiple Embedding Models
```mermaid
flowchart LR
    subgraph Bench Scripts
      A[benchmark_all_embeddings.py]
    end
    A --> C1[Ollama 11434]
    A --> C2[Ollama 11435]
    A --> C3[Ollama 11436]
    A --> C4[Ollama 11437]
    C1 & C2 & C3 & C4 --> M[Metrics Aggregation]
    M --> R[Reports logs/*.html]
```

---
Add more diagrams as new components (e.g., hybrid search, caching, OCR layer) are introduced.

## Evaluation Metrics Flow
```mermaid
flowchart LR
  Q[Queries + Relevance Spec] --> E[eval_suite.py]
  E -->|Embed queries| O[Ollama]
  E -->|Vector search| DB[(PGVector)]
  DB --> E
  E --> M[Metrics JSON]
  M --> R[(Recall@K\\nMRR\\nnDCG)]
```
