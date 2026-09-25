# StartupValue

StartupValue is being built as a valuation decision-intelligence platform for startups. The target product combines deterministic DCF and Venture Capital Method calculations with reproducible Monte Carlo simulation, sensitivity analysis, target valuation analysis and institutional reporting.

This repository is an active foundation, not a production-ready release. The audit and product specifications are complete enough to guide implementation; core modules, authenticated API flows and the first integrated wizard path are now in place. The production gates in the documentation still apply.

## Repository map

```text
apps/frontend/       Next.js 16, React 19 and TypeScript interface
apps/backend/        FastAPI API, financial engines and persistence foundation
docs/                Product, UX, model, methodology, security and operations specs
infra/caddy/         Development and production reverse-proxy configuration
infra/env/           Environment-file templates without credentials
infra/scripts/       Compose validation, backup and isolated restore drill
legacy/              Preserved V2 HTML prototype
```

The main architectural references are [ARCHITECTURE](docs/ARCHITECTURE.md), [MODEL_AUDIT](docs/MODEL_AUDIT.md), [METHODOLOGY](docs/METHODOLOGY.md), [SECURITY](docs/SECURITY.md), [BENCHMARK](docs/BENCHMARK.md) and [DEPLOY_VPS](docs/DEPLOY_VPS.md).

## Current implementation status

Implemented or under active integration:

- Next.js application shell, premium public landing components and seven-step valuation wizard;
- signup/login/logout with Argon2id password hashing, opaque HttpOnly sessions and `/auth/me`;
- FastAPI application shell with liveness/readiness endpoints and explicit CORS origins for local development;
- workspace-scoped startups, scenarios, immutable scenario revisions, synchronous simulation persistence and idempotent `SimulationResult` creation;
- audited pure-Python valuation, simulation and decision-support modules;
- Alembic migration foundation, including revocable sessions;
- cross-tenant, auth, valuation, simulation, report-contract and API tests;
- local Playwright smoke flow covering signup, wizard submission and persisted simulation success;
- container images for frontend and backend, using non-root runtime users;
- Compose topology for frontend, API, worker, PostgreSQL, authenticated Redis and Caddy;
- private Docker networks: only Caddy publishes host ports;
- production hardening defaults, health checks, named volumes and log rotation;
- Caddy routing, automatic HTTPS in production and baseline security headers;
- local backup staging with checksums and an isolated restore-drill workflow.

Still required before a production launch:

- CSRF protection, rate limiting, password reset delivery, session management UI and deeper authorization policies;
- RLS-backed multi-tenancy, PostgreSQL/Redis integration tests and production database smoke tests;
- background job orchestration, outbox/retry semantics and retained private sample storage;
- complete results experience, target analysis UI, scenario comparison and authenticated dashboard backed by real persisted data;
- audited tax implementation and full decision-intelligence UI;
- PDF visual rendering checks and authenticated report download flow;
- real readiness checks for PostgreSQL, Redis and private storage (the current endpoint reports degraded);
- nonce-based CSP emitted by the application; Caddy intentionally does not add a permissive fallback CSP;
- CI image publication by immutable digest, SBOM and vulnerability/secret scans;
- benchmark evidence, resource-limit tuning, monitoring/alerts and a measured backup restore drill;
- legal review of Privacy, Terms and LGPD workflows;
- staging security review and every release gate described in `docs/`.

Do not present the current application as production-ready or use it for investment decisions.

## Local container setup

Requirements:

- Docker Engine with Docker Compose v2;
- at least 4 GB of free RAM for the complete stack;
- ports 8080 and 8443 available, or alternate values in `.env`;
- for the non-container route, the toolchain versions pinned in
  `.python-version` (Python 3.12) and `.nvmrc` (Node 24).

Create a local environment file and replace every `CHANGE_ME` value. Secrets shown in the template are placeholders and must not be reused in production.

```bash
cp infra/env/development.env.example .env
docker compose --env-file .env config --quiet
docker compose --env-file .env build
docker compose --env-file .env up -d
```

