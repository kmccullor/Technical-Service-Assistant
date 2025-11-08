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
  - ✅ Added `scripts/testing/load_test_report.py` so nightly runs can enforce p95/failure thresholds and fail CI when SLOs regress.
  - ✅ Added `scripts/reporting/nightly_summary.py` to aggregate the latest load + accuracy results into Markdown in `reports/` for quick review.
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
  - ✅ Added `tests/data/accuracy_dataset.json` along with `scripts/testing/accuracy_eval.py` and `make eval-accuracy`. The harness streams `/api/chat`, checks required keywords, and writes JSON summaries to `tests/accuracy_logs/`.
  - Hook the evaluation into CI so regressions block releases; expose the latest accuracy score inside `quality_dashboard.html`.

By iteratively tackling each section, the project will gain confidence across reliability, scalability, user experience, and answer correctness.
