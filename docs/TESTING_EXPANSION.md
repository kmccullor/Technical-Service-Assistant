# Testing Expansion Roadmap

This document tracks the initiatives required to deliver the broader test coverage that now includes service validation, load testing, performance profiling, and response accuracy verification.

## 1. Service Operation Validation

- `make smoke-test` executes `scripts/service_smoke_test.py`, which:
  - Verifies `/health`, `/api/auth/health`, and `/api/ollama-health`.
  - Probes nginx/frontend, Prometheus, Grafana, Redis, Postgres, and all Ollama instances.
  - Fails fast when a dependency is unhealthy so deployments can block automatically.
- TODO:
  - Integrate the smoke test with CI (e.g., `quality.yml`) and nightly cron to catch drifting services.
  - Extend the script with authenticated chat and ingestion probes once stable mock credentials exist.
  - ✅ `quality.yml` now includes a `smoke-test` job that runs on the self-hosted runner after unit+integration suites succeed; it executes `make smoke-test` so production services are validated before deployment prep.

## 2. Load & Stress Testing

- Existing artifacts: `stress_test.py` and historical JSON outputs in `stress_test_results_*.json`.
- Next steps:
  - ✅ Added `scripts/testing/load_test.py` (backed by `k6`) plus a `make load-test` target. Defaults: 100 VUs for 2 minutes, hitting `/health`, `/api/ollama-health`, `/api/auth/health`, `/api/chat`. Results and thresholds export to `load_test_results/`.
  - Capture Prometheus/Grafana metrics during the run (export as attachments) and fail the job when p95 latency or error-rate SLOs are exceeded.
  - Schedule high-load runs (e.g., nightly) and store results for regression analysis.

## 3. Performance UX Testing

- Planned improvements:
  - Add automated Lighthouse/Playwright sweeps for the Next.js frontend (login, chat, data dictionary).
  - Instrument backend endpoints with timing metrics surfaced in Prometheus dashboards.
  - Profile resource usage (`py-spy`, `perf`) during load tests to pinpoint bottlenecks and feed optimizations back into the codebase.

## 4. Accuracy & Quality

- Goal: enforce “100% correct” responses on a curated evaluation set.
- Proposed workflow:
  - Build a labeled dataset (questions, expected answers, citations) sourced from existing QA scripts.
  - Create `make eval-accuracy` that runs the dataset through the live stack, evaluates semantic similarity plus rule-based checks, and outputs a pass/fail report.
  - Hook the evaluation into CI so regressions block releases; expose the latest accuracy score inside `quality_dashboard.html`.

By iteratively tackling each section, the project will gain confidence across reliability, scalability, user experience, and answer correctness.
