# StartupValue — Especificação de produto

Data: 2026-09-22. Responsável: especialista 1, Product Manager. Status: **proposta para implementação; não descreve funcionalidades já entregues**.

## 1. Fontes e conclusão da auditoria

Foram lidos integralmente o texto extraído do manual V2 (`docs/audit/evidence/manual_full_text.txt`, 324 linhas numeradas, incluindo tabelas) e o HTML original, agora preservado em `legacy/startupvalue_dashboard_v2.html`. O manual é referência funcional e educacional sujeita a correção. O HTML é um protótipo local, com três etapas, cálculo e estado em memória no navegador, gráficos Chart.js e exportação TXT. Não constitui um SaaS, nem há evidência de autenticação, persistência remota, isolamento de clientes ou testes nesse arquivo.

O produto deve permitir formular e confrontar premissas de investimento. Seu objeto central é uma **análise reproduzível**, vinculada a uma empresa e a uma versão de cenário, que apresenta uma distribuição de valores condicionada às premissas. A aquisição comercial deve prometer transparência sobre possíveis futuros, sem converter frequência simulada em probabilidade objetiva de mercado.

## 2. Posicionamento e resultado esperado

**STARTUPVALUE — Valuation Intelligence for Startups.**

Headline: “Não existe um único futuro para uma startup. Nós calculamos milhares deles.”

Subheadline: “Transforme projeções financeiras em uma distribuição probabilística de valuation através de Monte Carlo, DCF e Venture Capital Method.”

Proposição: uma plataforma para estimar faixas, investigar risco, identificar associações entre premissas e resultados, comparar alternativas e documentar decisões de investimento e captação. A aplicação deve responder: quanto pode valer; qual intervalo central; qual downside/upside; qual frequência simulada supera uma meta; quais premissas caracterizam os cenários que atingem essa meta; como os dois métodos diferem; qual chance de breakeven no horizonte definido.

O benefício verificável é reduzir a distância entre uma projeção financeira e uma decisão explicável. Não se promete valuation certificado, recomendação individual de investimento, previsão do preço de uma rodada ou otimização tributária juridicamente válida.

## 3. Públicos e personas

| Persona de projeto | Trabalho que precisa executar | Obstáculo | Experiência prioritária |
|---|---|---|---|
| Founder/co-founder em preparação de rodada | Discutir faixa de valor, aporte e diluição com sócios e investidores | Jargão e confiança indevida em um número único | Modo simples, premissas visíveis, meta de valuation e narrativa |
| CFO/analista de investimento/VC/family office/CVC | Auditar uma tese e confrontar hipóteses | Modelo opaco, falta de reprodutibilidade e convenções inconsistentes | Modo profissional, snapshots, métodos separados e exportação |
| Advisor/consultoria/boutique de M&A | Repetir análises para vários clientes | Retrabalho, risco de mistura de dados, apresentação fraca | Várias empresas, comparação, relatórios privados |
| Aceleradora/incubadora/investidor-anjo | Ensinar premissas e avaliar oportunidades | Diferentes níveis de formação e maturidade | Glossário, ajuda contextual, etapas pequenas |

Estas personas são hipóteses de design derivadas do briefing e do público citado no manual; não são resultados de entrevistas. Pesquisa posterior deve validar linguagem, disposição a pagar, periodicidade de uso e dados disponíveis.

## 4. Sistema atual e problemas comprovados

