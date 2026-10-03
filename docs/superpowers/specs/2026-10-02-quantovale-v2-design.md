# QuantoVale V2 — Spec de design

Data: 2026-10-02 · Status: aprovado em conversa (design) · Autor: brainstorm com o dono do produto

## 1. Objetivo

Evoluir o QuantoVale de fundação auditada para produto lançável, mantendo a metodologia
(DCF + VC Method + Monte Carlo) intacta. Quatro frentes:

1. duas métricas complementares derivadas dos cenários existentes;
2. relatório white label para os planos profissionais;
3. estrutura comercial publicada (4 planos com preço real) + lista de espera, sem checkout;
4. landing redesenhada com intro 3D coreografada de ~7 segundos, e preparação completa
   do deploy em VPS Hostinger parametrizado por domínio.

Público: donos de empresa (uso próprio) e consultores/contadores/assessores de
investimento (usam o relatório como entrega de serviço — por isso white label).

Restrições herdadas que continuam valendo: nenhuma fórmula do motor auditado muda
(`MODEL_AUDIT.md`), limites aplicados no backend (P14), transparência de premissas/seed
em todos os planos, nenhuma assinatura fictícia, disclaimers metodológicos sempre
presentes no PDF.

## 2. Métricas complementares (decisão: itens 1 e 2 apenas)

Ambas são leituras derivadas dos cenários Monte Carlo já persistidos
(`SimulationSamples`). Nada é recalculado no motor; nenhuma versão de fórmula muda.
O schema do relatório (`apps/backend/app/reports/schema.py`) ganha seções novas e tem a
versão de contrato incrementada.

### 2.1 Múltiplos implícitos — `apps/backend/app/decision/multiples.py` (novo)

- Por cenário: `EV_exit / EBITDA_anual_saída` e `EV_exit / Receita_anual_saída`,
  usando as mesmas convenções de agregação anual do VC Method (soma dos meses do ano
  de saída, conforme `METHODOLOGY.md`).
- Saída: P25/P50/P75 de cada múltiplo + contagem de cenários excluídos
  (EBITDA ≤ 0 ou receita ≤ 0 não produz múltiplo; a exclusão é reportada, nunca
  silenciosa).
- Rotulagem obrigatória na UI e no PDF: "múltiplo implícito nas suas premissas —
  não é múltiplo de mercado".
- Testes: golden values com seed fixa; propriedade "múltiplo × métrica reconstrói EV
  dentro de tolerância"; caso degenerado com 100% de EBITDA ≤ 0.

### 2.2 Engenharia reversa ampliada ("Plano para a meta") — estende `decision/targets.py` e `insights/`

Hoje o produto responde "qual a probabilidade de valer X". Passa a responder
"o que precisa acontecer para valer X no horizonte":

- CAGR de receita mediano dos cenários que atingem a meta vs. dos que não atingem;
- margem EBITDA mediana no ano de saída, mesmo recorte;
- trajetória ano a ano (receita e margem medianas dos cenários vencedores, anos 1..H);
- deltas por driver reutilizando o recorte hit/miss já existente no motor de insights
  (`insights/engine.py`), com a mesma linguagem de associação — nunca causalidade.
- Caso degenerado: meta com < 50 cenários vencedores → seção reporta amostra
  insuficiente em vez de estatísticas instáveis (limiar fixado em código e testado).

Resultado vira a seção "Plano para a meta" no dashboard de resultados e no PDF.

### 2.3 Gating

Múltiplos implícitos: todos os planos pagos. Plano para a meta: Empresário em diante
(o Grátis mantém a probabilidade da meta que já existe). Aplicado no backend.

## 3. White label

### 3.1 Modelo

`ReportBranding` (novo, 1:1 com `Workspace`): `firm_name`, `logo_path` (arquivo no
volume privado `private_data`, nunca servido publicamente; validação de tipo/tamanho:
PNG/JPEG/SVG sanitizado, ≤ 1 MB), `primary_color` (hex validado), `footer_text`
(texto curto, escapado). Upload e leitura autenticados e escopados ao workspace.

### 3.2 Renderização

`reports/pdf_theme.py` e `reports/pdf.py` aceitam um objeto de branding opcional:

- com entitlement `white_label` e branding configurado → PDF com logo/cores/nome da
  firma, sem marca QuantoVale;
