# Technical Service Assistant

[Previous content remains the same until the CI/CD section...]

## Development and Testing

### Prerequisites
- Python 3.9+
- Docker and Docker Compose
- PostgreSQL 16 with pgvector extension
- Git with pre-commit hooks

### Development Setup
```bash
# Clone the repository
git clone <repository-url>
cd Technical-Service-Assistant

# Set up Python virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or .venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration
```

### Editor Workflows

#### Codex CLI
1. From the project root run `codex` (or `codex run`) to launch the Codex CLI in this workspace.  
2. Use the built-in commands to inspect files (`ls`, `sed`, `rg`) and run project tasks (`make test`, `pytest tests/unit`, `docker compose up`).  
3. Keep the Python virtual environment activated inside the Codex shell so installs resolve to `.venv`. Use `pip install -r requirements*.txt` and re-run `pre-commit run --all-files` after making changes.  
4. When editing files, prefer `apply_patch` or the Codex editor helpers so diffs stay clean. Run `git status` periodically and stage only the files you intentionally changed.  
5. Before finishing the Codex session, execute the relevant project checks (`make lint`, `pytest`, `npm test` inside `next-rag-app`) so CI parity is maintained.

#### Visual Studio Code
1. Install recommended extensions: Python, Pylance, Ruff or Flake8, isort, Black Formatter, Docker, YAML, Even Better TOML, Prisma (for Drizzle SQL), Tailwind CSS, ESLint, and Prettier.  
2. Open the repository folder (`File → Open Folder…`). VS Code should detect the `.venv` environment; if not, select it manually from the command palette (`Python: Select Interpreter`).  
3. Configure formatting by enabling `"python.formatting.provider": "black"`, `"editor.defaultFormatter": "ms-python.black-formatter"`, and `"python.sortImports.args": ["--profile", "black"]` in `.vscode/settings.json`. Ensure `"editor.formatOnSave": true`.  
4. Create `.vscode/launch.json` entries for the FastAPI backend (`uvicorn reranker.app:app --reload`) and key scripts such as `quality_monitor.py`. Include an npm launch task for the Next.js app (`cd next-rag-app && npm run dev`).  
5. Add VS Code tasks for the common workflows (`make test`, `pre-commit run --all-files`, `pytest tests/reranker/test_reranker_app.py`, `npm --prefix next-rag-app test`). Map them to keyboard shortcuts or the command palette to mirror CI.  
6. Use the Docker extension to manage the local stack (`docker compose up`/`down`) and view container logs. For database inspection, connect to the Postgres service with the SQLTools extension using the credentials from `.env`.  
7. Leverage the Test Explorer UI (Python and Jest) to rerun focused tests. Watch the Problems panel for lint/type errors flagged by Pylance and Ruff/Flake8.

### Code Quality Standards
This project maintains **excellent code quality** with automated enforcement:

- **Black**: Code formatting (120 char line length)
- **isort**: Import organization  
- **autoflake**: Unused import/variable removal
- **flake8**: Style and error checking
- **mypy**: Static type checking
- **bandit**: Security vulnerability scanning
- **pytest**: Comprehensive testing with coverage

### Running Tests
```bash
# Run all tests
make test

# Run specific test suites
pytest tests/unit/          # Unit tests only
pytest tests/integration/   # Integration tests  
pytest tests/e2e/          # End-to-end tests

# Run with coverage
pytest --cov=. --cov-report=html

# Run performance tests
pytest -m "not slow"        # Skip slow tests
pytest -m "slow"           # Run only slow tests
```

### Quality Checks
```bash
# Run all quality checks
pre-commit run --all-files

# Individual tools
black --check .             # Check formatting
mypy .                      # Type checking
bandit -r .                 # Security scanning
safety check               # Dependency vulnerabilities
```

### CI/CD Pipeline
The project includes a comprehensive GitHub Actions pipeline:

- **Quality Gates**: Code formatting, type checking, security scanning
- **Testing**: Unit, integration, and end-to-end tests
- **Coverage**: Automated coverage reporting with Codecov
- **Security**: Vulnerability scanning with bandit and safety
- **Build**: Docker image creation and validation
- **Deployment**: Automated deployment preparation

Pipeline runs on every push and pull request, ensuring code quality standards are maintained.

### Performance Testing
```bash
# Run performance benchmarks
python scripts/benchmark_system.py

# Memory profiling
python -m memory_profiler script_name.py

# Line profiling
kernprof -l -v script_name.py
```

### Contributing Guidelines

1. **Code Quality**: All code must pass pre-commit hooks and CI pipeline
2. **Testing**: New features require corresponding tests
3. **Documentation**: Update relevant documentation for changes
4. **Type Hints**: All new code should include proper type annotations
5. **Security**: Run security scans before submitting changes

### Testing Strategy

#### Unit Tests (`tests/unit/`)
- Fast, isolated tests for individual functions and classes
- Mock external dependencies
- High coverage of core business logic
- Run in < 10 seconds total

#### Integration Tests (`tests/integration/`)
- Test component interactions
- Use real database (test instance)
- Mock external APIs (Ollama, SearXNG)
- Focus on data flow and API contracts

#### End-to-End Tests (`tests/e2e/`)
- Complete workflow testing
- Use Docker Compose for full environment
- Test user-facing functionality
- Performance and load testing

### Monitoring and Observability

The system includes built-in monitoring capabilities:

```python
# Performance monitoring
from prometheus_client import start_http_server, Counter, Histogram

# Start metrics server
start_http_server(8000)

# Custom metrics
pdf_processed = Counter('pdfs_processed_total', 'Total PDFs processed')
processing_time = Histogram('pdf_processing_seconds', 'PDF processing time')
```

### Debugging

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with profiling
py-spy top --pid <process_id>

# Memory analysis
python -m memory_profiler app.py

# Database query analysis
export EXPLAIN_QUERIES=true
```

### Backend Modularization Roadmap
- Extract RBAC and authentication routes from `reranker/app.py` into dedicated `routers/auth.py` and `routers/admin.py` modules; register them in the main FastAPI app from a lightweight `create_app()` factory.  
- Move long-running utilities (metrics, document retrieval, cache, knowledge corrections) into service classes under `services/` so routers import only their interfaces, not database plumbing.  
- Introduce a shared `deps.py` module for FastAPI dependency wiring (auth manager, DB sessions, settings) to eliminate repeated `sys.path.append` calls and simplify testing.  
- Convert synchronous database helpers to explicit repository objects (e.g., `UserRepository`, `VerificationTokenRepository`) that encapsulate thread-pool execution; reuse them in background jobs and tests.  
- As modules split, add targeted unit tests per router/service to reduce reliance on the sprawling `tests/test_reranker_app.py`.

### Common Development Tasks

```bash
# Add new dependency
pip install new-package
pip freeze | grep new-package >> requirements.txt

# Update dependencies
pip-compile requirements.in
pip-compile requirements-dev.in

# Database migrations
python scripts/migrate_database.py

# Code formatting
black .
isort .

# Security check
bandit -r .
safety check
```

[Rest of the documentation continues as before...]
