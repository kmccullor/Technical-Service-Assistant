# Repository Guidelines

## Project Structure & Module Organization
- Core services: `reranker/` (FastAPI, routing, embeddings) and `pdf_processor/` (ingestion workers).
- UI lives in `next-rag-app/`; shared helpers sit in `utils/` and operational scripts in `scripts/`.
- Test suites under `tests/` with ring orchestration via `test_runner.py`; migrations reside in `migrations/`, seed SQL in `init.sql`, and reference docs in `ARCHITECTURE.md` and `DEVELOPMENT.md`.

## Build, Test, and Development Commands
- Bootstrap dependencies with `make install`; activate `.venv` before running tooling.
- Run the stack using `make up` / `make down`; individual service definitions are in `docker-compose.yml`.
- Use `make test` for the default focused coverage run, `make test-all` for every ring, and `make quality-report` to refresh QA dashboards.
- Daily ops checks: `make health-check` for container status and `make check-db` when verifying ingestion data.

## Coding Style & Naming Conventions
- Python formatting uses Black (120 cols), isort, and 4-space indentation; `pre-commit run --all-files` mirrors CI enforcement.
- Modules and packages follow snake_case; keep functions descriptive and typed. Prefer Google-style docstrings to satisfy `pydocstyle`.
- Linting and security gates rely on `flake8`, `mypy`, and `bandit`; their options live in `pyproject.toml` and `mypy.ini`.

## Testing Guidelines
- Pytest is organized by rings (`unit`, `integration`, `e2e`); mark tests accordingly and keep assets in `tests/fixtures/`.
- Minimum coverage is 95% for targeted modules; match CI locally with `pytest --cov --cov-fail-under=95`.
- Use `test_runner.py --ring 1` for pre-commit smoke verification and `--all --performance` before release branches.

## Commit & Pull Request Guidelines
- Prefer conventional commit headers (`feat`, `fix`, `chore`) or the established "End of day commit - YYYY-MM-DD" pattern when batching maintenance.
- PRs should include a short summary, linked issues, test results, and UI screenshots or logs when relevant; keep generated artifacts out of Git.
- Ensure `pre-commit` and `make test` pass before pushing; reference quality metrics (coverage, dashboards) in the PR description if they informed the change.

## Security & Configuration Tips
- Application settings resolve via environment precedence in `config.py`; update `.env.example` when adding keys and never commit local `.env` files.
- After environment resets, run `make seed-rbac`; for data integrity checks use `make check-db` or `scripts/advanced_health_check.sh`.
- Rotate secrets in non-local environments and confirm `docker-compose.production.yml` mirrors required overrides before deploying.
