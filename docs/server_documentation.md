# Server and Resource Documentation

> Navigation: See `ARCHITECTURE.md` for end-to-end flow, `SCRIPTS.md` for executable references, `EMBEDDINGS.md` for model strategy, and `TROUBLESHOOTING.md` for common issues.

## Overview
This document provides a reference for the Technical Service Assistant server and its resources, including service details, ports, credentials, and integration notes.

## Services

### pgvector (Postgres)
- **Image:** pgvector/pgvector:pg16
- **Container Name:** pgvector
- **Port:** 5432
- **Database:** vector_db
- **User:** postgres
- **Password:** postgres
- **Volume:** pgvector_data
- **Notes:** Optimized for vector storage and similarity search. Includes health checks for readiness.

### Redis Cache
- **Image:** redis:7-alpine
- **Container Name:** redis-cache
- **Port:** 6379
- **Notes:** Configured for response caching with LRU eviction policy. Includes health checks.

### Ollama Servers
- **Images:** ollama/ollama
- **Container Names:** ollama-server-1, ollama-server-2, ollama-server-3, ollama-server-4
- **Ports:** 11434, 11435, 11436, 11437
- **Volumes:** ollama_data_1, ollama_data_2, ollama_data_3, ollama_data_4
- **Notes:** Local LLM and embedding model servers. Used for text generation and embedding. Includes health checks.

### Reranker
- **Build Context:** ./reranker
- **Container Name:** reranker
- **Port:** 8008
- **Environment Variables:**
  - DB_HOST=pgvector
  - DB_PORT=5432
  - DB_NAME=vector_db
  - DB_USER=postgres
  - DB_PASSWORD=postgres
  - OLLAMA_URL=http://ollama-server-1:11434
  - EMBEDDING_MODEL=nomic-embed-text
  - CHAT_MODEL=mistral:7B
  - RERANK_MODEL=BAAI/bge-reranker-base
- **Notes:** Handles reranking of search results. Includes health checks.

### PDF Processor
- **Build Context:** ./pdf_processor
- **Container Name:** pdf_processor
- **Environment Variables:**
  - DB_HOST=pgvector
  - DB_PORT=5432
  - DB_NAME=vector_db
  - DB_USER=postgres
  - DB_PASSWORD=postgres
  - UPLOADS_DIR=/app/uploads
  - POLL_INTERVAL_SECONDS=60
  - EMBEDDING_MODEL=nomic-embed-text:v1.5
  - LOG_DIR=/app/logs
- **Notes:** Processes PDF uploads for text extraction and embedding. Includes health checks.

### Next.js RAG Application
- **Build Context:** ./next-rag-app
- **Container Name:** rag-app
- **Port:** 3000
- **Environment Variables:**
  - DATABASE_URL=postgresql://postgres:postgres@pgvector:5432/vector_db
  - USE_LOCAL_MODELS=true
  - OLLAMA_BASE_URL=http://ollama-server-1:11434
  - OLLAMA_INSTANCES=http://ollama-server-1:11434,http://ollama-server-2:11434,http://ollama-server-3:11434,http://ollama-server-4:11434
  - EMBEDDING_MODEL=nomic-embed-text:v1.5
  - CHAT_MODEL=mistral:7b
  - NODE_ENV=production
  - NEXT_PUBLIC_APP_URL=http://RNI-LLM-01.lab.sensus.net:3000
  - RERANKER_ENABLED=true
  - CONFIDENCE_THRESHOLD=0.2
  - VECTOR_WEIGHT=0.6
  - LEXICAL_WEIGHT=0.4
  - MAX_TOKENS=1024
  - TEMPERATURE=0.3
  - WEB_SEARCH_ENABLED=false
  - CACHE_TTL=3600
  - OLLAMA_TIMEOUT=30000
  - REQUEST_TIMEOUT=45000
  - RERANKER_BASE_URL=http://reranker:8008
  - USE_RERANKER_WEBSEARCH=true
  - REDIS_URL=redis://redis:6379
- **Notes:** Main web interface for RAG application. Includes health checks.

### Monitoring Services
#### Prometheus
- **Image:** prom/prometheus:latest
- **Container Name:** prometheus
- **Port:** 9091
- **Notes:** Collects metrics for monitoring. Includes health checks.

#### Grafana
- **Image:** grafana/grafana:latest
- **Container Name:** grafana
- **Port:** 3001
- **Notes:** Visualization service for metrics. Includes health checks.

#### Exporters
- **Ollama Exporter:** Collects metrics from Ollama servers. Port: 9105.
- **Postgres Exporter:** Collects metrics from pgvector. Port: 9187.
- **Redis Exporter:** Collects metrics from Redis. Port: 9121.
- **Node Exporter:** Collects host system metrics. Port: 9100.
- **cAdvisor:** Collects container metrics. Port: 8081.

## Integration
- **PDF Ingestion:** `pdf_processor` handles text extraction and embedding storage in pgvector.
- **LLM/Embeddings:** Ollama servers provide local LLM and embedding models.
- **Web Interface:** Next.js RAG app serves as the main user interface.
- **Monitoring:** Prometheus and Grafana provide metrics and visualization.

## Volumes
- pgvector_data
- redis_data
- ollama_data_1
- ollama_data_2
- ollama_data_3
- ollama_data_4
- prometheus_data
- grafana_data
- temp_uploads

## OS/Platform
- Rocket9 Linux
- Python (for scripting and integration)

## References
- Supabase: https://github.com/supabase/supabase
- Ollama: https://github.com/ollama/ollama

---
Update this file as services change. For architectural changes update `ARCHITECTURE.md` first, then cross-link here.