Open `http://localhost:8080`. The internal frontend, backend, PostgreSQL and Redis ports are not published. Inspect them through Caddy or `docker compose exec`.

Useful commands:

```bash
docker compose --env-file .env ps
docker compose --env-file .env logs -f --tail=200 caddy frontend backend worker
docker compose --env-file .env --profile tools run --rm migrate
docker compose --env-file .env down
```

The frontend container runs the optimized standalone server, so this Compose setup is production-like and does not provide source hot reload. Run the application toolchains directly when developing UI or Python code.

```bash
npm ci
npm run dev

cd apps/backend
python -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes --no-deps -r requirements-dev.lock.txt
python -m pip install -e . --no-deps
uvicorn app.main:app --reload
```

On PowerShell, activate the Python environment with `.venv\Scripts\Activate.ps1`. A local backend started outside Compose needs local `DATABASE_URL` and `REDIS_URL` values.

## Dependency locking

Every dependency version is resolved ahead of time and committed, so an
environment built today matches one built months from now.

| File | Scope | Consumed by |
| --- | --- | --- |
| `package-lock.json` | frontend, exact tree | `npm ci`, frontend Dockerfile |
| `apps/backend/uv.lock` | backend, source of truth | `uv`, regeneration only |
| `apps/backend/requirements.lock.txt` | backend runtime, hashed | backend Dockerfile |
| `apps/backend/requirements-dev.lock.txt` | backend runtime and dev, hashed | local development, CI |
| `.python-version` | Python 3.12 | `uv`, `pyenv` |
| `.nvmrc` | Node 24 | `nvm` |

The two `requirements*.lock.txt` files are plain pip input carrying `--hash`
entries, so installing from them needs no extra tool:

```bash
python -m pip install --require-hashes --no-deps -r apps/backend/requirements-dev.lock.txt
```

They are resolved universally across every supported interpreter (3.11 to 3.13)
and every target platform, so one file covers both Linux containers and Windows
development machines. Platform-specific dependencies carry environment markers
and are skipped where they do not apply: `uvloop` installs on Linux, `colorama`
on Windows.

The backend image installs from `requirements.lock.txt` instead of resolving
`pyproject.toml` at build time, which is what makes image builds reproducible.

Regenerate after any change to `apps/backend/pyproject.toml`:

```bash
cd apps/backend
uv lock
uv export --no-emit-project --no-dev --format requirements-txt -o requirements.lock.txt
uv export --no-emit-project --extra dev --format requirements-txt -o requirements-dev.lock.txt
```

`uv` is needed only to regenerate the lock, never to install from it.

## Runtime topology

```text
Internet -> Caddy :80/:443 -> Next.js
                    |
                    +------> FastAPI (/api/* and /health/*)

FastAPI/worker -> PostgreSQL + Redis + private_data volume
```

PostgreSQL and Redis are attached only to the internal `data` network. Frontend/backend communication uses internal Docker networks. Reports and simulation samples live in `private_data`; Caddy never serves that volume directly. Authenticated application endpoints must authorize every report download.

The `worker` listens to the `simulation`, `report` and `maintenance` RQ queues. The `migrate` service is behind the `tools` profile and runs only when explicitly invoked.

## Production deployment

Follow [DEPLOY_VPS](docs/DEPLOY_VPS.md) for host hardening, DNS, firewall, release, rollback and monitoring. A minimum deployment sequence is:

1. Copy `infra/env/production.env.example` to `/opt/startupvalue/secrets/production.env`, set mode `600`, and replace every placeholder.
2. Set `FRONTEND_IMAGE` and `BACKEND_IMAGE` to CI-produced immutable tags or digests. Never deploy `latest`.
3. Point the domain A/AAAA records to the VPS and allow only restricted SSH plus ports 80/443.
4. Validate the merged Compose model before starting services.
5. Start PostgreSQL and Redis, run the one-shot migration, then start the application and Caddy.
6. Verify HTTPS, headers, health, authenticated smoke tests, logs and a backup/restore drill before opening traffic.

