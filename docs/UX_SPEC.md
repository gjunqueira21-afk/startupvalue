# StartupValue — Especificação de experiência

Data: 2026-09-22. Estado: proposta anterior à implementação. Este documento descreve o comportamento esperado; não afirma que ele já existe.

## Princípios

1. Explicar antes de pedir: cada etapa diz por que o dado importa, sua unidade e onde será usado.
2. Complexidade progressiva: modo simples e profissional editam o mesmo modelo canônico. Trocar de modo não perde dados nem cria valores ocultos.
3. Premissas visíveis: defaults têm origem `illustrative_default`, aparecem na revisão e no relatório e nunca são apresentados como benchmark.
4. Resultados condicionais: toda métrica mostra método, base, moeda, horizonte e população. Frequência simulada não é previsão garantida.
5. Trabalho recuperável: rascunhos, jobs e resultados sobrevivem a reload, logout e nova sessão.
6. Acessibilidade e desempenho fazem parte do fluxo; WebGL é enriquecimento progressivo.

## CURRENT SYSTEM e problemas

O legado abre diretamente em um formulário de cinco blocos anuais, permite saltar entre três tabs sem validar dependências e guarda tudo em memória. A inspeção em navegador está em `audit/evidence/legacy_*.yml`. Em 390 px, as tabs chegam a x=570 e o primeiro fluxo passa de 3.500 px. Resultados podem ser abertos vazios; os labels chamam médias mensais de projeção anual; percentuais são inseridos como decimais com sufixo `x`; cards de seleção usam emoji; não há loading recuperável, empty/error states, autenticação, autosave ou retorno contextual. O manual exige cálculo intermediário para avançar (P0039–P0040), mas o código não protege a ordem.

## Arquitetura de informação

Rotas públicas: `/`, `/methodology`, `/glossary`, `/pricing`, `/security`, `/privacy`, `/terms`, `/login`, `/signup`, `/forgot-password`, `/reset-password`.

Área autenticada: `/app` (overview), `/app/companies`, `/app/companies/new`, `/app/companies/[id]`, `/app/scenarios/[id]/edit`, `/app/simulations/[id]`, `/app/compare`, `/app/reports`, `/app/settings`, `/app/admin` apenas para role administrativa.

Navegação principal: Overview, Empresas, Análises, Relatórios. Seletor de workspace aparece quando aplicável. Ajuda contextual, conta e modo de exibição ficam no menu do usuário. Mobile usa header compacto e navegação inferior ou drawer; steps viram lista horizontal com snap e título textual atual, sem cortar controles.

## Landing e entrada

O primeiro fold contém marca, headline fornecida, subheadline, CTA “Calcular minha startup”, CTA “Ver como funciona” e visual Monte Carlo carregado após o conteúdo principal. Fallback 2D comunica os mesmos percentis. As seções seguintes cobrem problema, seis passos, métodos, exemplo claramente ilustrativo, públicos, pricing, FAQ e footer institucional.

Signup solicita nome, e-mail, senha e aceite separado de termos/privacidade. Login oferece recuperação. Mensagens não revelam se um e-mail existe. Após cadastro, onboarding pergunta objetivo, estágio e preferência simples/profissional; são preferências reversíveis, não dados financeiros.

## Dashboard e estados vazios

Overview mostra empresas, execuções, relatórios e uso do plano, seguido de análises recentes. Estado vazio explica o primeiro resultado que será obtido e oferece “Criar primeira empresa”. Lista de empresa mostra P50 com método/base, faixa P25–P75, data, status e versão; sem resultado mostra “Ainda não simulada”, nunca zero.

Jobs usam estados `queued`, `running`, `succeeded`, `failed`, `cancelled`. Progresso vem do backend e informa fase, contagem concluída e total quando conhecido. Reload retoma polling. Falha preserva inputs, mostra `error_code` legível e oferece revisar/reexecutar; retry idempotente não duplica resultado publicado.

