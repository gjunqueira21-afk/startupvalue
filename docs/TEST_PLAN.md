# StartupValue — Plano de testes e release gates

## Estratégia

Testes seguem risco: motores puros recebem cobertura numérica/propriedades; API/persistência usa Postgres/Redis reais; E2E cobre jornadas; segurança tenta cruzar tenants; PDF e responsive têm inspeção visual. Mock é usado apenas em fronteiras externas. Fixture produzida pelo código sob teste não serve como oracle independente.

## Unitários financeiros

- Monthly/annual conversion and calendar; accumulated variable discount factors.
- FCFF reconciliation; EV→equity; terminal month61 and `g<WACC` validation.
- VC annual metric, exit bridge, PV `(1+r)^H`, pre/post/investment/ownership and future dilution.
- Tax policy selection/effective dates/rounding with official golden examples.
- Missing/non-finite/support errors; currency/unit types prevent accidental mixing.

Golden cases in `MODEL_AUDIT.md` are implemented with absolute/relative tolerances justified by float64 and monetary presentation. Compare key cases to hand/spreadsheet independent calculation.

Property tests: with nonnegative flows and fixed terminal, larger WACC cannot increase PV; larger sustainable flow cannot reduce DCF; `g>=WACC` invalid; pre+investment=post; ownership=investment/post; percentiles ordered; no hidden filtering. Do not assert WACC monotonicity for arbitrary signed flows.

## Monte Carlo/statistics

- Same canonical input/model/runtime/seed/n yields same sample arrays and hashes.
- Distribution moments/quantiles/support for constant, normal truncated, t, triangular, uniform and lognormal within predeclared statistical tolerance.
- No clipping mass; failure 0/1; state counts sum N; values signed/zero retained.
- Persistence/correlation approximate theoretical behavior; invalid correlation rejected.
- P5/10/25/50/75/90/95 convention, constant array and tails; histogram counts sum N; CDF monotonic/endpoints.
- Breakeven discrete CDF and non-achievement; conditional metrics labeled.
- Spearman perfect/constant/ties; target all/none/equality; Wilson limits.
- 1k/5k/10k/25k benchmark records duration/RAM/hardware/image; it is performance evidence, not model validity.

## API/integration

Real services via Compose/testcontainers: migrations from empty and previous release, repositories, transactions/outbox, idempotency, retries, worker crash/recovery, immutable result/report, checksum/storage, target reuse without new RNG, report source contract, quotas and pagination. OpenAPI client contract fails on incompatible schema drift.

Health live/ready behavior is tested for DB/Redis/storage outage. Logs are captured and scanned for secret/financial canaries. Time and email adapters are deterministic in tests.

## Security

For every tenant resource/action, create workspace A/B and assert A cannot list/read/mutate/delete/duplicate/run/download B. Test parent-child ID swaps and background jobs. Run same suite with RLS active and recycled pooled connections.

Auth: Argon2 hash/rehash, login/reset enumeration, token expiry/reuse, fixation/rotation/logout/revoke, cookie flags, CSRF/origin, role transitions, last owner, rate limit/concurrency. App: injection, XSS/CSP, mass assignment, oversized body, SSRF renderer, path traversal, signed URL swap/expiry. Scan dependencies/images/IaC/secrets.

## E2E

Playwright desktop and mobile:

1. landing methods/pricing/methodology and reduced motion fallback;
2. signup/login/logout/forgot/reset;
3. create company, autosave wizard simple, switch professional, validation/review;
4. run job, reload during progress, complete, result IDs/percentiles;
5. set target, drivers/sensitivity, duplicate/compare scenarios;
6. generate/download PDF, logout/login, recover same result;
7. archive/delete/export account data and error states.

Use deterministic seed/fixture worker. E2E does not wait arbitrary sleeps; poll observable states. Accessibility: axe plus keyboard/screen-reader manual checks. Responsive: 390×844, 768×1024, 1440×900 with no global overflow/overlap.

## PDF

Contract, extraction, all-page render inspection, semantic structure, long/negative/empty cases, grayscale and authenticated access per `PDF_SPEC.md`. Dashboard and PDF compare raw values/metadata from same result. PDF job failure/retry must not create new simulation.

## Infrastructure and recovery

CI builds clean images and starts dev/prod Compose profiles; health, migration, smoke and graceful shutdown. Test backup script, checksum/encryption and isolated restore including artifacts/result hashes. Staging rehearses deploy and rollback across compatible migration. Chaos checks stop worker/Redis/Postgres and verify honest states/no result corruption.

## Release gates

Block release on:

- any Critical/High security or cross-tenant failure;
- failing golden/property/reproducibility test;
- result/PDF mismatch or Monte Carlo recalculation in report;
- missing seed/model/tax/input/result metadata;
- migration/backup/restore/rollback without evidence;
- E2E core flow failure, WCAG critical issue or target viewport defect;
- benchmark exceeding chosen capacity without entitlement/queue safeguards;
- secrets or sensitive values in repository/logs.

Coverage percentage is diagnostic, not release proof. Flaky core test is treated as failure and fixed, not retried until green.

