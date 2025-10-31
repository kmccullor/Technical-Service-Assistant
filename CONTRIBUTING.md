# Contributing to Technical Service Assistant

Welcome to the Technical Service Assistant project! This guide will help you contribute effectively while maintaining our high code quality standards.

## 🎯 **Project Status**

**Code Quality**: EXCELLENT (Production Ready)
- 182 minor violations remaining (mostly cosmetic f-string placeholders)
- Zero critical issues (bare except clauses, unused imports, formatting resolved)
- 100% consistent formatting across entire codebase
- Enterprise-grade development infrastructure with full automation

## 🛠️ **Development Setup**

### Prerequisites
- Python 3.9+
- Git with pre-commit hooks support
- Docker and Docker Compose (for integration testing)
- PostgreSQL 16 with pgvector (for local development)

### Quick Start
```bash
# Clone and setup
git clone <repository-url>
cd Technical-Service-Assistant

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Verify setup
pre-commit run --all-files
pytest tests/unit/
```

## 📋 **Contribution Requirements**

### **Mandatory Quality Gates**
All contributions must pass these automated checks:

1. **✅ Code Formatting**
   - Black formatting (120 char line length)
   - isort import organization
   - No trailing whitespace

2. **✅ Type Safety**
   - mypy static type checking
   - Type annotations for all new functions
   - Proper handling of Optional types

3. **✅ Security Scanning**
   - bandit security vulnerability detection
   - safety dependency vulnerability checking
   - No high-severity security issues

4. **✅ Testing Requirements**
   - Unit tests for new features
   - Integration tests for API changes
   - Maintain 70% minimum code coverage

5. **✅ Code Quality**
   - flake8 linting compliance
   - No unused imports or variables
   - Proper error handling (no bare except clauses)

### **Development Workflow**

#### **Before Making Changes**
```bash
# Update dependencies
pip install -r requirements-dev.txt

# Run quality checks
pre-commit run --all-files

# Run tests
pytest
```

#### **Making Changes**
1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Follow Code Standards**
   - Use type hints for all new functions
   - Add docstrings (Google style) for public functions
   - Include error handling with custom exceptions
   - Add performance monitoring for slow operations

3. **Write Tests**
   ```bash
   # Unit tests (fast, isolated)
   tests/unit/test_your_feature.py

   # Integration tests (component interaction)
   tests/integration/test_your_feature_integration.py

   # E2E tests (complete workflows, if applicable)
   tests/e2e/test_your_feature_workflow.py
   ```

4. **Performance Considerations**
   ```python
   from utils.monitoring import monitor_performance, performance_context

   @monitor_performance("your_operation")
   def your_function():
       with performance_context("database_query"):
           # Your implementation
           pass
   ```

#### **Before Committing**
```bash
# Format code
black .
isort .

# Check types
mypy .

# Run security scans
bandit -r .
safety check

# Run tests with coverage
pytest --cov=. --cov-report=html

# Pre-commit will run automatically on commit
git add .
git commit -m "feat: your descriptive commit message"
```

## 🧪 **Testing Guidelines**

### **Test Organization**
```
tests/
├── unit/           # Fast (<1s), isolated, mocked dependencies
├── integration/    # Component tests with real services
├── e2e/           # Complete workflow tests
├── fixtures/      # Shared test data
└── conftest.py    # Pytest configuration and fixtures
```

### **Writing Tests**
```python
import pytest
from unittest.mock import Mock, patch

class TestYourFeature:
    """Test your feature functionality."""

    @pytest.mark.unit
    def test_unit_functionality(self, mock_database):
        """Test isolated unit functionality."""
        # Fast, isolated test with mocks
        pass

    @pytest.mark.integration
    def test_integration_workflow(self, test_client):
        """Test component integration."""
        # Test with real services but controlled environment
        pass

    @pytest.mark.e2e
    @pytest.mark.slow
    def test_complete_workflow(self):
        """Test complete user workflow."""
        # Full system test (may be slow)
        pass
```

### **Test Execution**
```bash
# Run all tests
pytest

# Run specific test types
pytest -m unit              # Fast unit tests only
pytest -m integration       # Integration tests
pytest -m "not slow"        # Skip slow tests

# Run with coverage
pytest --cov=. --cov-report=html
```

## 🔒 **Security Guidelines**

### **Security Requirements**
- Never commit secrets, API keys, or credentials
- Use environment variables for configuration
- Validate all user inputs
- Use parameterized queries for database operations
- Handle file uploads securely

### **Security Scanning**
```bash
# Check for vulnerabilities
bandit -r .

# Check dependencies
safety check
pip-audit

# Security will be checked automatically in CI/CD
```

## 📊 **Performance Guidelines**

### **Performance Requirements**
- API responses < 5 seconds
- Database queries optimized with proper indexing
- Memory usage monitored and profiled
- Concurrent operations tested

### **Performance Monitoring**
```python
from utils.monitoring import monitor_performance, PerformanceTimer

# For functions
@monitor_performance("pdf_processing")
def process_pdf(file_path: str):
    pass

# For code blocks
with PerformanceTimer("complex_operation"):
    # Your code here
    pass
```

## 📚 **Documentation Standards**

