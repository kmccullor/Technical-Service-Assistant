# Technical Service Assistant

Production-ready retrieval-augmented generation platform that combines a FastAPI backend (`reranker`), document ingestion workers (`pdf_processor`), and a Next.js frontend (`next-rag-app`). The system orchestrates local Ollama models, Postgres + pgvector storage, and rich monitoring to deliver enterprise-style knowledge assistant workflows.

### Quick Start
```bash
make install         # bootstrap Python & Node deps (requires .venv)
cp .env.example .env # configure environment variables
make up              # launch Postgres, Ollama, reranker, pdf pipeline, frontend
```
- Optional: `make seed-rbac` to load default users and roles after first boot.
- Bring the stack down with `make down`. Use `make health-check` to verify containers.

### Core Services
- `reranker/` – FastAPI APIs, embeddings, reranking, auth endpoints.
- `pdf_processor/` – ingestion workers for PDFs (text/table/image extraction).
- `redis-cache` – lightweight cache + instrumentation store (enable via `REDIS_URL`; chat metrics land under `tsa:chat:*`).
- `next-rag-app/` – Next.js UI for querying, auth flows, and monitoring dashboards.
- `utils/` – shared helpers (chunking, retrieval, RBAC middleware).
- `scripts/` – operational tooling (checks, benchmarking, automation).

### Essential Commands
- `make test` / `make test-all` – pytest ring runner with coverage gates (95% target).
- `pre-commit run --all-files` – formatting, linting, type checking, security scans.
- `pytest --cov --cov-fail-under=95` – manual coverage verification.
- `make quality-report` – refresh QA dashboards (`quality_dashboard.html`).
- `make check-db` – verify ingestion data; `make health-check` – container status.
- `make smoke-test` – run the automated service smoke test (verifies API health, Ollama, Redis, Postgres, Grafana/Prometheus, and nginx).
  - CI: GitHub Actions (`quality.yml`) has a `smoke-test` job that runs this target on the self-hosted runner after unit/integration suites succeed, ensuring live services stay healthy.
  - The smoke test auto-loads `.env`, so it works out-of-the-box when run from the repo root (set `SMOKE_DB_HOST` only if you need to override the Compose host).
- `python scripts/collect_service_logs.py [tail_lines]` – grab recent Docker logs for reranker/frontend/pgvector/redis/nginx into `logs/smoke/<timestamp>/`; useful when smoke/load tests fail.
- `make load-test` – execute the K6-based load harness (`scripts/testing/load_test.py`). Auto-falls back to the official `grafana/k6` Docker image if a native `k6` binary is not found. Summaries + optional Prometheus snapshots land under `load_test_results/`; run `python scripts/testing/load_test_report.py` to enforce thresholds locally. Pass `--timeout-profile load_test_results/model_latency_profile_*.json` to reuse measured scenario latencies as the per-request timeout budget.
- `python scripts/testing/model_latency_profile.py --samples 3` – run targeted probes (simple chat, deep thinking, reasoning, code, vision) to capture response-time distributions and recommend safe timeout values for load tests. The script writes `model_latency_profile_<timestamp>.json`; feed that file to the load harness via `--timeout-profile` before kicking off `make load-test`.
- Load harness prompts for `X-API-Key`/JWT at runtime when env vars aren’t set; you can also pre-set `LOAD_TEST_USERNAME`/`LOAD_TEST_PASSWORD` and it will hit `/api/auth/login` automatically (`--insecure-login` skips TLS verification for self-signed certs). The script retries once without TLS verification if the server presents a self-signed cert, so manual fiddling with `REQUESTS_CA_BUNDLE` is optional.
- Set `LOAD_TEST_DOC_ENDPOINT=/api/documents` (or pass `--doc-endpoint`) if you want the load test to exercise document uploads; uploads are skipped by default to avoid 404s on deployments that don’t expose that route.
- `python scripts/auth/get_load_test_token.py` – helper to hit `/api/auth/login` using `LOAD_TEST_USERNAME`/`LOAD_TEST_PASSWORD` env vars and print `export LOAD_TEST_BEARER_TOKEN=…`. Set `LOAD_TEST_VERIFY_TLS=false` if you need to skip TLS validation for self-signed certs.
- `python scripts/reporting/nightly_summary.py` – generate a Markdown summary (`reports/nightly_summary_*.md`) that combines the most recent load-test and accuracy evaluations.
- `make eval-accuracy` – run the accuracy harness (`scripts/testing/accuracy_eval.py`) against the curated dataset in `tests/data/accuracy_dataset.json`. Set `ACCURACY_API_KEY`/`ACCURACY_BEARER_TOKEN` as needed; results land in `tests/accuracy_logs/`.

### Repository Map
- Documentation: `docs/` (see [docs/README.md](docs/README.md) for an index).
- Migrations: `migrations/`, SQL seeds in `init.sql`, schema reference in `vector_database_schema.sql`.
- Tests: `tests/` organized by ring with orchestration via `test_runner.py`.
- Deployment: `docker-compose*.yml`, `deployment/`, and `docker-compose.production.yml`.
- Reference guides: `ARCHITECTURE.md`, `DEVELOPMENT.md`, `CODE_QUALITY.md`, `SECURITY.md`.

### Development Workflow
1. Activate the virtualenv: `source .venv/bin/activate`.
2. Start services (`make up`) or run focused backends with `uvicorn reranker.app:app --reload`.
3. Use `npm --prefix next-rag-app run dev` for local frontend development.
4. Validate changes with `make test` and `pre-commit run --all-files` before committing.
5. Review coverage under `htmlcov/` and dashboards in `quality_dashboard.html`.

