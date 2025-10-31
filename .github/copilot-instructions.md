# AI Agent Productivity Quickstart
This guide distills essential knowledge for AI agents to be immediately productive in this codebase. For full details, see referenced docs and component READMEs.

### Architecture & Data Flow
- Unified Python worker system: PDF ingestion, chunking, embedding, hybrid search, confidence-based routing
- Key services: 4 Ollama containers (embedding), reranker (FastAPI), SearXNG (web search), unified chat frontend
- All config via `config.py` (never use `os.environ` directly)
- Data: Single `document_chunks` table in Postgres (see `init.sql`)

### Developer Workflows
- Build/run: `make up`, `make down`, `make logs`, `make test`, `make eval-sample`, `make recreate-db`
- Testing: `pytest` (unit/integration/e2e), markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`, `@pytest.mark.slow`
- AI test generation: `python ai_test_generator.py --scenario api --module reranker/app.py`
- Quality: `pre-commit install`, `pre-commit run --all-files`, `black`, `isort`, `autoflake`, `flake8`, `mypy . --show-error-codes`
- Security: `bandit -r . -f json`, `safety`, `pip-audit`

### Project Conventions
- Always import config from `config.py`
- Use custom exceptions from `utils/exceptions.py`
- Use Pydantic `BaseModel` + `Field` for API/data contracts
- No bare `except:`; log errors with context
- Use `@monitor_performance` and context managers for timing
- Tests: `tests/unit/`, `tests/integration/`, `tests/e2e/`, fixtures in `conftest.py`

### Integration Points
- Ollama: 4 containers, routed via nginx (`/ollama/`, `/ollama-2/`, ...)
- Reranker: FastAPI (`reranker/app.py`), endpoints `/api/hybrid-search`, `/api/intelligent-route`, `/api/ollama-health`
- SearXNG: Privacy-first web search, fallback for low-confidence queries
- Frontend: Unified chat, streaming, parameter controls, memory management
- Database: Postgres, single `document_chunks` table, JSONB metadata

### Key Files & Onboarding References
- `README.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md`, `CODE_QUALITY.md`, `CONTRIBUTING.md`
- `docs/HYBRID_SEARCH.md`, `pdf_processor/README.md`, `reranker/README.md`, `frontend/README.md`
- `Makefile`, `docker-compose.yml`, `init.sql`, `config.py`, `utils/exceptions.py`

### Common Tasks (Examples)
- Add PDF: Place in `uploads/`, worker auto-processes
- Test hybrid search: `curl -X POST http://localhost:8008/api/hybrid-search -d '{"query":"Latest JavaScript frameworks"}'`
- Debug routing: `docker logs reranker`
- Benchmark embeddings: `python bin/benchmark_all_embeddings.py`
- Run AI test generator: `python ai_test_generator.py --scenario api --module reranker/app.py`

---
# Copilot Instructions for Technical Service Assistant

