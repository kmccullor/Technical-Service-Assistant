# Executive Summary: Technical Service Assistant

## Project Overview
The Technical Service Assistant is a production-ready, local LLM-powered retrieval-augmented generation (RAG) platform designed for enterprise knowledge management and technical support workflows. It integrates document processing, AI-driven categorization, intelligent model orchestration, and comprehensive monitoring to deliver accurate, context-aware responses from technical documentation.

## Key Goals
- Provide offline-capable, enterprise-grade knowledge assistance for Sensus AMI technology and equipment troubleshooting
- Enable advanced reasoning, document discovery, and multi-modal content processing (text, tables, images)
- Achieve high accuracy through specialized model routing, enhanced retrieval techniques, and iterative research capabilities
- Support scalable deployment with Docker, Kubernetes, and monitoring stacks (Prometheus, Grafana)

## Core Technologies
- **Backend**: Python/FastAPI (reranker service), PostgreSQL + pgvector for vector storage, Ollama for local LLM inference
- **Frontend**: Next.js/React with TypeScript, Radix UI components, Drizzle ORM
- **AI/ML**: 4 parallel Ollama instances with specialized models (Mistral, Llama, Gemma, Phi), FlagEmbedding for reranking, transformers for multimodal processing
- **Document Processing**: PyMuPDF, Camelot for PDF extraction, AI categorization with privacy detection
- **Infrastructure**: Docker Compose, Kubernetes, Redis caching, monitoring exporters
- **Development**: Pre-commit hooks, pytest testing rings, Black/isort formatting

## Main Components
- **reranker/**: FastAPI API server with RAG chat, reranking, intelligent routing, and analytics
- **pdf_processor/**: Document ingestion workers for PDF processing, chunking, embedding, and AI metadata enrichment
- **next-rag-app/**: Next.js UI for querying, authentication, and dashboards
- **reasoning_engine/**: Advanced reasoning with chain-of-thought, knowledge synthesis, and model orchestration
- **utils/**: Shared utilities for search, RBAC, logging, and metrics
- **monitoring/**: Prometheus/Grafana stack with health checks and performance tracking

## Key Features
- **AI Document Categorization**: Automatic classification, privacy detection, and metadata enrichment
- **Intelligent Model Routing**: Question classification with specialized model selection across 4 Ollama instances
- **Enhanced Retrieval**: Hybrid search (vector + BM25), iterative research, and quality metrics
- **Security & RBAC**: Role-based access control, API key authentication, privacy filtering
- **Monitoring & Quality**: Comprehensive metrics, feedback loops, and 95% test coverage targets
- **Extensibility**: Plugin architecture for new modalities, chunking strategies, and model integrations

## Architecture Highlights
- **Microservices Design**: Separated concerns across ingestion, API, and UI services
- **Vector Database**: Unified pgvector schema with AI-enriched metadata
- **Model Specialization**: 4-instance Ollama cluster optimized for different query types (chat/QA, code/technical, reasoning/math, embeddings)
- **Production Readiness**: Docker deployment, health monitoring, automated testing, and operational tooling

## Notable Aspects
- **Local/Offline Capability**: No external API dependencies, ensuring data privacy and reliability
- **Advanced Accuracy**: 30-50% improvement through enhanced retrieval and iterative research
- **Enterprise Focus**: Built for Sensus AMI systems with SQL query generation and technical documentation support
- **Developer Experience**: Comprehensive tooling, linting, testing, and documentation for maintainable codebase

The system represents a sophisticated, production-hardened implementation of modern RAG architecture, optimized for technical service scenarios with strong emphasis on accuracy, scalability, and operational reliability.