```bash
export ENV_FILE=/opt/startupvalue/secrets/production.env
docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.prod.yml config --quiet
docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.prod.yml up -d postgres redis
docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.prod.yml --profile tools run --rm migrate
docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.prod.yml up -d
```

The production Caddyfile enables HSTS. Use it only after DNS and HTTPS are confirmed for the real domain. The infrastructure does not promise zero downtime on a single VPS. Database changes must follow expand/migrate/contract so application rollback remains possible.

Resource limits are conservative starting values, not measured capacity claims. Tune them only after running the simulation and PDF benchmarks on the chosen VPS.

## Environment and secrets

Compose requires database, Redis, session and CSRF secrets. Generate independent random values of at least 32 bytes. Keep the production file outside the repository, readable only by the deployment operator. No credential belongs in `NEXT_PUBLIC_*`, Docker images, command output or source control.

`DOMAIN` must be the real public hostname in production. `MODEL_VERSION` and `TAX_VERSION` are audit identifiers and must change under the versioning rules in the methodology. `SENTRY_DSN` is optional; leaving it blank keeps the integration disabled.

The Compose files currently pass secrets through container environment variables. A later deployment hardening step may move supported credentials to Docker secrets without changing application contracts.

## Backups and restore drills

`infra/scripts/backup.sh` creates a restricted local staging directory containing:

- a custom-format PostgreSQL dump;
- the private reports/samples archive;
- SHA-256 checksums and a small manifest.

It does not encrypt or upload the backup because the offsite provider has not been selected. A production operator must encrypt the completed directory, copy it to independently controlled offsite storage and verify the remote checksum. Redis is intentionally excluded because it is not a source of truth.

```bash
sudo ENV_FILE=/opt/startupvalue/secrets/production.env \
  BACKUP_ROOT=/opt/startupvalue/backups \
  RETENTION_DAYS=14 \
  ./infra/scripts/backup.sh
```

`infra/scripts/restore-drill.sh` validates the manifest and restores into a newly named database plus a separate artifact directory. It refuses to overwrite an existing database and never replaces the active private-data volume.

```bash
sudo ENV_FILE=/opt/startupvalue/secrets/production.env \
  ./infra/scripts/restore-drill.sh /opt/startupvalue/backups/20260922T120000Z
```

After restoration, verify table counts, foreign keys, result hashes and an authenticated smoke flow. Record measured RPO/RTO. Production cutover remains a deliberate operator procedure; the drill script does not automate destructive replacement.

## Security notes

- Caddy is the only public container. Do not publish database, Redis, backend or report-volume ports.
- Redis requires a password even in local Compose. PostgreSQL and application secrets have no committed default.
- Containers use `no-new-privileges`; application containers drop Linux capabilities and run as non-root.
- Access logs, application logs and error monitoring must redact cookies, tokens, financial payloads and signed URLs.
- Security headers at the proxy are a baseline. Session security, CSRF, nonce-based CSP, authorization and rate limits belong in the application and remain release gates.
- A passing container health check proves process availability, not mathematical correctness, tenant isolation or production readiness.

Report suspected vulnerabilities privately to the project owner; do not include customer data or credentials in an issue.

## Validation

When Docker is available, validate both configurations with:

```bash
cp infra/env/development.env.example .env
./infra/scripts/validate-compose.sh .env infra/env/production.env.example
```

Application validation is defined in [TEST_PLAN](docs/TEST_PLAN.md). At minimum, a release needs unit and property tests for the engines, real PostgreSQL/Redis integration tests, reproducibility tests, cross-tenant security tests, PDF contract/visual checks and the complete Playwright E2E journey.

## Legacy source

The original prototype is preserved at `legacy/startupvalue_dashboard_v2.html`. It is audit evidence, not the source of truth for formulas or UI behavior. Corrections and compatibility decisions are recorded in [MODEL_AUDIT](docs/MODEL_AUDIT.md).