- sem entitlement → comportamento atual (marca QuantoVale; Grátis mantém marca d'água);
- disclaimers metodológicos e identificadores de auditoria (seed, versão do modelo)
  permanecem em TODAS as variantes.

### 3.3 UI

Página "Marca do relatório" em configurações do workspace, visível apenas com o
entitlement. Preview do cabeçalho/rodapé antes de salvar.

### 3.4 Testes

Contrato do PDF com e sem branding; cross-tenant (workspace A jamais lê/usa branding
de B); upload malicioso (SVG com script é sanitizado ou rejeitado); entitlement
aplicado no backend (request forjado sem o plano não injeta branding).

## 4. Planos, preços e lista de espera

### 4.1 Estrutura comercial (decisão aprovada)

| Plano | Preço mensal | Anual (~20% off) | Entitlements principais |
|---|---|---|---|
| Grátis | R$ 0 | — | 1 empresa, 1.000 cenários, resumo com marca d'água |
| Empresário | R$ 97 | R$ 932 (R$ 78/mês) | 5 empresas, 10.000 cenários, relatório completo, Plano para a meta, múltiplos implícitos |
| Consultor | R$ 297 | R$ 2.851 (R$ 238/mês) | tudo do Empresário + white label, até 10 workspaces de cliente, 25.000 cenários |
| Escritório | R$ 697 | R$ 6.691 (R$ 558/mês) | tudo do Consultor + workspaces ilimitados; multiusuário anunciado como "em breve" |

Âncoras de mercado registradas: BizEquity US$ 199,99–499,99/mês (private label no
superior); Equidam US$ 135–1.063 one-off; consultoria tradicional BR R$ 12k–80k por
projeto; Valutech a partir de ~R$ 249.

### 4.2 Entitlements mínimos (sem billing)

- Campo `plan` (enum: `free`, `empresario`, `consultor`, `escritorio`) em `Workspace`,
  default `free`, alterável apenas por operação administrativa auditada
  (`AuditEvent`). Usuário não se autopromove (P14).
- Resolvedor server-side `plan → entitlements` em módulo único
  (`app/core/entitlements.py`): `max_startups`, `max_scenarios_per_run`,
  `white_label`, `max_client_workspaces`, `full_report`, `target_plan_section`.
  Todos os pontos de enforcement consomem o resolvedor; nenhum limite vive só no
  frontend.
- Entidades completas Plan/Entitlement/Usage do PRODUCT_SPEC ficam para a fase de
  billing (YAGNI agora; o enum migra para FK quando billing chegar).

### 4.3 Lista de espera

- Tabela `waitlist`: e-mail (validado), plano de interesse, origem (landing/pricing),
  timestamp. Sem dados financeiros.
- Endpoint público `POST /api/waitlist` com rate limiting simples por IP e resposta
  idempotente para e-mail repetido.
- Landing e `/pricing` mostram preços reais com CTA "Entrar na lista de espera";
  texto explícito de que a cobrança ainda não está ativa. Nenhum checkout.

## 5. Landing: redesign + intro 3D de 7 segundos

### 5.1 Intro coreografada (reusa a cena `components/landing/futures-scene.tsx`)

Três atos, ~7 s no total, rodando uma única vez por sessão (sessionStorage):

1. **0–2 s** — um único ponto/linha ("o número único da planilha"), câmera aproximando;
2. **2–5 s** — explosão em milhares de trajetórias 3D em leque (os futuros simulados),
   com profundidade e paralaxe;
3. **5–7 s** — condensação na distribuição final com P25/P50/P75 destacados; câmera
   assenta sincronizada com a entrada da headline.

Regras: `prefers-reduced-motion` ou WebGL ausente → fallback estático existente;
scroll/clique/tecla pula para o estado final imediatamente; orçamento 60 fps em
desktop médio com degradação de contagem de partículas em mobile; sem bloquear LCP da
headline (texto não espera o canvas).

### 5.2 Revisão de clareza

- Linguagem 100% "qualquer empresa" em todas as rotas públicas (varredura por resíduo
  de "startup" como categoria de cliente; o nome de pacote `@startupvalue/*` e paths
  internos não mudam nesta fase).
- Seção "Para quem" reequilibrada: consultores/contadores/assessores com o white label
  como argumento central ("entregue com a sua marca").
- Seção de planos com os 4 planos e preços reais; página `/pricing` dedicada.
- FAQ: adicionar "Posso usar com meus clientes?" (white label) e "Quando a cobrança
  começa?" (lista de espera).

## 6. Deploy Hostinger (preparação; go-live aguarda domínio)

- `docker-compose.hostinger.yml` e gate basicauth existentes permanecem a base.
- Entregáveis: template de env de produção parametrizado por `DOMAIN`, validação do
  compose mesclado, runbook enxuto (DNS → secrets → migrate → smoke → abrir tráfego)
  e checklist de segurança pré-go-live derivado de `DEPLOY_VPS.md`.
- Go-live real depende do domínio (ainda não registrado) e de acesso SSH do operador.

## 6b. Admin de plataforma (adendo aprovado em 2026-10-03)

O dono do negócio precisa administrar assinantes sem SSH. Escopo aprovado:

- Flag `is_platform_admin` em `User` (concedida apenas por script de operador,
  auditada; nunca por request). Exposta em `/auth/me`.
- Endpoints `/api/v1/admin/*`, todos exigindo a flag (403 caso contrário):
  visão geral (contagens de usuários, workspaces por plano, empresas,
  simulações, relatórios, lista de espera), lista de espera com export CSV,
  busca de workspace por e-mail de membro, e troca de plano auditada
  (reusa `set_workspace_plan`).
- Página `/app/admin` visível apenas para o admin: métricas, tabela/export da
  lista de espera, busca e troca de plano com confirmação.
- Restrição mantida do PRODUCT_SPEC §10: admin NÃO lê projeções financeiras,
  cenários ou PDFs de assinantes; nenhuma rota admin expõe esses dados.

Critérios de aceite adicionais: (8) rota admin com usuário comum → 403 em
todas; (9) troca de plano via admin persiste e gera AuditEvent; (10) export
CSV da waitlist baixa com content-type text/csv.

## 7. Fora de escopo desta fase

Checkout/billing (fase 2 — Mercado Pago ou Stripe), multiusuário por workspace,
score de qualidade de premissas, métricas de saúde financeira (payback/TIR),
comparables de mercado, renomear pacotes/paths internos.

## 8. Critérios de aceite

1. Suíte backend verde, incluindo golden tests das duas métricas novas.
2. PDF com e sem branding passa no teste de contrato; cross-tenant de branding verde.
3. Entitlements dos 4 planos aplicados no backend com testes de request forjado.
4. `POST /api/waitlist` persiste, deduplica e limita taxa.
5. Landing: intro 3D de ~7 s com skip e reduced-motion; Playwright cobre os três
   estados (intro, skip, fallback).
6. Nenhum teste existente de valuation/simulação alterado em valor esperado
   (metodologia intacta).
7. `validate-compose` passa com o env parametrizado por `DOMAIN`; runbook revisado.