| Evidência | Problema de produto | Decisão proposta |
|---|---|---|
| Manual 25–40; HTML `goToStep` | Etapas dependem de cálculo manual prévio; navegação permite abrir resultados vazios | Wizard com validação, rascunho persistido e revisão antes do envio |
| Manual 43–53; HTML `rec1..rec5`, `buildReceita` | Campos apresentados como projeção anual representam médias mensais repetidas 12 vezes | Unidade explícita, entrada anual ou mensal, conversão transparente sem multiplicação implícita |
| HTML `state`, `runSimulation`, `exportResults` | Resultado só em memória; TXT não recupera cenário nem garante auditoria | Empresa, cenário versionado, execução e relatório persistidos |
| Manual 190–193; HTML `res-post-dcf-med`, `res-post-vc-med` | Resultado de método recebe rótulo pós-money sem aporte efetivo | Identificar EV/equity e base pré/pós-money; rodada separada e reconciliada |
| Manual 128–131; HTML `calcImposto` | “Otimizar” é promessa sem branch de otimização; anexos 2/4/5 caem no 3 | Estimativa simplificada rotulada; não vender comparação tributária até implementar elegibilidade e regras |
| HTML `filterPositive` | Percentis e gráficos eliminam zeros/falhas/negativos, alterando a leitura de risco | Preservar amostra completa e distinguir valor operacional de valor do equity |
| HTML `generateRevenueScenario`, `Math.random` | Incerteza fixa e sem seed, sem parâmetros explicáveis de persistência | Modelo estocástico versionado, configurável e reproduzível |
| Manual 141–145; HTML variável `breakeven` em `runSimulation` | Prazo informado é lido mas não entra na probabilidade exibida | Prazo como meta de comparação, distribuição observada e censura explícita |
| Manual 216–217 | P25 é apresentado como piso aceitável de negociação | Percentil é descrição da amostra; preço negociável depende de condições externas |
| Manual 191–192 | DCF chamado conservador e VC otimista como propriedade geral | Comparação explicada pelos inputs e mecanismos, sem ranking automático |
| Manual 71, 77, 151, 160–172 | Faixas de custos, encargos, sucesso, múltiplos e WACC sem fonte/calibração | Não propagar como benchmarks; exemplos rotulados e premissas editáveis |
| Manual 136–139; HTML opções “Preciso/Alta Precisão” | Mais sorteios tratados como validade econômica | Explicar redução do erro de Monte Carlo sem corrigir premissas inadequadas |
| HTML `calcStats` e `renderResults` | Ausência P10/P95, drivers, comparação e alvo livre | Contrato completo de resultados e Decision Intelligence |

As correções matemáticas específicas pertencem a `MODEL_AUDIT.md` e `METHODOLOGY.md`. Este documento não valida regras fiscais nem preserva resultados antigos por conveniência comercial.

## 5. Jornada e activation

1. Landing apresenta proposta, visual conceitual de futuros, métodos, casos de uso, exemplo marcado como ilustrativo, FAQ, planos e metodologia pública.
2. CTA abre signup/login; após signup cria workspace pessoal e mostra primeira empresa. Recuperação de senha deve funcionar com provedor de e-mail configurado; envio não configurado não pode fingir sucesso de entrega.
3. Usuário seleciona objetivo e modo simples/profissional. Pode trocar modo preservando os mesmos inputs canônicos e visualizando o que mudou.
4. Wizard: empresa → receita → custos e reinvestimentos → métricas opcionais → premissas de valuation → incerteza/simulação → revisão.
5. Revisão mostra todas as premissas efetivas, origem dos valores, unidade, método, moeda, horizonte, versão e seed. Defaults são hipóteses de exemplo, nunca benchmarks implícitos.
6. Envio cria job e snapshot imutável. A interface mostra etapa e progresso verdadeiro informado pelo backend; sem contadores decorativos. Reabrir a página recupera execução.
7. Resultado abre com método e base de valor explícitos, P50/P25/P75, downside/upside e interpretação dos números reais. Métodos alternáveis mantêm os mesmos identificadores de cenários.
8. Usuário informa meta, compara target-hit/miss, lê associações, duplica cenário ou baixa relatório privado.
9. Em nova sessão, dashboard recupera empresas, cenários, execuções e relatórios.

**Evento de activation:** primeira simulação válida concluída e persistida, seguida de leitura dos resultados e uma ação de interpretação (meta, comparação ou relatório). Cadastro isolado não conta como ativação.

## 6. Escopo funcional do primeiro produto vendável

### Conta, trabalho e dados

Signup/login/logout/recuperação; workspace com autorização; CRUD de empresa; rascunho de projeção; criar/duplicar/renomear/arquivar/excluir cenário; execuções imutáveis; listas e detalhes; comparação de cenários da mesma moeda/base/horizonte, com diferenças explicitadas. Edição de cenário não altera resultados antigos nem seus PDFs. Um resultado pode ser identificado como baseado em versão anterior.

