# Performance UX Testing

## Playwright Performance Smoke
- Config: `next-rag-app/playwright.config.ts` with serial tests under `tests/performance/`.
- Environment variables:
  - `PLAYWRIGHT_BASE_URL` (default `https://rni-llm-01.lab.sensus.net`)
  - `PLAYWRIGHT_API_KEY` / `PLAYWRIGHT_BEARER_TOKEN`
- Execution options:
  1. `cd next-rag-app && npx playwright test --config=playwright.config.ts`
  2. `./scripts/testing/run_playwright_docker.sh` (builds/runs inside Playwright’s official Docker image, ensuring dependencies are available).
- GitHub workflow `.github/workflows/playwright.yml` runs nightly / on-demand; upload artifacts include the HTML report.

## Lighthouse Snapshot (CLI)
- Config: `next-rag-app/tests/performance/lighthouse.config.cjs`.
- Command: `./scripts/testing/run_lighthouse.sh` (uses node:18 container, runs `lhci autorun`, writes reports to `next-rag-app/lighthouse-report`).

## Backend Metrics Hook (future work)
- Emit latency histograms from reranker endpoints and surface them in Prometheus.
- Capture those metrics alongside the Playwright run for correlation.