## Wizard

Há sete etapas: Empresa; Receita; Operação e reinvestimento; Métricas; Valuation; Incerteza; Revisão. Autosave indica Salvando/Salvo/Erro ao salvar. Próximo valida somente o necessário; usuários podem voltar livremente. A revisão é obrigatória antes do job.

### 1 Empresa

Nome, país, moeda, setor, modelo de negócio, estágio e ano. Campos desconhecidos podem ficar ausentes quando opcionais; ausência não vira zero. País não ativa automaticamente tratamento fiscal detalhado.

### 2 Receita

Escolha explícita Anual ou Mensal. Tabela editável com unidade no cabeçalho e gráfico acessível com tabela equivalente. Alterar frequência abre confirmação mostrando a conversão e arredondamentos. Pre-revenue permite zero com mês esperado de início. Simple pergunta receita atual e projeção do ano 5 e permite curva sugerida marcada como ilustrativa; Professional edita toda a série, sazonalidade e origem.

### 3 Operação e reinvestimento

Receita líquida/bruta e tributos têm definição. COGS ou margem bruta são modos mutuamente exclusivos. Despesas administrativas, vendas/marketing, pessoal, infraestrutura, gerais, D&A, CAPEX e capital de giro são separados. Simple agrupa e mostra “Detalhar”; Professional apresenta reconciliação EBITDA→EBIT→FCFF. Caixa e dívida alimentam a ponte EV→equity, não o FCFF.

### 4 Métricas

Campos mudam conforme modelo: ARR/MRR/churn/CAC/LTV para recorrência; GMV/take rate para marketplace quando suportado. Cada campo diz “informativo” ou “usado no modelo”. Burn e runway só são calculados com caixa e fluxo compatíveis; caso contrário mostrar necessidade de financiamento.

### 5 Valuation

Simple usa perguntas em linguagem direta e mostra os valores técnicos derivados. Professional edita WACC anual ou curva, g terminal, normalização, múltiplo e métrica de saída, retorno alvo, horizonte, investimento e diluição futura. UI exige `g < WACC_terminal`, coerência de múltiplo/métrica e base EV/equity. Aporte, ownership, pre-money e post-money reconciliam ao vivo.

### 6 Incerteza

Simple escolhe baixa/média/alta com intervalos monetários resultantes e aviso de que são presets ilustrativos. Professional define distribuição, parâmetros, suporte, persistência, correlação, failure e recovery. Contagens permitidas são 1k/5k/10k/25k conforme entitlement. Seed é editável/gerada uma vez e sempre visível. Nenhuma opção se chama “alta precisão”.

### 7 Revisão

Resumo por seção com Editar; warnings e erros separados; origem de cada default; método/base/moeda; n; seed; model/tax versions previstos; hipóteses omitidas e aproximações. “Rodar N cenários” fica habilitado apenas sem erro. O clique cria snapshot imutável; duplo clique não cria jobs duplicados.

## Resultados e Decision Intelligence

Header mostra empresa/cenário, status, data, simulation ID, model version, seed, n e seletor de método/base. Métricas principais: P50, P25–P75, P10, P90 e probabilidade de meta. P5/P95, média/SD e massa <=0 ficam em detalhes. Texto executivo usa somente `SimulationResult`; com massa no P50, não afirma “50% estritamente abaixo”.

Tabs: Visão geral; Distribuição; Financeiro; Drivers; Meta; Sensibilidade; Métodos; Premissas. Histograma, CDF e box plot compartilham cores e percentis, têm tabela e descrição. Failure/zero aparecem como massa explícita. Breakeven diferencia operacional sustentado de recuperação acumulada, mostra P(T≤12/24/36/60) e “não atingido no horizonte”.

Drivers exibem Spearman, sinal, população e n com texto “associação no modelo”. Tornado fica separado como perturbação ceteris paribus. Upside/downside comparam subconjuntos e contagens. Variável constante não aparece com zero inventado.

