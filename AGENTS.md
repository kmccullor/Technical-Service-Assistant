# Agent Guidelines for Technical Service Assistant

## Build/Lint/Test Commands
- **Install**: `make install` (creates venv + installs deps)
- **Lint**: `pre-commit run --all-files` (black, isort, autoflake, flake8, mypy, bandit, pydocstyle)
- **Test all**: `make test` or `pytest`
- **Single test**: `pytest tests/path/to/test.py::TestClass::test_method -v`
- **Test rings**: `python test_runner.py --ring 1` (unit), `--ring 2` (integration), `--ring 3` (e2e)
- **Coverage**: `pytest --cov=module --cov-report=html`

## Code Style Guidelines
- **Formatting**: Black (120 char lines), isort imports, 4-space indentation
- **Naming**: snake_case for modules/functions/variables, PascalCase for classes
- **Types**: Full type hints required, use `typing` module imports
- **Imports**: Group stdlib, third-party, local; use absolute imports
- **Docstrings**: Google-style required for public functions
- **Error handling**: Use custom exceptions from `utils/exceptions.py`, never bare `except:`
- **Configuration**: Always import from `config.py`, never `os.environ` directly
- **Security**: No secrets in code, use environment variables via config.py
