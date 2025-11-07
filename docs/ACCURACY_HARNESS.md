# Accuracy Evaluation Harness

## Dataset
- Stored at `tests/data/accuracy_dataset.json`.
- Each entry contains an `id`, `question`, and keyword requirements (required/optional/forbidden).
- Expand this file with additional prompts (e.g., metadata extraction, escalation workflows, RBAC checks).

## Runner
- `scripts/testing/accuracy_eval.py` streams responses from `/api/chat`, aggregates keyword hits, and enforces `ACCURACY_THRESHOLD` (default 90%).
- `make eval-accuracy` wrapper sets env defaults and writes JSON logs to `tests/accuracy_logs/`.
- Environment variables:
  - `ACCURACY_BASE_URL` (default `https://rni-llm-01.lab.sensus.net`)
  - `ACCURACY_API_KEY`, `ACCURACY_BEARER_TOKEN`
  - `ACCURACY_THRESHOLD`

## CI Integration
- GitHub workflow `.github/workflows/accuracy.yml` runs nightly / on-demand, executes `make eval-accuracy`, and uploads logs as artifacts.
- Failures (accuracy below threshold) block the workflow and surface in alerting.