Em “What needs to be true?”, usuário informa target, método/base e recebe hits/N, proporção e erro Monte Carlo, além de P25/P50/P75 de inputs em hit/miss. Grupo vazio ou n pequeno tem explicação. Alterar target consulta samples salvos e cria análise derivada; não roda Monte Carlo novamente.

Comparação exige mesma moeda, horizonte e base ou mostra impedimento. Cada coluna identifica versão e premissas. Duplicar cenário cria nova revisão editável; arquivar mantém resultados; excluir usa diálogo com nome digitado quando houver resultados e informa consequências.

## Ajuda e linguagem

Tooltip curto responde “o que é” e “por que importa”; link “Saiba mais” abre drawer sem perder o wizard. Glossário cobre DCF, WACC, terminal, perpetuidade, Monte Carlo, percentil, mediana, desvio padrão, VC, pre/post-money, diluição, breakeven, ARR e MRR. Conteúdo do manual é revisado: remover P25 como piso, hierarquia DCF/VC, faixas sem fonte e “otimização” tributária automática.

Termos preferidos: estimativa, cenário, distribuição, frequência simulada, associação, hipótese. Evitar: valor verdadeiro, previsão garantida, causa, melhor regime, piso justo. Mensagens de erro apontam campo e correção; não exibem stack trace.

## Acessibilidade e mobile

Meta WCAG 2.2 AA: landmarks, heading order, labels programáticos, descrição de erro ligada ao input, focus visível, skip link, ordem de tab coerente, targets de pelo menos 24×24 CSS px e contraste validado. Cards de escolha usam radio nativo. Charts não são única fonte; cada um tem resumo e tabela. Cor nunca é o único indicador. Dados atualizados usam região `aria-live` sem anunciar cada frame.

`prefers-reduced-motion` remove paralaxe, contagem animada e movimento de partículas; fallback estático permanece. WebGL não recebe foco nem intercepta pointer necessário. Em mobile, resumo/resultados funcionam; tabelas viram cards ou scroll com primeira coluna fixa e affordance; formulários têm teclado numérico apropriado; CTA não cobre conteúdo; PDF preview usa miniatura e download.

## Error e destructive states

- 401 expira sessão, preserva rascunho local não sensível e retorna ao ponto após login.
- 403 mostra ausência de acesso, sem revelar existência do recurso.
- 409 de revisão indica que cenário mudou e oferece recarregar/duplicar, sem sobrescrever.
- 422 mantém valores e foca primeiro erro.
- 429 informa espera e não repete job automaticamente.
- Indisponibilidade de Redis impede novo job com status honesto; resultados salvos continuam legíveis.
- PDF em processamento tem status; falha pode ser repetida sem recalcular simulação.

## Migração

1. Preservar originais e importar somente projeções como rascunho `legacy_unverified`.
2. Criar componentes sem fórmula e contratos de formulário canônicos.
3. Implementar auth, workspace, empresas e autosave antes do wizard completo.
4. Ligar wizard ao motor testado; liberar resultados apenas com artefato persistido.
5. Liberar target, comparação e PDF após autorização e consistência de fonte.
6. Testar com founder iniciante e analista profissional; revisar termos e defaults pela compreensão observada.

## Critérios de aceitação UX

- Fluxo signup→simulação→resultado→logout/login recupera exatamente a análise.
- Usuário não envia unidade ambígua nem avança com `g>=WACC`.
- Troca simple/pro mantém inputs canônicos e revela todos os defaults na revisão.
- Navegação por teclado completa landing, auth, wizard, resultados e download.
- Viewports 390×844, 768×1024 e 1440×900 não têm overflow global, sobreposição ou CTA inacessível.
- Reload em job e PDF retoma status; falha nunca produz card com zero substituto.
- Resultado informa método/base/população; target não muda simulation ID ou samples.
- Todos os gráficos críticos têm alternativa textual/tabela e passam contraste AA.

