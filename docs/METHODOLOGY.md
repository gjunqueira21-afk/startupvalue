# StartupValue — Metodologia proposta

Data: 2026-09-22. Modelo proposto: `3.0.0-draft`; publicação de `3.0.0` somente após testes e revisão. Documento de especificação; não constitui evidência de implementação. Mudanças matemáticas, parâmetros padrão, ordem de amostragem ou convenções estatísticas exigem nova versão do modelo. Regras fiscais têm versão e vigência próprias.

## 1. O que se estima

Todos os resultados são condicionados às projeções, premissas e mecanismos aqui declarados. Probabilidade simulada não é frequência de mercado validada. O objetivo é tornar comparáveis possíveis futuros, com risco e limitações explícitos. Não há preço justo garantido, piso automático de negociação ou preferência universal entre DCF e VC.

Cada resultado identifica `method`, `valuation_basis`, moeda, data-base, horizonte e população: incondicional ou condicional a um estado. Bases permitidas: `dcf_enterprise_value`, `dcf_equity_signed`, `dcf_equity_limited_liability`, `vc_implied_post_money`, `vc_implied_pre_money`. Nunca somar/apresentar distribuição de bases distintas como se fosse uma só.

## 2. Contrato financeiro

O detalhamento e os casos de correção estão em [MODEL_AUDIT.md](MODEL_AUDIT.md). Convenções acordadas com a auditoria quantitativa:

- Receita anual deve ser convertida em 12 meses cujo total reconcilie o valor informado. Receita mensal média do legado significa 12 vezes o valor no ano. Perfil mensal uniforme é uma hipótese visível; um perfil customizado usa pesos mensais não negativos que somam 1.
- `EBITDA = receita − COGS − despesas operacionais`; `EBIT = EBITDA − D&A`; `FCFF = EBIT − impostos operacionais pagos + D&A − CAPEX − ΔNWC`. Financiamentos e aportes não são FCFF. Modelo por margem bruta e modelo por COGS são mutuamente exclusivos para evitar dupla dedução.
- DCF usa fluxos ao final de cada mês. Taxa mensal efetiva `w_m=(1+w_a)^(1/12)−1`. Fator de desconto `DF_t=∏(1+w_m,k)`, de k=1 até t. Uma taxa anual variável não é retroativamente aplicada a todos os meses anteriores.
- Terminal no mês60: `TV_60=FCFF_61_sustentável/(w_m,terminal−g_m)`. `EV=Σ FCFF_t/DF_t+TV_60/DF_60`. Exigir `g_anual < WACC_terminal`; não substituir terminal inválido por zero.
- FCFF terminal é normalizado economicamente, com reinvestimento e margem sustentável declarados. Não perpetuar um choque transitório isolado no mês60. FCFF sustentável negativo exige abordagem de encerramento/transição explícita, em vez de rotular perpetuidade negativa como empresa estável.
- `equity_signed = EV + caixa excedente + ativos não operacionais − dívida − outros claims`. Não contar caixa inicial duas vezes no FCFF/ponte. Caixa necessário à operação não é automaticamente excedente.
- `equity_limited_liability=max(equity_signed,0)` é uma visão econômica opcional, sob hipótese de responsabilidade limitada e sem aportes obrigatórios adicionais. Preservar o valor assinado e a massa de zeros; nunca apagar cenários negativos.
- VC: EBITDA anual de saída é soma dos meses49–60, ou receita anual para um múltiplo de receita escolhido explicitamente. `EV_exit=múltiplo×métrica_anual`; ponte para equity exit; `PV_exit=equity_exit/(1+r)^H`. Sob plano financiado compatível, `post_money=PV_exit`, `pre_money=post_money−I`, `ownership=I/post_money`. Resultado inviável não vira participação negativa ou >100% aceita silenciosamente. Diluição futura requer retenção explícita da participação.
- Método por múltiplo EBITDA não é aplicável quando a métrica de saída é não positiva; usar fallback econômico configurado, preservar o cenário e registrar motivo. Não removê-lo da amostra para melhorar os percentis.
- Risco de encerramento explícito e prêmio de risco na taxa devem ser explicados em conjunto para evitar dupla contagem. Não “corrigir” WACC/retorno alvo automaticamente.