## Project Overview
This is a **local-first** end-to-end PDF ingestion and **hybrid search pipeline** with **intelligent model routing**, **confidence-based search routing**, and **advanced accuracy improvements**. The architecture uses a **unified Python worker-based system** with enhanced retrieval capabilities, dynamic model selection, and **privacy-first web search fallback**. Key components:
- **PostgreSQL 16 + pgvector 0.8.1** for optimized vector storage and similarity search
- **4 parallel Ollama containers** (ports 11434-11437) with intelligent routing and load balancing - see [Ollama documentation](https://ollama.com/)
- **Enhanced Python PDF processor** with polling-based ingestion and accuracy improvements
- **BGE reranker service** with intelligent routing and **hybrid search endpoints** (port 8008)
- **SearXNG privacy-first search engine** (port 8888) with 8+ search engines for web fallback
- **Confidence-based routing** between document RAG and web search
- **Semantic chunking** preserving document structure and context
- **Unified chat interface**: Single dialog with configurable search modes and thresholds (port 8080)

## Architecture & Data Flow
Current **unified Python worker** with **intelligent routing** and **hybrid search**:
1. **File detection:** `pdf_processor/process_pdfs.py` polls `uploads/` every `POLL_INTERVAL_SECONDS` (60s default)
2. **Extraction:** PyMuPDF (text/images) + Camelot (tables) via `pdf_processor/utils.py` - **this is the single source of truth for all extraction logic**
3. **Chunking:** Sentence-based with overlap using NLTK punkt tokenizer - adds metadata (document name, page number, chunk type)
4. **Embeddings:** HTTP calls to Ollama containers (`nomic-embed-text:v1.5` default), with **intelligent routing** across benchmark containers
5. **Storage:** Direct postgres inserts to unified `document_chunks` table with integrated embeddings - see `init.sql` for schema
6. **Hybrid Search Routing:** `/api/hybrid-search` first tries RAG, then falls back to SearXNG web search if confidence < threshold
7. **Confidence Calculation:** Enhanced algorithm considers context relevance, uncertainty phrases, and query-context overlap
8. **Web Search Fallback:** SearXNG with HTML parsing fallback provides privacy-first search across 8+ engines
9. **Optional reranking:** BGE reranker service refines top-K results when enabled

**Eliminated N8N complexity:** All processing now uses unified Python worker architecture with `document_chunks` schema.

## Key Files & Directories
- **`config.py`**: Centralized configuration with env var loading - **all services import from here, never read os.environ directly**
- **`reranker/app.py`**: FastAPI service with search, chat, RAG, **hybrid search**, and intelligent routing endpoints (`/api/hybrid-search`, `/api/intelligent-route`, `/api/ollama-health`)
- **`frontend/index.html` + `app.js`**: **Unified chat interface** with configurable hybrid search, confidence thresholds, and search method indicators
- **`frontend/nginx.conf`**: Proxies for all 4 Ollama instances (`/ollama/`, `/ollama-2/`, `/ollama-3/`, `/ollama-4/`), reranker APIs, and SearXNG
- **`searxng/settings.yml`**: **NEW** - Privacy-first search configuration with 8+ engines and weighted results
- **`searxng/limiter.toml`**: **NEW** - Rate limiting and bot detection configuration for API access
- **`docs/HYBRID_SEARCH.md`**: **NEW** - Comprehensive documentation for hybrid search system
- **`enhanced_retrieval.py`**: **NEW** - Enhanced retrieval pipeline with two-stage search and quality metrics
- **`hybrid_search.py`**: **NEW** - Vector + BM25 hybrid search for technical term optimization
- **`semantic_chunking.py`**: **NEW** - Structure-aware chunking preserving document hierarchy
- **`test_enhanced_retrieval.py`**: **NEW** - A/B testing framework for accuracy validation
- **`pdf_processor/utils.py`**: Core extraction/chunking/embedding logic - unified across all ingestion pathways
- **`docker-compose.yml`**: 4 Ollama containers + pgvector + reranker + frontend + pdf_processor worker + **SearXNG search engine**

## Developer Workflows
**Essential commands:**
```bash
make up              # docker compose up -d --build
make down            # docker compose down
make logs            # docker logs -f pdf_processor
make test            # pytest
make eval-sample     # Run evaluation suite
make recreate-db     # Destructive: reset postgres volume
```

**Testing Chat Interfaces:**
- **Unified interface**: `http://localhost:8080/` - Hybrid search with configurable confidence thresholds and web fallback
- **SearXNG interface**: `http://localhost:8888/` - Direct access to privacy-first search engine
- **Hybrid search test**: `curl -X POST http://localhost:8008/api/hybrid-search -d '{"query":"Latest JavaScript frameworks", "confidence_threshold":0.3}'`
- **Web search test**: `curl -X GET http://localhost:8008/api/test-web-search`
- Intelligent routing test: `curl -X POST http://localhost:8008/api/intelligent-route -d '{"query":"code example"}'`

**Testing/Debugging:**
- `python test_connectivity.py` - health check all services
- `docker logs -f reranker` - watch intelligent routing decisions and API calls
- `python bin/benchmark_all_embeddings.py` - compare embedding models across 4 Ollama containers
- `python scripts/eval_suite.py eval/sample_eval.json --k 5 10 20` - quality metrics

**Enhanced Accuracy Testing (NEW):**
- `python enhanced_retrieval.py` - test enhanced vs standard retrieval
- `python test_enhanced_retrieval.py` - A/B comparison with metrics
- `python hybrid_search.py` - test vector vs BM25 vs hybrid search
- `python semantic_chunking.py` - analyze chunking strategies

**Adding PDFs:** Place in `uploads/` - worker polls and processes automatically

## Project Conventions
- **Configuration:** Use `config.py` Settings class - lazy-loaded, typed interface with defaults
- **Configuration:** Use `config.py` Settings class - lazy-loaded, typed interface with defaults
- **Intelligent Routing:** Question classification in `reranker/app.py` (`classify_question()`) maps to model selection (`select_model_for_question()`)
- **Frontend Integration:** Chat interfaces call `/api/intelligent-route` before generation, use returned `selected_model` and `instance_url`
- **Chunking strategy:** `sent_overlap` in `pdf_processor/utils.py` - sentence-based with previous sentence included for context
- **Embedding model testing:** Use multiple Ollama containers (ollama-server-1 through ollama-server-4) for parallel evaluation
- **Error handling:** Per-file error logs in `logs/` directory with model name context
- **Database schema:** Single `document_chunks` table with JSONB metadata column - see `migrations/` for evolution
- **Reranker integration:** Optional via `RERANK_MODEL` env var, improves retrieval quality
- **Frontend caching:** Aggressive cache-busting in nginx (`no-cache`, versioned assets) for development

## Integration Points & Service Communication
- **Frontend <-> Reranker:** HTTP API (port 8008) for `/search`, `/chat`, `/api/intelligent-route`, `/api/ollama-health`
- **Chat interfaces <-> Ollama:** Proxied through nginx (`/ollama/`, `/ollama-2/`, etc.) with intelligent routing
- **pdf_processor <-> Ollama:** HTTP API calls with automatic fallback across ports 11434-11437
- **Scripts <-> Postgres:** Direct connections via `psycopg2` using `config.py` database settings
- **All containers:** Share `uploads/` volume for file-based coordination
- **No N8N dependency:** Current architecture is pure Python + Docker

## Model Selection & Routing Patterns
- **Question Classification:** Technical → `mistral:7b`, Code → `codellama`, Chat → `llama2`, Default → `llama2`
- **Instance Health:** `/api/ollama-health` monitors all 4 instances, intelligent router selects healthy instances
- **Load Balancing:** Router distributes requests across healthy instances based on response time and load scores
- **Fallback Strategy:** Graceful degradation to primary instance (`ollama-server-1`) when routing fails
- **Frontend Headers:** `X-Ollama-Instance` header passes routing decisions from intelligent selection

## Common Tasks
- **Add new model routing:** Edit `classify_question()` and `select_model_for_question()` in `reranker/app.py`
- **Debug routing decisions:** Check `docker logs reranker` for routing logs and instance health checks
- **Add new embedding model:** Pull to Ollama containers, update `EMBEDDING_MODEL` in config, run benchmarks
- **Modify chat interface:** Edit `frontend/chat.html` + `chat.js`, rebuild frontend image (`docker compose build frontend`)
- **Change extraction:** Modify extraction functions in `pdf_processor/utils.py` - affects all ingestion paths
- **Database changes:** Add migration files to `migrations/` directory
- **Add nginx proxy routes:** Edit `frontend/nginx.conf` for new endpoints, rebuild and restart frontend

## Recent Features & Patterns (Follow Pydantic AI Standards)
See [Pydantic AI documentation](https://ai.pydantic.dev/) for AI agent patterns and best practices.
See [Anthropic documentation](https://www.anthropic.com/) for advanced AI safety and development practices.

- **Streaming Chat:** Real-time responses using Ollama's streaming API with proper JSON line parsing
- **Parameter Controls:** Temperature sliders and max token inputs in chat interface
- **Memory Management:** Conversation trimming to prevent context window overflow
- **Enhanced Error Handling:** Structured 422 parsing, retry logic, and user-friendly error messages
- **RAG Integration:** Foundation for document-aware responses combining retrieval + generation (see `RAGChatRequest` models)
- **Pydantic Models:** Use `BaseModel` with `Field` annotations for API contracts (see intelligent routing models as examples)

## Code Quality Standards & Enforcement
**Status: EXCELLENT** - Codebase maintains high quality standards with automated tools and pre-commit hooks.

### **Quality Tools & Configuration**
- **Black**: Code formatting (120 char line length) - `black --line-length=120`
- **isort**: Import organization with Black compatibility - `isort --profile=black --line-length=120`
- **autoflake**: Unused import/variable removal - `autoflake --remove-all-unused-imports --remove-unused-variables --in-place`
- **flake8**: Linting with project-specific rules - `flake8 --max-line-length=120 --extend-ignore=E203,W503,F541`
- **Pre-commit hooks**: Automated enforcement via `.pre-commit-config.yaml`

### **Mandatory Practices for All Code Changes**
1. **Always run pre-commit hooks before committing:**
   ```bash
   pre-commit install  # One-time setup
   pre-commit run --all-files  # Manual check
   ```

2. **Follow formatting standards:**
   - 120 character line length (Black enforced)
   - Consistent import organization (isort enforced)
   - No unused imports or variables (autoflake enforced)
   - No trailing whitespace (pre-commit enforced)

3. **Error handling requirements:**
   - **Never use bare `except:` clauses** - always specify exception types
   - Use proper logging instead of print statements where appropriate
   - Handle edge cases explicitly (file I/O, network requests, database operations)

4. **Code organization:**
   - All configuration imports via `config.py` - never read `os.environ` directly
   - Use type hints for function parameters and returns
   - Prefer `BaseModel` with `Field` annotations for API contracts
   - Follow existing patterns for database connections, HTTP clients, etc.

### **Quality Metrics & Current Status**
- **182 minor violations remaining** (mostly cosmetic f-string placeholder issues - F541)
- **Zero critical issues** (bare except clauses, unused imports, formatting inconsistencies)
- **100% consistent formatting** across entire codebase
- **Organized imports** in all Python files

### **When Adding New Code**
- **Use existing patterns:** Follow established conventions in similar files
- **Run quality checks:** Ensure pre-commit hooks pass before submitting
- **Document complex logic:** Add docstrings for non-trivial functions
- **Test thoroughly:** Verify functionality doesn't break existing features

### **Quality Enforcement Integration**
- **Pre-commit hooks** run automatically on every commit
- **CI/CD validation** can be added with: `pre-commit run --all-files`
- **IDE integration** available for VS Code, PyCharm with appropriate extensions
- **Manual tools** available for development: see `CODE_QUALITY.md` for complete usage guide

**Reference Documentation:** See `CODE_QUALITY.md` for comprehensive setup instructions, troubleshooting, and best practices.

## Enhanced Development Standards & Testing
**Status: COMPREHENSIVE** - Advanced development infrastructure with automated testing, monitoring, and CI/CD.

### **Testing Strategy & Infrastructure**
- **Pytest Framework**: Comprehensive test suite with organized structure
  - `tests/unit/`: Fast, isolated unit tests with mocking
  - `tests/integration/`: Component integration tests with real database
  - `tests/e2e/`: End-to-end workflow testing with Docker Compose
- **Coverage Requirements**: Minimum 70% code coverage with HTML/XML reports
- **Test Markers**: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`, `@pytest.mark.slow`
- **Fixtures**: Comprehensive test fixtures in `tests/conftest.py` for database, API clients, mock data

### **Static Analysis & Type Safety**
- **mypy**: Strict type checking with `mypy.ini` configuration
  - Enforces type annotations on all new code
  - Specific rules for tests/, scripts/, bin/ directories
  - Third-party library exclusions configured
- **Security Scanning**: Automated vulnerability detection
  - **bandit**: Security linting with `pyproject.toml` configuration
  - **safety**: Dependency vulnerability scanning
  - **pip-audit**: Additional dependency security checks

### **Performance & Monitoring**
- **Performance Decorators**: `@monitor_performance()` for function timing
- **Context Managers**: `with performance_context()` for code block monitoring
- **Prometheus Integration**: Optional metrics collection (`utils/monitoring.py`)
- **Memory Profiling**: `@profile_memory` decorator for memory analysis
- **System Metrics**: CPU, memory, disk usage logging

### **Error Handling Standards**
- **Custom Exception Hierarchy**: Structured exceptions in `utils/exceptions.py`
  - `TechnicalServiceError` base class with context and error codes
  - Specific exceptions: `PDFProcessingError`, `EmbeddingGenerationError`, `DatabaseError`, etc.
  - Serializable error format for API responses
- **Error Context**: Use error context managers for operation tracking
- **Structured Logging**: Enhanced logging with operation context and timing

### **CI/CD Pipeline Standards**
- **GitHub Actions**: Comprehensive pipeline in `.github/workflows/quality.yml`
  - **Quality Gates**: Pre-commit hooks, type checking, security scanning
  - **Testing Stages**: Unit → Integration → E2E with proper dependencies
  - **Coverage Reporting**: Automated coverage upload to Codecov
  - **Build Validation**: Docker image creation and smoke testing
  - **Security Reports**: Automated vulnerability scanning and reporting

### **Development Workflow Requirements**
1. **All code changes must**:
   - Pass pre-commit hooks (formatting, linting, security)
   - Include appropriate type annotations
   - Have corresponding tests (unit/integration as appropriate)
   - Maintain or improve code coverage
   - Pass all CI/CD pipeline stages

2. **Testing Requirements**:
   - New features require unit tests
   - API changes require integration tests
   - Major features require end-to-end tests
   - Performance-critical code requires benchmarks

3. **Code Organization**:
   - Use custom exceptions from `utils/exceptions.py`
   - Add performance monitoring for slow operations
   - Include proper error handling with context
   - Follow established patterns for database connections, HTTP clients

### **Documentation Standards**
- **Docstring Format**: Google-style docstrings enforced by pydocstyle
- **Type Annotations**: All public functions and methods must have type hints
- **API Documentation**: FastAPI auto-generated docs with enhanced schemas
- **Performance Notes**: Document performance characteristics for critical functions

### **When Adding New Features**
1. **Create tests first** (TDD approach recommended)
2. **Add type annotations** throughout
3. **Include performance monitoring** for non-trivial operations
4. **Use custom exceptions** for error handling
5. **Add security scanning exclusions** if needed (with justification)
6. **Update documentation** and API schemas
7. **Ensure CI/CD pipeline passes** before merging

### **Performance Standards**
- **API Response Times**: < 5 seconds for search operations
- **Memory Usage**: Monitor with profiling decorators
- **Database Operations**: Use connection pooling and query optimization
- **External API Calls**: Include timeout and retry logic
- **Concurrent Operations**: Test under load with threading/async patterns

**Integration Documentation:** See `DEVELOPMENT.md` for complete development setup, testing workflows, and contribution guidelines.