### **Code Documentation**
```python
def process_document(file_path: str, chunk_size: int = 1000) -> List[DocumentChunk]:
    """Process a document and extract structured content.

    Args:
        file_path: Absolute path to the document file
        chunk_size: Maximum characters per chunk

    Returns:
        List of DocumentChunk objects with extracted content

    Raises:
        PDFProcessingError: If document processing fails
        ValidationError: If file_path is invalid

    Example:
        >>> chunks = process_document("/path/to/doc.pdf", 500)
        >>> print(f"Extracted {len(chunks)} chunks")
    """
```

### **API Documentation**
- Use FastAPI with comprehensive schemas
- Include request/response examples
- Document error responses
- Add operation descriptions and tags

## 🚀 **CI/CD Pipeline**

### **Automated Checks**
Every pull request automatically runs:
1. **Quality Gates**: Pre-commit hooks, formatting, linting
2. **Type Checking**: mypy static analysis
3. **Security Scanning**: bandit, safety vulnerability checks
4. **Testing Pipeline**: Unit → Integration → E2E progression
5. **Coverage Reporting**: Codecov integration with 70% minimum
6. **Build Validation**: Docker image creation and testing

### **Pipeline Status**
- ✅ Must pass all quality gates
- ✅ Must maintain test coverage
- ✅ Must pass security scans
- ✅ Must build successfully

## 🔄 **Review Process**

### **Pull Request Requirements**
1. **✅ Description**: Clear description of changes and rationale
2. **✅ Tests**: Appropriate test coverage for changes
3. **✅ Documentation**: Updated docs for user-facing changes
4. **✅ Performance**: No significant performance regressions
5. **✅ Security**: No new security vulnerabilities
6. **✅ Compatibility**: Backwards compatibility maintained

### **Review Checklist**
- [ ] Code follows established patterns and conventions
- [ ] Tests are comprehensive and well-organized
- [ ] Documentation is updated and accurate
- [ ] Performance impact is acceptable
- [ ] Security considerations are addressed
- [ ] Error handling is robust and consistent

## 🆘 **Getting Help**

### **Resources**
- **Code Quality**: See [CODE_QUALITY.md](CODE_QUALITY.md)
- **Development Setup**: See [DEVELOPMENT.md](DEVELOPMENT.md)
- **Project Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md)
- **API Documentation**: Available at `/docs` when running locally

### **Common Issues**
```bash
# Pre-commit hook failures
pre-commit run --all-files

# Type checking errors
mypy . --show-error-codes

# Test failures
pytest -vvv --tb=long

# Security scan issues
bandit -r . -f json
```

### **Support Channels**
- **Issues**: GitHub Issues for bugs and feature requests
- **Discussions**: GitHub Discussions for questions and ideas
- **Documentation**: Project wiki for detailed guides

## 🎖️ **Recognition**

Contributors who consistently follow these guidelines and help maintain our high quality standards will be recognized in:
- Project README.md contributors section
- Release notes for significant contributions
- Code review acknowledgments

---
Thank you for contributing to the Technical Service Assistant project and helping maintain our excellent code quality standards! 🚀

## 🧪 Experimental & Archival Directories

### `experiments/`
Purpose: Houses historical phase scripts, benchmarking utilities, exploratory prototypes, and research artifacts that are not part of the production runtime.

Policies:
- Not subject to strict type or coverage thresholds (relaxed in mypy + coverage config)
- Should not be imported by core production modules (avoid creating hidden runtime dependencies)
- Filenames should be descriptive (e.g., `phase3b_reranking_ablation.py`)
- Add a header comment noting status: ACTIVE EXPERIMENT, DEPRECATED, or REFERENCE ONLY
- Migrate any experiment that graduates to production into an appropriate package (e.g., `reranker/`, `utils/`, etc.) and remove the experimental copy to avoid divergence

### `results/`
Purpose: Central location for JSON/metrics artifacts generated by evaluation, benchmarking, or reliability runs.

Policies:
- Large or binary artifacts (>5MB) should be compressed or excluded via .gitignore if reproducible
- Include a README.md summarizing artifact generation commands
- Prefer deterministic naming: `<area>_<date>_<descriptor>.json`

### `backup/`
Purpose: Contains timestamped project snapshots and end-of-day archive captures. These may include partial or truncated files (not intended for execution).

Policies:
- Excluded from lint/type/security enforcement
- Never modify historical snapshots—create a new one instead
- Do not import from `backup/` in any active code
- Consider periodic compression (`scripts/archive_old_backups.sh` once added)

### Adding New Experiments
1. Place in `experiments/` with a clear, date-stamped docstring
2. Avoid adding new third-party dependencies unless justified
3. If it requires sample data, store under `data/` (not inside experiment file)
4. Open a tracking issue if experiment is intended to graduate

### Graduation Checklist (Experiment → Production)
- [ ] Core logic moved into appropriate module
- [ ] Added tests (unit + integration if applicable)
- [ ] Added documentation (README / architecture notes)
- [ ] Performance considerations reviewed
- [ ] Security implications assessed
- [ ] Experimental script removed or replaced with a thin launcher referencing production code

This structure keeps the root clean, preserves research velocity, and protects production stability.
