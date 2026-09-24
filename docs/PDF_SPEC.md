# StartupValue — Especificação do relatório PDF

Estado: design de informação anterior à implementação. O PDF é um artefato institucional A4 gerado de `SimulationResult`; não é impressão da página e nunca recalcula Monte Carlo.

## Contrato

`ReportData` recebe snapshot da empresa/cenário, SimulationResult imutável, target analysis selecionada, método/base/moeda, template version e textos determinísticos. Todos os números reconciliam com API/dashboard por ID e path de dados. Ausente vira `N/A` com razão; não vira zero.

Metadados em todas as páginas: empresa, scenario, confidencialidade, simulation ID curto, data e página. Cover e methodology mostram IDs completos, model/tax version, seed, n, runtime/report version e result checksum. Download é autenticado ou assinado por prazo curto.

## Estrutura

1. Cover: marca, Valuation & Monte Carlo Analysis, empresa, scenario, data, Confidential.
2. Executive Summary: P50, P25–P75, P10/P90, target probability com hits/N, uncertainty descritiva, top associations e 1–3 parágrafos.
3. Company Overview: perfil, estágio/modelo, data-base, moeda, objetivo e limitações.
4. Financial Assumptions: receita/custos/reinvestment, cash/debt, tax, input origin e warnings.
5. Monte Carlo Distribution: histograma/CDF/box plot, P5–P95, failure/zero mass e erro MC.
6. DCF Analysis: FCFF bridge, discount curve, terminal assumptions, EV→equity reconciliation.
7. Venture Capital Method: exit metric/multiple, horizon/return, exit EV→equity, PV, investment/pre/post/ownership.
8. Financial Projections: revenue/EBITDA/FCFF/margins e breakeven probabilities.
9. Valuation Drivers: Spearman com população/n e aviso de associação; upside/downside conditional summaries.
10. What Needs to Be True: target, hits/miss P25/P50/P75 e narrativa não causal.
11. Risk & Sensitivity: states/tails, uncertainty measures, tornado endpoints e limitations.
12. Methodology: concise DCF/VC/Monte Carlo/percentiles/seed/tax definitions e disclaimer.
13+. Appendix: inputs completos, distribution parameters/correlation, detailed stats, warnings and audit metadata.

## Layout

A4 portrait, margins 16–20 mm, grid 12 columns, white background. Sans local 9.5–10.5 pt body, mono tabular for identifiers/numbers; headings 14–26 pt. Green/blue are darkened for print and accompanied by labels/dash. Charts are SVG or high-resolution raster, captions and alt/accessible text where PDF pipeline supports it. No dark full-page dashboard, button, hover affordance or clipped scroll table.

Tables repeat headers, keep units in column labels, right-align numeric values, preserve negative sign and use locale pt-BR. Avoid breaking a metric block, figure+caption or reconciliation across pages. Long assumption tables move to appendix. Footer does not cover content.

## Narrative rules

Templates consume named fields. Example pattern: “Em N cenários, a mediana de [basis/method] foi X. O intervalo P25–P75 foi A–B. A meta T foi atingida em k/N cenários (p%).” With ties, do not say exactly half below/above. Drivers use “apresentou associação”; target groups use “nos cenários que atingiram”. If n/group is small or empty, state it. No LLM calculation; optional LLM narrative must be checked against allowed facts and fall back to deterministic text.

## Accessibility and security

HTML source has semantic headings, tables, language and reading order. Target tagged PDF/PDF-UA when toolchain reliably supports it; until validated, provide accessible HTML report alongside PDF. Fonts embedded/subsetted; text remains selectable. Metadata excludes internal paths/users. Chromium network is disabled during rendering; content escaped; local assets only.

## Verification

- Contract: every displayed number maps to ReportData/SimulationResult and matches dashboard formatting tolerance.
- Structural: page count, text extraction, headings, tables, IDs, seed/version and no missing glyphs.
- Visual: render every page to PNG; inspect overlap, orphan headings, clipping, chart labels, grayscale and 100% zoom.
- Cases: negative/zero values, long company names, pt-BR accents, empty target group, 25k simulations, warnings/appendix, 12+ pages.
- Security: unauthorized/other tenant/expired signed URL fail; cache headers and filename safe.
- Regression: golden PDF semantic snapshot plus image diff with reviewed tolerance; timestamps/IDs normalized only for test fixture.

Release blocks if PDF recalculates, diverges from dashboard, omits audit IDs, exposes public URL, has clipped/unreadable pages or calls correlation causality.

