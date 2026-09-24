# StartupValue — Síntese da auditoria e plano de migração

Data: 2026-09-22. A auditoria foi feita antes de qualquer alteração da aplicação. Originais, hashes, extração integral e probes estão em `audit/SOURCE_MANIFEST.md` e `audit/evidence/`.

## CURRENT SYSTEM

Um HTML local de 1.666 linhas contém UI, estado, fórmulas, Monte Carlo, charts e export TXT. Cinco valores mensais médios por categoria são repetidos por 12 meses. O navegador calcula proxy de EBITDA menos imposto, DCF mensal e VC, sorteia receitas com `Math.random`, guarda estado em memória, filtra valuations não positivos e mostra três steps. O manual V2 de 324 parágrafos explica esse fluxo e faz recomendações comerciais/financeiras.

Não existiam backend, banco, autenticação, multi-tenancy, seed, model version persistida, jobs, PDF, testes, Docker, deploy, backup ou healthcheck.

## ISSUES FOUND

### Bloqueadores matemáticos e estatísticos

- VC usa EBITDA do último mês como se anual e divide por `(1+r)^5−1`; PV de saída correto usa métrica anual e `(1+r)^H`.
- Simples retorna valor mensal e callers dividem por 12 outra vez; caso determinístico usa EBITDA anual parcial.
- WACC variável é aplicado retroativamente, sem fatores acumulados; terminal é descontado no mês 59, sem fluxo do mês 61.
- `g>=WACC` vira terminal zero silencioso.
- Aporte `pre×ownership` não entrega ownership solicitado; EV/equity e pre/post-money são confundidos.
- Proxy de fluxo omite COGS/reinvestimento/CAPEX/D&A/NWC; dívida/caixa não reconciliam equity.
- Failures, zeros e negativos são removidos dos percentis/gráficos, criando selection bias.
- Receita mensal é sorteada independentemente; sigma é 35% da média global, não CoV por mês; triangular tem modo no máximo e média +16,67%; clipping cria massa zero.
- Sem seed/version/runtime; resultado não é reproduzível. Breakeven input não participa da métrica e mediana exclui não atingidos.
- Linha chamada densidade é histograma ligado; array constante divide por zero.

### Produto e UX

- Formulário extenso abre sem landing/auth/dashboard e permite etapas fora de ordem.
- “Projeção anual” recebe média mensal; percentuais usam decimal+sufixo `x`; defaults parecem benchmarks.
- Modo simples/profissional, revisão, autosave, errors/empty states e persistência não existem.
- Manual chama P25 de piso, DCF conservador/VC otimista e mais draws de “alta precisão”; afirmações não são propriedades gerais.
- “Otimizar regime” não é implementado e anexos ausentes caem no III.
- Mobile mantém steps além de 390 px e fluxo >3.500 px; emoji é iconografia final; charts não têm alternativa.
- Resultado não informa método/base/população e TXT não é relatório auditável.

### SaaS, segurança e operação

- Sem isolamento tenant/authorization; qualquer futura API ingênua criaria IDOR.
- Sem proteção de sessão/reset/CSRF/rate limiting, report/sample access ou LGPD workflows.
- Sem jobs idempotentes/outbox, result source of truth, logs redigidos ou audit trail.
- Sem containers, TLS, migrations, health/readiness, backups/restores, rollback ou monitoring.

## PROPOSED SYSTEM

Plataforma SaaS de decisão com landing→auth→dashboard→wizard→job→resultado→target/PDF. Simple e Professional usam o mesmo input canônico. Cenários têm revisions imutáveis; cada simulation fixa input hash, model/tax/runtime versions, seed e count. `SimulationResult` guarda distribuição completa e referência a samples privados; dashboard, target e PDF leem esse artefato.

Monólito modular: Next.js/TypeScript, FastAPI/Python, engines puros NumPy/SciPy, PostgreSQL/SQLAlchemy/Alembic, Redis/RQ, Playwright PDF e Caddy em Docker Compose. Sessão opaca HttpOnly, Argon2id, CSRF, authorization workspace-first e RLS defense-in-depth. Jobs usam outbox/idempotency. Caddy é único ingresso; Postgres/artifacts têm backup offsite e restore drill.

Motor `3.0.0`: FCFF reconciliado; DCF mensal acumulado e terminal sustentável; EV→equity; VC anual e round math; failure econômico preservado; PCG64 e trajetórias persistentes; percentis completos; breakeven incondicional; Spearman, tornado e target hit/miss separados. Tax é inicialmente `simplified_estimate` versionado por vigência, sem “otimização”.

## MIGRATION PLAN

| Gate | Entrega | Prova necessária |
|---|---|---|
| 0 Audit | originais/hashes, specs e metodologia | documentos completos e probes reproduzidos |
| 1 Foundation | monorepo, Compose, CI, contracts, legacy preservado | lint/build/smoke limpo |
| 2 Engines | valuation, simulation, statistics, decision, tax proxy | golden/property/seed tests e benchmark |
| 3 SaaS core | DB/migrations, auth, tenancy, scenarios, jobs/results | integration e cross-tenant suite |
| 4 Frontend | landing, auth, dashboard, wizard, results | E2E/reload/session/mobile/a11y |
| 5 Intelligence | target, drivers, tornado, compare, narratives | artifact/denominator/wording tests |
| 6 Reporting | A4 PDF da mesma fonte e private download | dashboard/PDF contract + render QA |
| 7 Operations | prod Compose, Caddy, backup/restore, monitoring | staging deploy/rollback/restore evidence |
| 8 Go-live | security/numeric/UX/operational gates | no Critical/High blocker |

Resultados antigos podem ser importados apenas como `legacy_unverified`. Inputs do legado recebem frequência/unidade explícita. Nunca relabelar saída antiga como model 3.0.0 nem prometer compatibilidade onde houve correção.

## Pareceres

- Produto: `PRODUCT_SPEC.md`
- UX: `UX_SPEC.md`; UI: `DESIGN_SYSTEM.md`; 3D: `audit/04_CREATIVE_3D.md`
- Matemática: `MODEL_AUDIT.md`; Estatística/sensibilidade: `METHODOLOGY.md`, `audit/07_STATISTICS.md`, `audit/10_SENSITIVITY.md`
- VC/tax: `audit/08_VC_INPUTS.md`, `audit/09_TAX_BRAZIL.md`
- Arquitetura: `ARCHITECTURE.md`; Segurança: `SECURITY.md`; Deploy: `DEPLOY_VPS.md`
- PDF/QA: `PDF_SPEC.md`, `TEST_PLAN.md`