## 3. Premissas e distribuições

Cada variável armazena nome, unidade, distribuição, parâmetros, suporte, origem (`user`, `illustrative_default`, `calibrated`), referência de calibração quando houver e se é fixa. Não existe CoV universal de 35%. A mesma distribuição não é obrigatória para receita, custo, margem e taxa.

| Distribuição | Parametrização / validação | Interpretação |
|---|---|---|
| Constante | valor finito | Incerteza desativada; não aparece como driver estimável. |
| Normal | loc e scale>0; para variáveis não negativas usar truncamento [L,U] | loc/scale são parâmetros da normal subjacente, não necessariamente média/SD após truncar. Exibir momentos resultantes. |
| Student-t | df>2 para modo com variância finita, loc, scale; limite de suporte declarado | Antes de truncar, SD=scale×sqrt(df/(df−2)); para SD desejado s, scale=s×sqrt((df−2)/df). Não exponenciar t como se tivesse média finita lognormal. |
| Triangular | mínimo a ≤ modo c ≤ máximo b, a<b | Média=(a+b+c)/3; usuário informa modo, não “média”. a=b é constante explícita. |
| Uniforme | a<b | Média=(a+b)/2; todos os valores no suporte têm mesma densidade. |
| Lognormal | média aritmética m>0 e CoV c>0 | sigma=sqrt(log(1+c²)); mu=log(m)−sigma²/2; X=exp(mu+sigma Z). c=0 vira constante; receita estrutural zero continua zero. |
| Trajetória customizada / Linear | valores mensais ou anuais com unidades e perfil | É uma projeção-base, não uma distribuição. Acrescentar separadamente fatores de incerteza. |
| Sistema legado | sem categoria independente | Importar como uniforme [0,7;1,3] apenas mediante descrição explícita da hipótese antiga. |

Normal truncada usa `a=(L−loc)/scale`, `b=(U−loc)/scale` na convenção SciPy. Não usar clipping, que cria massa artificial nas fronteiras. Para t truncada, amostrar `q=F(L)+u×(F(U)−F(L))` e aplicar a inversa; publicar momentos pós-truncamento. [SciPy truncnorm](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.truncnorm.html), [SciPy t](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.t.html).

Na triangular, se `u<(c−a)/(b−a)`, `x=a+sqrt(u(b−a)(c−a))`; caso contrário, `x=b−sqrt((1−u)(b−a)(b−c))`. A parametrização lognormal distingue média do log da média monetária. [SciPy triang](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.triang.html), [SciPy lognorm](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.lognorm.html).

### Modo simples

Proposta de presets ilustrativos, não benchmarks: baixa/média/alta incerteza usam fatores lognormais de receita com média1 e CoV 0,10/0,25/0,50, respectivamente; fatores de custos fixos média1 e CoV 0,05/0,15/0,30. O usuário vê os intervalos monetários resultantes na revisão e pode alterar os parâmetros. Esses números são decisões de produto sujeitas à validação de compreensão, não classificação científica de risco.

Um fator de receita e um fator de custos fixos persistem por todo o horizonte no modo simples. Receita e custo variável compartilham o vínculo contábil descrito abaixo. WACC, g e múltiplo ficam fixos se usuário não ativar incerteza; não inventar drivers para eles. Probabilidade de failure deve ser informada ou a análise deve declarar `conditional_on_survival`; não assumir “70% de sucesso” como dado de mercado. Todos os parâmetros, inclusive defaults ocultos durante onboarding, aparecem na revisão e PDF.

## 4. Trajetórias economicamente coerentes

Primeiro release pode usar fatores por cenário constantes ao longo de 60 meses, com projeção-base informada; isso representa erro persistente de planejamento. Não representa crescimento estocástico estimado. O modo profissional permite processo mensal com persistência e marginais explícitas:

1. Para cada cenário i, sortear vetor normal persistente `A_i~N(0,R)` e estado inicial independente `E_i,1~N(0,R)`.
2. `E_i,t = rho E_i,t−1 + sqrt(1−rho²) epsilon_i,t`, com `epsilon~N(0,R)` independente entre meses/cenários, `|rho|<1`.
3. `Z_i,t=sqrt(lambda)A_i+sqrt(1−lambda)E_i,t`, `0≤lambda≤1`; marginais normais padrão. Correlação latente temporal de um fator a lag h: `lambda+(1−lambda)rho^h`.
4. `U_i,k,t=Phi(Z_i,k,t)` e `X_i,k,t=F_k,t^−1(U_i,k,t)` produzem fatores com marginais escolhidas. A cópula gaussiana é uma hipótese, não prova de dependência de cauda. R é correlação dos latentes, não necessariamente correlação Pearson dos valores finais.
5. `receita_i,t=base_receita_t × fator_receita_i,t`. O custo de cada categoria é soma de componente fixo informado×fator de custo e proporção variável×receita simulada. Nenhum custo deve ser simultaneamente incluído em COGS e despesa operacional.
6. Choque de margem é representado por alteração do ratio de COGS/custo variável, com suporte válido; EBITDA e sua margem são derivados. Não sortear EBITDA margin independentemente e também subtrair as mesmas despesas.

Modo simples: lambda=1 e R identidade entre fatores exógenos, reconhecendo a hipótese de independência residual. No profissional, rho/lambda/R exigem escolha explícita ou preset identificado como ilustrativo; não afirmar que foram estimados. R deve ser simétrica, diagonal1 e positiva definida para Cholesky; rejeitar matriz inválida com explicação, sem “corrigir” silenciosamente. Dependências determinísticas devem ser modeladas como vínculos e não matriz singular. [NIST sobre autocorrelação](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35c.htm).

Incerteza de crescimento pode ser expressa por dispersão do fator aumentando no tempo, com parâmetros anuais interpolados; não adicionar silenciosamente um random walk ao processo. Crescimento realizado é calculado da trajetória. Receita zero exige mês de início de operação explícito; fator multiplicativo não cria vendas a partir de zero.

Para WACC/g incertos, primeiro release exige suportes compatíveis: menor WACC terminal estritamente maior que maior g, com margem econômica definida na configuração. Domínio validado antes do job. Não rejeitar draws inválidos e apresentar os restantes como população original. Não truncar valuation extremo; se houver overflow/NaN, falhar a execução com diagnóstico técnico e manter inputs para revisão.

## 5. Encerramento, distress e caixa

Escolha inicial implementável: modelo de encerramento exógeno por horizonte com timing declarado. Entrada `p_failure_60` em [0,1]. Hipótese simplificada de hazard mensal constante `h=1−(1−p_failure_60)^(1/60)`; tempo de encerramento tem distribuição geométrica, limitado ao horizonte. p=0 significa nenhum encerramento exógeno; p=1 significa encerramento no primeiro mês, devendo a UI explicitar essa consequência. Futuro modelo de hazard por período deve ser outra opção versionada.

Em cada trajetória, operar até o mês anterior ao encerramento; no mês de encerramento aplicar fluxo de liquidação empresarial líquido de despesas de fechamento declarado pelo usuário; após isso receita/custos operacionais/terminal são zero. Valor residual zero é hipótese visível quando escolhido. DCF inclui os fluxos anteriores e recuperação descontada, com ponte EV/equity consistente; não substituir toda a história por zero. VC deve usar valor distribuível na liquidação e seu momento, se ocorrer antes da saída, com tratamento de claims no motor financeiro.

Preservar simultaneamente cenário operacional contrafactual e trajetória realizada com encerramento para auditoria, sem misturar populações nas métricas. Failure não é censura estatística independente: é estado absorvente concorrente ao breakeven. Horizonte sem breakeven é não atingimento observado até mês60.

