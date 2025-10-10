## Configuration & Environment Variable Precedence

The system centralizes configuration in `config.py` and (optionally) a project `.env` file. To avoid ambiguity, the following precedence order applies (highest wins):

1. Explicit environment variables passed to a running process (e.g. `docker compose` service `environment:` entries, or variables exported in your shell)
2. Variables loaded from a local `.env` file (auto‑loaded by `config.py` if present)
3. Internal defaults defined in `config.py`

This design lets Docker Compose / production orchestration inject authoritative values, while local developers can customize behavior without editing compose files. If a value appears “ignored,” verify it is not overridden earlier in the chain.

### Adding / Overriding Variables
1. Copy `.env.example` to `.env`
2. Adjust needed values (e.g. `DB_PASSWORD`, `API_KEY`, model names)
3. Recreate or restart affected containers if using Docker (environment changes are only read on container start)

### Verifying Effective Configuration
From inside the `reranker` container:
```
docker exec -it reranker python config.py | sort
```
This prints the final values after precedence resolution.

### Security Notes
* Never commit your real `.env` file – only `.env.example`
* Rotate `API_KEY` / `JWT_SECRET` in non‑local environments
* Use distinct credentials per environment (dev/stage/prod)

### Common Gotchas
| Symptom | Likely Cause | Resolution |
|---------|--------------|-----------|
| Changed value in `.env` not reflected | Container still using old environment | `docker compose up -d --build` or restart service |
| Script cannot resolve `pgvector` host | Running script on host instead of inside Docker network | Use `docker exec -it reranker ...` |
| Login fails for seeded admin | RBAC seed script not executed (or different email) | Run `make seed-rbac` (added target) |

---

## Frontend Auth API Access (Rewrites vs Direct URL)

The Next.js frontend now proxies all `/api/auth/*` calls to the FastAPI backend (reranker service) using a rewrite configured in `next.config.js`:

```
async rewrites() {
	return [
		{ source: '/api/auth/:path*', destination: 'http://reranker:8008/api/auth/:path*' }
	];
}
```

This allows the React auth layer (`AuthContext`) to issue same‑origin requests (e.g. `fetch('/api/auth/login')`) without hard‑coding backend hostnames and without triggering CORS preflights inside the Docker network.

### Optional Direct Backend URL
If you prefer to bypass the rewrite (e.g. external deployments, split domains, or local testing outside Docker), set:

```
NEXT_PUBLIC_BACKEND_URL=https://your-backend-host:8008
```

When this environment variable is defined, the frontend will prefix all auth calls with that base instead of relying on rewrites. Leave it unset (empty) for the default rewrite-based behavior.

### Health Check Resilience
The `AuthContext` performs a lightweight health probe to `/api/auth/health` on mount. A `404` (endpoint missing) no longer causes a blank screen — it is treated as a soft failure and the UI continues. Only network errors or non‑404 error statuses show an "Auth service unavailable" message.

### Summary
| Scenario | Recommended Setup |
|----------|-------------------|
| Docker local dev (single compose network) | Use built‑in rewrites (leave `NEXT_PUBLIC_BACKEND_URL` unset) |
| Deploy with separate frontend and backend hosts | Set `NEXT_PUBLIC_BACKEND_URL` to the public backend base URL |
| Temporary direct testing vs remote backend | Export `NEXT_PUBLIC_BACKEND_URL` in shell before build/run |

If you add new auth endpoints on the backend under `/api/auth/*`, they are automatically covered by the existing rewrite mapping.

