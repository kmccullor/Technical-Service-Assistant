# Remote Deployment Configuration

This project originally assumed a localhost development environment. For remote or server-based deployments, all operational scripts and health checks now support environment-variable overrides so you can avoid hard‑coded `localhost` references.

## Key Environment Variables

Set these in your shell profile, systemd unit, Docker Compose overrides, or CI pipeline before invoking scripts:

| Variable | Purpose | Default (if unset) |
|----------|---------|--------------------|
| `RERANKER_URL` | Base URL for API / reranker service | `http://localhost:8008` |
| `FRONTEND_URL` | Base URL for web UI | `http://localhost:8080` |
| `SEARXNG_URL` | Base URL for SearXNG search | `http://localhost:8888` |
| `OLLAMA_PRIMARY_URL` | Primary Ollama instance (used in install script) | `http://localhost:11434` |
| `OLLAMA_HOST` | Host used to probe all Ollama ports (end_of_day.sh) | `http://localhost` |
| `OLLAMA1_URL` .. `OLLAMA4_URL` | Individual Ollama instances (daily checklist) | `http://localhost:1143X` |

Example export block:

```bash
export RERANKER_URL="https://tsa.example.com"
export FRONTEND_URL="https://tsa.example.com"
export SEARXNG_URL="https://search.tsa.example.com"
export OLLAMA_PRIMARY_URL="http://tsa-internal:11434"
```

## Updated Scripts (Environment-Aware)

The following scripts / files were updated to respect these variables:

* `reranker/healthcheck.sh`
* `scripts/test_fast_reasoning.py`
* `scripts/monitoring_dashboard.py`
* `scripts/analysis/enhanced_retrieval.py`
* `scripts/analysis/multistage_reranker.py`
* `scripts/testing/test_system_validation.py`
* `scripts/monitor_specialization.py`
* `scripts/install.py`
* `scripts/daily_morning_checklist.sh`
* `scripts/advanced_health_check.sh`
* `scripts/end_of_day.sh`
* `Makefile.daily` (health-check target)
* `test_frontend.html` (dynamic API base inference)

## Usage Patterns

1. One-off execution:
   ```bash
   RERANKER_URL=https://tsa.example.com python scripts/test_fast_reasoning.py
   ```
2. Persistent shell session:
   ```bash
   echo 'export RERANKER_URL=https://tsa.example.com' >> ~/.bashrc
   ```
3. Docker Compose override (`docker-compose.override.yml`):
   ```yaml
   services:
     reranker:
       environment:
         - API_HOST=0.0.0.0
     pdf_processor:
       environment:
         - RERANKER_URL=https://tsa.example.com
   ```

## Frontend Considerations

The production Next.js frontend should call relative paths (`/api/...`) through its reverse proxy / ingress. The demo `test_frontend.html` now infers the host automatically, but you may also set `window.RERANKER_URL` globally before loading the script:

```html
<script>window.RERANKER_URL = 'https://tsa.example.com';</script>
<script src="/test_frontend.js"></script>
```

## Verifying Remote Configuration

Run after exporting variables:
```bash
grep -R "http://localhost:8008" -n --exclude-dir='.next' . | grep -v docs || echo "No hardcoded localhost API references outside docs."
```

Expect either zero matches or references only inside historical documentation files.

## Future Hardening

* Add CI check to fail if new code introduces `http://localhost:8008` literals outside `docs/`.
* Provide a small helper in `utils/` for consistent base URL retrieval.
* Extend environment parameterization to ports for advanced multi-tenant setups.

---
Last updated: $(date +%Y-%m-%d)
