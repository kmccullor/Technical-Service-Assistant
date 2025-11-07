# Performance UX Testing

This document captures the plan for frontend performance monitoring using Playwright (and future Lighthouse coverage).

## Playwright Performance Smoke
- Config: `next-rag-app/playwright.config.ts` with serial tests under `tests/performance/`.
- Environment variables:
  - `PLAYWRIGHT_BASE_URL` (default `https://rni-llm-01.lab.sensus.net`)
  - `PLAYWRIGHT_API_KEY` / `PLAYWRIGHT_BEARER_TOKEN` for authenticated API calls.
- `npx playwright test --config=playwright.config.ts` produces `playwright-report/` with HTML + JSON metrics.
- GitHub Actions workflow (`.github/workflows/playwright.yml`) runs on schedule and upload reports.

## Backend Metrics Hook (future work)
- Emit request latency histograms (p95) from reranker and expose via Prometheus.
- Capture those metrics alongside the Playwright run for a single, unified report.

## Lighthouse Integration (future work)
- Add a `make lighthouse` target using Chrome’s Lighthouse CLI against deployed frontend.
- Include results in CI artifacts and highlight regressions.