Perfil mínimo: nome, setor, país, modelo de negócio, estágio e ano de fundação. Empresa pré-receita pode projetar receitas futuras; valores ausentes não se tornam zeros silenciosamente. País será informativo; suporte fiscal detalhado a outros países não deve ser anunciado. Moeda inicial BRL, estrutura preparada para outra moeda sem converter ou comparar moedas distintas implicitamente.

Receita e despesas: 5 anos anuais ou 60 meses; granularidade única por série e normalização auditável. Custos separados de CAPEX, depreciação, capital de giro, caixa e dívida. Informação insuficiente exige rotular aproximação, sem chamar EBITDA de fluxo de caixa livre. Métricas SaaS são opcionais; ARR/MRR/churn/CAC/LTV não alteram valuation por mágica e devem indicar se são descritivas ou drivers do modelo.

### Modelagem e interpretação

DCF e VC auditados; caixa/dívida e rodada explícitos; falhas e valores não positivos preservados; receitas, custos, margens e taxa de desconto modelados conforme metodologia; parâmetros por cenário e dependência temporal; seed obrigatória; 1.000/5.000/10.000/25.000 execuções disponíveis conforme entitlement.

Resultados: P5/P10/P25/P50/P75/P90/P95, média, dispersão, histograma, densidade apropriada ao tipo de distribuição, CDF e box plot; receitas, EBITDA, fluxo de caixa e margens; breakeven com definição operacional e/ou caixa identificada, chance em 12/24/36/60 meses e percentis condicionais identificados. Massa de falha/zero deve ser visível e densidade contínua não deve ocultá-la.

Decision Intelligence: drivers calculados por método definido; tornado com impacto identificado como perturbação controlada; explicações automáticas determinísticas; frequência de atingir valuation alvo; mediana/P25/P75 dos inputs nos grupos hit/miss, tamanhos de amostra e aviso quando um grupo é vazio ou pequeno. Nenhuma narrativa transforma associação em causa. Alterar meta consulta cenários existentes e não ressorteia a análise.

Incerteza: exibir medida quantitativa documentada, como IQR e dispersão relativa quando denominador for válido. Não criar rótulo “alta/moderada/baixa” sem regra publicada e justificativa. Se P50 for zero ou próximo de zero, informar indisponibilidade da razão e mostrar dispersão absoluta, sem infinito enganoso.

PDF A4 dedicado, com 12 seções previstas no briefing, extraído do mesmo resultado e snapshot do dashboard; identifica empresa, data, simulação, versão, seed, contagem, método, base de valor, premissas e limitações. Todos os componentes devem existir antes de a oferta chamar o relatório de profissional.

### Experiência, operação e segurança

Landing premium e hero 3D progressivo, fallback 2D, preferência por movimento reduzido e mobile; aplicação acessível por teclado; validação contextual; recuperação de falhas de jobs; monitoramento, limites de uso, backups restauráveis e deploy Docker/VPS com HTTPS. Produção é um gate verificável; não é uma etiqueta atribuída ao finalizar código.

## 7. Simple Mode e Professional Mode

Simple Mode simplifica a linguagem e propõe presets documentados, não reduz transparência nem muda a matemática escondidamente. “Baixa/média/alta incerteza” deve mostrar o parâmetro efetivo e dizer que é uma hipótese selecionada, não uma inferência de setor. O mapeamento numérico será definido e versionado pelo especialista estatístico antes da implementação.

Professional Mode oferece distribuição e parâmetros próprios, WACC por ano, terminal growth, horizonte, target return, múltiplo e métrica de saída, aporte/diluição, parâmetros de correlação e seed. “Linear” é uma trajetória de referência, não uma família probabilística; “custom” exige esquema validado e não execução de código arbitrário.

Modo é uma preferência de interface, distinto do plano comercial. Transparência das premissas, seed, metodologia, política de falhas e acesso aos próprios dados existem em todos os planos.

## 8. Arquitetura comercial e entitlements propostos

Não há pesquisa de preço ou custo de produção nesta auditoria. Os limites abaixo são decisões iniciais de produto, sujeitos a benchmark de capacidade; não são comparações de mercado. Preços devem permanecer “a definir” em documentação e o checkout desativado até credenciais e política comercial existirem. Não mostrar assinatura ativa fictícia.