### Testing Rings
- Ring 1 (`tests/unit/`): fast unit coverage; run via `test_runner.py --ring 1`.
- Ring 2 (`tests/integration/`): live Postgres + pgvector; `make test` defaults here.
- Ring 3 (`tests/e2e/`): full pipeline validation; trigger with `make test-all` or `test_runner.py --all --performance`.

### Documentation Highlights
- High-level architecture: `ARCHITECTURE.md`
- Developer workflows: `DEVELOPMENT.md`
- Ops & troubleshooting: `TROUBLESHOOTING.md`, `docs/server_documentation.md`
- Deployment guidance: `docs/REMOTE_DEPLOYMENT.md`
- Monitoring and quality: `docs/ADVANCED_MONITORING.md`, `quality_dashboard.html`
- Testing roadmap: `docs/TESTING_EXPANSION.md`
- Performance UX plan: `docs/PERFORMANCE_UX.md`
- Accuracy harness: `docs/ACCURACY_HARNESS.md`

## Configuration & Environment Variable Precedence

Configuration is centralized in `config.py` with optional `.env` overrides. Precedence (highest wins):

1. Environment variables injected at runtime (Docker Compose `environment:`, exported shell vars).
2. Variables loaded from a local `.env` file (auto-read by `config.py` when present).
3. Internal defaults defined in `config.py`.

If a value appears ignored, verify whether a higher-precedence source overrides it.

### Adding or Adjusting Variables
1. Copy `.env.example` to `.env`.
2. Modify the values you need (`DB_PASSWORD`, `API_KEY`, model names, feature flags).
3. Restart affected containers (`docker compose up -d --build` or service restart) so changes take effect.

### Verifying Active Configuration
Run inside the `reranker` container:
```bash
docker exec -it reranker python config.py | sort
```
This prints final values after precedence resolution.

### Security Notes
- Never commit real `.env` files; only update `.env.example` when adding keys.
- Rotate `API_KEY` and `JWT_SECRET` outside local development.
- Use distinct credentials per environment (dev/stage/prod).

### Common Gotchas
| Symptom | Likely Cause | Resolution |
|---------|--------------|-----------|
| `.env` change not reflected | Containers still running old environment | `docker compose up -d --build` or restart service |
| Script cannot resolve `pgvector` host | Script executed on host network | `docker exec -it reranker ...` |
| Seeded admin login fails | RBAC seed not applied or email mismatch | `make seed-rbac` |

## Email Delivery (Postfix Integration)

Password reset and registration flows use SMTP via the `reranker` service. When Postfix is installed on the Docker host, the stack can relay mail through it without exposing an external provider.

- `docker-compose.yml` maps `host.docker.internal` to the host gateway so containers can reach Postfix on port 25.
- `.env` defaults set `SMTP_HOST=host.docker.internal`, `SMTP_PORT=25`, and `SMTP_USE_TLS=false`. Adjust these if your Postfix instance requires TLS or a submission port.
- Update sender domains (`VERIFICATION_EMAIL_SENDER`, `PASSWORD_RESET_EMAIL_SENDER`) to match the From address Postfix is configured to relay.

After updating `.env`, restart the stack:
```bash
docker compose up -d reranker
```
Then verify delivery end-to-end:
```bash
docker compose exec reranker python - <<'PY'
import smtplib
from email.message import EmailMessage
msg = EmailMessage()
msg["From"] = "no-reply@your-domain"
msg["To"] = "test-recipient@your-domain"
msg["Subject"] = "SMTP connectivity check"
msg.set_content("If you received this, Postfix relay from Docker is working.")
with smtplib.SMTP("host.docker.internal", 25, timeout=10) as server:
    server.send_message(msg)
print("Sent test email")
PY
```
Monitor `/var/log/mail.log` (or equivalent) on the host to confirm Postfix accepted the message.

## Frontend Auth Routing

The Next.js app rewrites `/api/auth/*` requests to the FastAPI backend (`reranker`) via `next.config.js`:

```javascript
async rewrites() {
  return [
    { source: '/api/auth/:path*', destination: 'http://reranker:8008/api/auth/:path*' }
  ];
}
```

Auth flows call `fetch('/api/auth/login')` without cross-origin issues while running in Docker.

### Optional Direct Backend URL
Set `NEXT_PUBLIC_BACKEND_URL=https://your-backend-host:8008` to bypass rewrites when the frontend and backend live on different hosts. Leave it unset for default same-origin behavior.

### Health Probe Behavior
`AuthContext` performs a health check against `/api/auth/health` on mount. A `404` is considered a soft failure (UI stays responsive); network errors or non-404 responses show "Auth service unavailable."

### Recommended Setups
| Scenario | Recommended Configuration |
|----------|---------------------------|
| Docker local development | Use built-in rewrites (leave `NEXT_PUBLIC_BACKEND_URL` unset) |
| Separate frontend / backend hosts | Set `NEXT_PUBLIC_BACKEND_URL` to the backend base URL |
| Temporary remote backend testing | Export `NEXT_PUBLIC_BACKEND_URL` before build/run |

New backend endpoints under `/api/auth/*` are automatically covered by the rewrite.

## Conversation Management & Retention

- **Per-user isolation:** The `/api/conversations` endpoints scope all reads, writes, and deletes to the authenticated user, preventing cross-user history access.
- **Retention guardrails:** Listings are capped at the 30 most recent conversations with activity inside the last 30 days, keeping the sidebar focused on active work.
- **Safe deletion:** Removing a conversation now also clears related analytics (such as `question_usage`) and returns HTTP 204 so the UI can refresh without parsing a payload.
- **Frontend alignment:** The Next.js sidebar calls the API with `?limit=30`, reflects the same 30-day window, and relies on the 204 status to trigger its refresh.