Estados de resultado são regras transparentes: `failure` por encerramento; `distress` por déficit de caixa quando existe ponte de caixa/financiamento completa; `low_growth` por crescimento abaixo de um limiar definido pelo usuário; `operating` nos demais. Não interpretar caixa negativo calculado só com FCFF como insolvência comprovada: serviço da dívida, juros, caixa inicial e financiamento afetam liquidez. Sem esses dados, mostrar “necessidade acumulada de financiamento”, não runway factual. Probabilidade de survival/failure é premissa e resultado observado, não variável contínua sorteada novamente sem justificativa.

## 6. Reprodutibilidade e artefato canônico

Usar `numpy.random.Generator(numpy.random.PCG64(seed))` explicitamente. Persistir seed antes de enfileirar; se usuário não fornece, gerar seed uma única vez no backend. Nunca usar seed nula em análise salva. Inputs canonicalizados incluem unidades, defaults resolvidos, política fiscal, método, base e todas as premissas.

Congelar ordem de fatores, ordem e shapes das chamadas ao RNG, dtype float64, algoritmo de decomposição, convenção de quantis, sequência dos blocos e versão de bibliotecas no manifesto da versão do modelo. Worker paralelo não define ordem dos draws. No primeiro release, uma execução gera arrays na ordem canônica e jobs paralelizam entre análises. Mais tarde, streams por blocos estáveis exigem testes e versão. Não prometer identidade bit a bit entre arquiteturas arbitrárias. A repetição exata exige imagem, ambiente e chamadas equivalentes. [Política NumPy de compatibilidade](https://numpy.org/doc/2.0/reference/random/compatibility.html).

`SimulationResult` imutável contém: IDs de workspace/startup/scenario/simulation; revisão de inputs; model_version; tax_version/effective_date; seed; n; timestamps; input_hash; runtime/image digest; RNG; parâmetros/correlações; contadores de estados; resultados por cenário ou referência protegida a arrays; estatísticas; gráficos agregados; drivers; definições de breakeven; target analysis inicial; warnings; hash dos dados de resultado. Valores ausentes usam null+motivo, nunca zero substituto.

Dashboard e PDF leem esse mesmo artefato, sem executar Monte Carlo novamente. Mudança de target consulta os samples armazenados e cria análise derivada versionada, referenciando o resultado original. Mudança de premissas cria nova simulação. Persistir ao menos inputs realizados relevantes, outputs, estado, métricas anuais, breakeven e trajetórias necessárias aos gráficos; política de retenção nunca apaga silenciosamente os dados necessários para a análise comercial prometida.

## 7. Estatísticas, intervalos e gráficos

Sobre N cenários de cada base: min, max, mean, median, P5/P10/P25/P50/P75/P90/P95, variância populacional (`ddof=0`) e SD descritiva. Convenção para valores contínuos: `numpy.quantile(method='linear')`, idêntica à interpolação correta do legado quando a amostra é a mesma. Média/SD só publicadas se finitas. Não filtrar valores negativos, zeros ou caudas. [NumPy quantile](https://numpy.org/doc/stable/reference/generated/numpy.quantile.html).

P25–P75 é intervalo central da distribuição simulada; não é intervalo de confiança de 50% para o valor verdadeiro da empresa. Em amostras com empates a massa entre limites pode exceder 50%; narrativa deve reconhecer concentração no valor. Mínimo/máximo são extremos observados, não limites econômicos possíveis.

Incerteza: mostrar `IQR=P75−P25`, `spread80=P90−P10`, probabilidade de equity_signed<=0 e massa de equity realizável zero. Mostrar `IQR/|P50|` somente quando |P50| é material (limiar monetário de apresentação explícito, por exemplo R$1 na moeda BRL); se não, null “mediana próxima de zero”. CoV=SD/|mean| somente com média não próxima de zero e com indicação de que perde utilidade em distribuições que cruzam zero. Não derivar score HIGH/MODERATE/LOW sem validação de thresholds. Mostrar “intervalo interquartil corresponde a X% da magnitude da mediana” quando aplicável.

Histograma tem bins reprodutíveis e contagens cuja soma é N. Densidade de histograma é count/(N×largura), com unidade monetária correta. Valores iguais viram um único átomo, não largura zero. Mostrar CDF empírica, box plot e marcadores dos percentis. Uma KDE opcional só descreve a parte contínua, com bandwidth declarado e peso proporcional; não suavizar massa de failure para negativos artificiais nem chamá-la probabilidade pontual. Valores extremos podem usar zoom, mas número/probabilidade fora do viewport continuam explícitos.

## 8. Erro Monte Carlo

Simulações permitidas: 1.000/5.000/10.000/25.000 por entitlement. Número de cenários melhora precisão numérica sob o modelo; não reduz incerteza econômica das premissas. Para evento com k sucessos, `p_hat=k/N`. Erro padrão aproximado `sqrt(p_hat(1−p_hat)/N)` e intervalo Wilson95% para erro de amostragem Monte Carlo. Nos limites k=0 ou N, Wilson não colapsa. Para zero hits, dizer “nenhum cenário atingiu a meta nesta amostra”, não “impossível”. [NIST Wilson](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).

Fórmula: com z=1,959963984540054, centro `(p_hat+z²/(2N))/(1+z²/N)` e meia largura `z sqrt(p_hat(1−p_hat)/N+z²/(4N²))/(1+z²/N)`. Este intervalo se refere à probabilidade do modelo com cenários independentes; correlação entre meses dentro de um cenário não viola independência entre cenários.

Erro padrão da média pode usar SD amostral/sqrt(N) com aviso de caudas pesadas. Não prometer cobertura normal em distribuições extremas. Intervalos para quantis ficam opcionais após validação por order statistics ou bootstrap de cenários inteiros; nunca reamostrar meses como observações independentes. Não confundir bootstrap numérico com validação externa do modelo.

## 9. Breakeven

Definir separadamente:

- Operacional sustentado: primeiro mês t que inicia K meses consecutivos de EBITDA>=0, antes de eventual failure; K=3 como convenção de estabilidade, configurável e registrada. A data é o mês inicial do bloco, confirmado ao final dele. Blocos incompletos no fim do horizonte não contam.
- Recuperação de caixa acumulado: primeiro mês em que fluxo de caixa acumulado cobre desembolso inicial explicitamente informado; métrica de projeto, sem incluir aportes como receita. Zero investimento inicial é hipótese, não valor omitido.

Guardar evento, mês e motivo de não atingimento. `P(T<=h)=count(event && T<=h)/N` para h=12/24/36/60 e meta do usuário; failure permanece no denominador. Quantis temporais incondicionais usam inversa discreta da CDF: menor mês com CDF>=q. Se q não for atingido até60, informar “não atingido no horizonte”; não substituir por60,61 ou mediana dos vencedores. Quantis condicionais aos atingidos podem ser exibidos em quadro separado com n/N. Não usar Kaplan–Meier tratando encerramento como censura não informativa para inflar probabilidade de breakeven.

## 10. Drivers e sensibilidade

Spearman entre fator/input realizado e valuation da mesma base, calculado com ranks médios nos empates. Publicar rho, direção, n, status estimável e população; variáveis constantes resultam null, não rho inventado. Ordenar por |rho|, com desempate estável. WACC fixo, failure_probability fixo ou exit_multiple fixo não aparecem como drivers estatísticos dessa execução. Variável `failure_state` pode ter associação, distinta da premissa de probabilidade de failure. [SciPy Spearman](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html).

Não interpretar rho² como contribuição à variância, rho como causalidade, ou p-value pequeno de amostra sintética como evidência empírica de mercado. Comparar amostra incondicional e operacional condicional quando útil; explicar que seleção altera associações. Receita Y5 e margem são métricas derivadas e podem ser redundantes com fatores de entrada; identificá-las como tal, sem somar importância.

Tornado é análise determinística separada: reavaliar motor para níveis baixo/alto definidos (por exemplo P10/P90 de um input), mantendo demais inputs-base. Registrar endpoints e restrições de viabilidade. Para fatores correlacionados, mudanças isoladas podem quebrar relações; construir cenários conjuntos compatíveis ou rotular exercício ceteris paribus. Não atribuir probabilidade ao tornado. Sobol, regressão padronizada e correlação parcial são extensões sujeitas a diagnóstico e validação; Sobol clássico não deve ser aplicado aos inputs dependentes sem tratamento adequado.

Upside/downside descritivos: definir subconjuntos superiores/inferiores por quantis da base escolhida, publicar tamanho e medianas/IQR dos inputs. Empates podem alterar fração do subset; informar contagens reais. Só narrar diferenças observadas, com unidade e sinal calculados. Não afirmar que uma intervenção causa o deslocamento.

## 11. Target e What Needs To Be True

Meta T sempre escolhe método/base/moeda/data compatíveis. `hit_i=(valuation_i>=T)`; probabilidade usa todos os N cenários dessa base. Mostrar count_hit/count_miss, p_hat e Wilson95%. Para cada input relevante, calcular P25/P50/P75 dentro de hit e miss; diferenças de medianas com sinal e unidade. Média pode ser adicional, nunca substituto obrigatório das estatísticas robustas.

Subconjunto vazio: estatísticas null+motivo. Subconjunto pequeno: contagem sempre visível; política de apresentação conservadora pode suprimir narrativa inferencial para n<30, rotulada como limite editorial e não lei estatística. Empates/equality seguem >=. Variável constante não recebe uma diferença explicativa. A probabilidade meta e análise comparativa são recalculadas exclusivamente dos samples imutáveis, sem novo sorteio.

Texto: “Nos cenários simulados que atingem T, a mediana de X é A; nos demais é B. A diferença é uma associação dentro deste modelo.” Nunca “X é necessário e suficiente” com base apenas nessa comparação. Múltiplas combinações podem atingir o mesmo valor.

Reverse valuation permanece extensão preparada: busca limitada a faixas econômicas fornecidas pelo usuário, método/base explícitos, common random numbers para comparação e verificação em amostra independente. Otimizar até p>50% exige considerar erro Monte Carlo, declarar objetivo/restrições e registrar buscas sem selecionar apenas resultados favoráveis. Não vender solver ou “receita necessária” como funcionalidade antes dessa implementação e seus testes.

## 12. Narrativa, relatório e testes de aceitação

Narrativa determinística usa apenas valores do artefato e regras de texto versionadas. Mostrar n, seed, model version, data, premissas dominantes, horizonte e base. Para empates, substituir “metade abaixo/metade acima” por interpretação correta da mediana. Se dado faltar, dizer por quê. Camada futura de LLM pode explicar, sem calcular ou substituir números.

Casos obrigatórios antes de release:

1. Percentis analíticos [0,10,20,30,40] -> [2,4,10,20,30,36,38] para P5..P95; valores assinados e massa zero preservados.
2. Triangular(50,100,150) média100; uniforme(50,150) média100; lognormal média100/CoV0,25; t5 escalada para variância1; normal truncada sem massa espúria. Testar tolerâncias de momentos derivadas de erro amostral, com seed fixo, sem tolerâncias ajustadas para “passar”.
3. Caso constante/zero, failure0 e failure1, array finito, N correto, erro de suporte, percentis ordenados, soma de bins=N.
4. Mesma seed/config/ambiente produz mesmos samples e resultado; retry, reload, PDF e target não alteram resultado salvo. Mudança do processo de draws exige revisão de golden fixture.
5. lambda1 preserva fator no tempo; AR1 estacionário aproxima correlação teórica; totais mensais reconciliam anos; custos/margens respeitam identidades.
6. T=[12,24,null,null,null] -> P24=0,4 e mediana incondicional não atingida; operacional e acumulado não se confundem.
7. Meta abaixo/acima de todos os resultados; meta exata em massa zero; grupos vazios; variável constante Spearman=null; permutação dos samples não altera estatísticas.
8. Propriedades financeiras em domínio correto: g>=WACC inválido; fluxo positivo maior não reduz DCF; WACC maior não eleva PV de fluxos e terminal não negativos, mantidas demais premissas. Não impor monotonicidade universal a séries assinadas.
9. Golden fixtures numéricas independentes em módulo financeiro, com tolerância e justificativa; nenhuma fixture derivada apenas copiando saída atual como verdade.
10. Benchmark real N=1k/5k/10k/25k registrando hardware, imagem, seed, inputs, RAM e duração; nenhum número de tempo foi produzido nesta fase de auditoria.

## 13. Migração metodológica

Preservar legado e hashes; importar projeções com unidades explícitas; manter resultados antigos somente como `legacy_unverified`, sem relabeling como modelo novo. Avisar que correções de imposto, DCF, VC, seleção de amostra e persistência de riscos alteram resultados. O manual vira camada educativa após remover recomendações sem suporte e afirmações de causalidade/precisão. Usar fontes primárias desta especificação e auditoria financeira; parâmetros ilustrativos permanecem claramente diferenciados de observações de mercado.

## 14. Convenções implementadas no motor estruturado (3.1.0-dev)

O contrato estruturado aceita exatamente 60 valores mensais para `monthly_revenue`, `monthly_opex` e `monthly_capex`, além de `gross_margin` entre 0 e 1. Receita e OPEX não podem ser negativos; CAPEX é determinístico nesta versão. Receita e OPEX recebem fatores multiplicativos separados, com distribuições explícitas `revenue_uncertainty` e `cost_uncertainty`. Distribuições de fatores multiplicativos precisam ter suporte não negativo. O choque de margem é aditivo em pontos percentuais: margem mensal amostrada por normal truncada em [0,1], centrada na margem-base, com desvio `margin_uncertainty_pp`; desvio zero produz margem constante. A truncagem altera a média efetiva perto de 0% e 100%, portanto a margem-base não deve ser interpretada automaticamente como média amostral nessas bordas.

Os três fatores usam uma cópula gaussiana com correlação cruzada identidade nesta implementação. `serial_correlation` controla a persistência AR(1) da parcela residual mensal; `persistent_weight` controla a parcela constante por cenário. A ordem de sorteio é: componente persistente, estado residual inicial, inovações mensais e mês de encerramento. Mesmos inputs canônicos, seed, N, versão de modelo e ambiente de execução reproduzem os mesmos vetores. A hipótese de independência cruzada dos três latentes não foi inferida de dados de mercado.

Para cenário *i* no mês *t*, o fluxo simplificado é `FCFF_i,t = receita_base_t × fator_receita_i,t × margem_i,t − opex_base_t × fator_custo_i,t − capex_base_t`. É uma aproximação operacional antes de efeitos tributários, variação de capital de giro, depreciação e detalhes de financiamento; não corresponde a FCFF contábil completo sem esses componentes. O encerramento é absorvente: fluxos operacionais anteriores permanecem, o fluxo do mês de encerramento é substituído pelo valor de liquidação informado e os meses seguintes ficam zero. O valor terminal só é concedido a cenários sem encerramento até o horizonte.

O DCF usa desconto mensal efetivo derivado do WACC anual. Quando há crescimento terminal, o fluxo mensal normalizado no horizonte é a **média dos últimos 12 FCFF mensais realizados**, limitada a zero apenas para elegibilidade ao valor terminal; os fluxos explícitos negativos são preservados. O valor terminal é calculado no fim do mês 60 e descontado pelo fator acumulado desse mês. Esta convenção substitui o uso do último mês isolado também para novas execuções do caminho legado `monthly_fcff`; por isso a versão do modelo é incrementada. Resultados anteriores persistidos não são recalculados.

Para análise de drivers estruturados, o snapshot privado guarda valuation assinado, receita e OPEX realizados no Ano 5, margem bruta **modelada** no Ano 5, fatores médios de receita/custo e estado de encerramento. Receita e OPEX realizados ficam zero após encerramento; a margem modelada preserva o caminho contrafactual, inclusive em cenários encerrados, e não é apresentada como margem observada depois do encerramento. Essas variáveis podem ser dependentes entre si. Spearman e a comparação hit/miss descrevem associação dentro dos cenários, não efeitos causais. FCFF total e FCFF dos últimos 12 meses foram excluídos da lista de drivers porque repetiriam quase diretamente o cálculo do DCF. No caminho legado, apenas fator de FCFF e estado de encerramento são drivers disponíveis.