| Capacidade | Free | Pro | Advisor / VC |
|---|---|---|---|
| Empresas ativas por workspace | 1 | 5 (limite inicial proposto) | 25 (limite inicial proposto) |
| Contagens por execução | 1.000 | 1.000/5.000/10.000 | 1.000/5.000/10.000/25.000 |
| Modos simples e profissional | Sim | Sim | Sim |
| DCF, VC, percentis completos, seed e premissas | Sim | Sim | Sim |
| Persistência e recuperação | Sim | Sim | Sim |
| Meta e drivers essenciais | Sim | Sim | Sim |
| Comparação de cenários e análise condicional completa | Não | Sim | Sim |
| PDF | Resumo com marca d'água | Relatório completo | Relatório completo por cliente |
| Workspaces | 1 pessoal | 1 | Vários, isolamento explícito |
| Exportar/excluir os próprios dados | Sim | Sim | Sim |
| White label | Fora do lançamento | Fora do lançamento | Roadmap, não anunciado como entregue |

25.000 cenários são uma capacidade obrigatória do core a testar, acessível inicialmente ao plano Advisor; não é uma exigência para toda simulação ou todo usuário em modo profissional. Para testes e ambientes sem billing, atribuição administrativa auditada permite validar todos os planos. Usuário não pode autoconceder entitlement.

Entidades: `Plan` identifica oferta; `Entitlement` controla limites efetivos; `Usage` registra execução/recursos e janela. Quotas mensais, concorrência e retenção são configuração de operação após benchmark e cálculo de custo; não se anuncia “ilimitado”. Reserva de uso ao enfileirar, conclusão/reconciliação idempotente e liberação quando job não iniciou evitam cobranças duplas. Limite esgotado apresenta explicação e preserva dados. Downgrade impede novas ações acima do limite e preserva leitura/exportação/exclusão de análises existentes.

Billing é adaptador com modos `disabled` e provedor futuro. Webhooks verificados, idempotentes e auditáveis quando implementados. Sem credenciais, não há cobrança nem promessa de processamento.

## 9. Retenção e métricas

Retenção nasce do acompanhamento de premissas: duplicar cenário, comparar versões de captação, revisar projeções mensalmente e recuperar relatórios de comitê. Não depender de volume de simulações como prova de valor.

Métricas de produto propostas: conclusão do onboarding; abandono por etapa; tempo até primeiro resultado válido; proporção de resultados com meta analisada; proporção de cenários comparados; retorno em 30 dias; geração de PDF concluída; erro de execução; recuperação bem-sucedida após reload/login. Instrumentar eventos sem valores financeiros, nomes de empresas, tokens ou texto livre sensível. Definir metas quantitativas após baseline, sem inventar taxas de conversão.

Casos comerciais: founder prepara faixa e condições para rodada; advisor compara premissas conservadora/base/agressiva para cliente; analista documenta a diferença DCF/VC e o peso do valor terminal; aceleradora usa glossário e cenários para ensinar risco. Nenhum caso comercial implica garantia de preço realizável.

## 10. Admin e direitos sobre dados

Admin mínimo: contagens de usuários, planos, empresas, jobs, relatórios, uso e falhas; filtros operacionais; alteração de plano auditada; retry controlado de jobs. Acesso administrativo não concede automaticamente leitura de projeções financeiras ou download de PDFs. Não implementar impersonação como atalho.

Produto deve ter páginas de privacidade/termos/LGPD consistentes com fluxos reais, exportação autenticada de dados e exclusão de startup, análise e conta. Exclusão informa efeitos e dependências; invalida acesso imediato e tem tratamento documentado de arquivos, jobs em andamento e backups. Prazos e base de retenção exigem definição no documento de segurança/privacidade antes de publicação, sem afirmar conformidade apenas por existir uma página.

## 11. Roadmap e plano de migração

