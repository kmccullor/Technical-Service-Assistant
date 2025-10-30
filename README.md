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
- `next-rag-app/` – Next.js UI for querying, auth flows, and monitoring dashboards.
- `utils/` – shared helpers (chunking, retrieval, RBAC middleware).
- `scripts/` – operational tooling (checks, benchmarking, automation).

### Essential Commands
- `make test` / `make test-all` – pytest ring runner with coverage gates (95% target).
- `pre-commit run --all-files` – formatting, linting, type checking, security scans.
- `pytest --cov --cov-fail-under=95` – manual coverage verification.
- `make quality-report` – refresh QA dashboards (`quality_dashboard.html`).
- `make check-db` – verify ingestion data; `make health-check` – container status.

### Repository Map
- Documentation: `docs/` (see [docs/README.md](docs/README.md) for an index).
- Migrations: `migrations/`, SQL seeds in `init.sql`, schema reference in `vector_database_schema.sql`.
- Tests: `tests/` organized by ring with orchestration via `test_runner.py`.
- Deployment: `docker-compose*.yml`, `deployment/`, and `docker-compose.production.yml`.
- Reference guides: `ARCHITECTURE.md`, `DEVELOPMENT.md`, `CODE_QUALITY.md`, `SECURITY.md`.

### Development Workflow
1. Activate the virtualenv: `source .venv/bin/activate`.
2. Start services (`make up`) or run focused backends with `uvicorn reranker.main:app --reload`.
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