| Fase | Entrega | Gate de avanço |
|---|---|---|
| 0 — Auditoria e especificação | Pareceres dos 14 especialistas, evidências, decisões de metodologia e arquitetura | Leituras completas, divergências catalogadas, nenhuma alteração da aplicação antes da conclusão |
| 1 — Foundation | Serviços separados, banco/migrations, auth, tenant, contratos e jobs | Integração e isolamento testados |
| 2 — Modelo | DCF, VC, impostos simplificados identificados, MC e sensibilidade | Golden/property tests, reprodução e benchmark |
| 3 — Experiência core | Landing, 3D progressivo, dashboard, wizard, resultados persistidos | Fluxo real completo, acessibilidade e responsive |
| 4 — Decisão e relatório | Metas, condicionais, comparação, narrativa e PDF | Mesmo resultado no dashboard/PDF; casos vazios e negativos |
| 5 — Release | Admin, entitlements, segurança, backup, deploy Docker/VPS | E2E em ambiente equivalente à produção, restore, HTTPS e smoke tests |
| 6 — Expansão | Reverse valuation, benchmarks, cap table/SAFE/options, carteira, IA explicativa | Evidência de demanda e metodologia específica por módulo |

Preservar o HTML em `legacy/startupvalue_dashboard_v2.html` somente depois do gate da auditoria; manter original verificável por hash. Não importar resultados antigos como se fossem reproduzíveis. Futuro importador de premissas deve exigir confirmação de unidade, mapear categorias e criar novo snapshot marcado como migrado; um novo resultado corrigido é uma nova execução. Manter comparação com legado nos testes apenas onde a fórmula anterior era correta, documentando diferenças esperadas nos demais casos.

A publicação em VPS depende de infraestrutura e acesso reais. Preparar Compose, scripts e guia não equivale a deployment efetuado. Relatório de entrega deve separar verificado localmente, verificado em Docker e verificado em VPS.

## 12. Critérios de aceitação de produto

| ID | Critério testável |
|---|---|
| P01 | Signup/login/logout/reset funcionam; login após logout recupera empresa, cenário e resultado reais |
| P02 | Wizard salva rascunho, valida inputs e preserva parâmetros ao alternar modos e recarregar |
| P03 | Entrada anual versus mensal equivalente produz séries canônicas equivalentes sob regra documentada |
| P04 | Alterar premissa cria nova versão; resultado/PDF anterior mantém snapshot original |
| P05 | Mesmos inputs/versão/seed/contagem reproduzem resultados sob contrato numérico; seed aparece no PDF |
| P06 | Cenários de falha/negativos/zero entram nos denominadores; total de cenários informado é reconciliável |
| P07 | P5/P10/P25/P50/P75/P90/P95 e gráficos derivam do resultado persistido, inclusive distribuição degenerada |
| P08 | Meta calcula hit/miss do mesmo conjunto; grupos vazios não geram explicações inventadas |
| P09 | Drivers, tornado e narrativa são derivados de dados; métodos e limitações são visíveis |
| P10 | Breakeven distingue definição, horizonte e sobreviventes; prazo informado altera a comparação correta |
| P11 | DCF/VC identificam métrica e base; aporte, pre/post-money e ownership reconciliam |
| P12 | PDF usa mesmo resultado sem nova MC e download é negado a outro tenant |
| P13 | Usuário A não lista/lê/edita/exclui resultados de B, inclusive por IDs conhecidos e jobs/relatórios |
| P14 | Free/Pro/Advisor têm limites aplicados no backend; alterar request não concede plano |
| P15 | Landing/login/dashboard/resumo/PDF preview funcionam em mobile, teclado e movimento reduzido |
| P16 | Erro/retry/reload durante job não duplica execução nem perde snapshot; progresso nunca inventa contagens |
| P17 | Exportação e exclusão atingem entidades e arquivos associados, com política de backup explicitada |
| P18 | Fluxo E2E: cadastro → empresa → wizard → simulação → meta → PDF → logout/login → análise recuperada |
| P19 | Docker e restore de backup são exercitados; healthchecks validam banco/Redis/app; deploy público só declarado após verificação |
| P20 | Todas as promessas comerciais correspondem a capacidades disponíveis; funcionalidades futuras aparecem como roadmap |

## Parecer

O protótipo é útil como inventário de termos e interação inicial. Não deve ser comercializado como plataforma profissional antes de corrigir semântica financeira, estatística e tributária, introduzir persistência/isolation e validar a jornada completa. A prioridade de produto é tornar cada conclusão rastreável a cenários e premissas; a apresentação premium reforça essa confiança, mas não a substitui.
