# Auditoria matemática — StartupValue

Data: 22/09/2026. Especialidade: Quant / Financial Mathematician. Status: auditoria e especificação concluídas; novo motor ainda não validado por este documento. Versão proposta do modelo: `3.0.0-draft`, reservando `3.0.0` para o motor aprovado; a mudança é incompatível numericamente com os erros identificados em `legacy-v2.0`.

## Escopo e evidência

Foram lidos integralmente o HTML original (1.666 linhas) e a extração integral do manual (324 linhas). Referências `H:L` abaixo apontam para linhas do arquivo preservado em `legacy/startupvalue_dashboard_v2.html`; referências `M:L` apontam para os parágrafos numerados em [manual_full_text.txt](audit/evidence/manual_full_text.txt), extraídos de `manual_startupvalue.docx`. Os parágrafos do manual não são números de página Word.

Os casos executados contra funções originais, sem modificação, estão em [legacy_probe_results.json](audit/evidence/legacy_probe_results.json); a rotina reprodutora é [probe_legacy.cjs](audit/evidence/probe_legacy.cjs). Eles comprovam defeitos do legado e não constituem testes de aprovação de uma aplicação nova. Cálculos adicionais abaixo foram conferidos independentemente em Python com aritmética de dupla precisão. Valores monetários devem ser arredondados apenas na apresentação.

## CURRENT SYSTEM

Projeções são cinco valores mensais médios por categoria, repetidos em blocos de 12 meses. Há quatro categorias de despesa, um fluxo denominado EBITDA menos impostos, desconto DCF mensal e saída VC a cinco anos. O Monte Carlo varia apenas receita, aplica uma porta binária de sucesso e descarta valuations não positivos antes das estatísticas. Não existem caixa, dívida, CAPEX, capital de giro, D&A, aporte efetivo, histórico tributário, seed ou versão do resultado persistido.

Os principais bloqueadores são: dupla divisão do Simples por 12; EBITDA anual parcial no caso determinístico; desconto variável não acumulado; perpetuidade um mês adiantada; saída VC mensal com desconto incorreto; participação calculada sobre pré-money; EV/equity/pré/pós-money confundidos; remoção dos fracassos da distribuição. Os resultados existentes não devem ser apresentados como valuations auditados.

## Convenções propostas

- Moeda BRL nominal, data-base explícita, fluxos de fim de mês, horizonte inicial de 60 meses. Não misturar crescimento real e taxa nominal.
- Receita informada como total anual é convertida em 12 parcelas que reconciliam exatamente; média mensal é multiplicada por 12. Campo `input_frequency` obrigatório. Sazonalidade é configuração explícita.
- Taxas armazenadas como decimal anual efetivo; UI apresenta percentuais. `25%` corresponde a `0.25`, não `25` nem `0.25%`.
- FCFF em BRL/mês; WACC é taxa do fluxo para todos os financiadores. FCFE, se introduzido futuramente, exige custo de equity e tratamento separado de dívida.
- Exibir separadamente EV operacional, ponte caixa/dívida, equity antes da rodada e termos da rodada. Simulação e pré/pós-money são eixos distintos.
- Cenários negativos e fracassos permanecem no conjunto. `raw_equity_value` assinado e `realizable_equity_value` sob responsabilidade limitada são métricas separadas, nunca filtros de seleção.
- `SimulationResult` registra premissas, base de valuation, unidade, taxa terminal, versão tributária, modelo, seed, quantidade e versão numérica do ambiente. PDF consome esse resultado sem recalcular.

## Q01 — Fluxo de caixa não é EBITDA menos imposto

**CURRENT IMPLEMENTATION.** H:1197–1204 e H:1388–1395 subtraem despesas administrativas, gerais, vendas, pessoal e imposto. Resultado vai diretamente ao DCF. M:81–83 chama isso de EBITDA e fluxo descontado, mas M:271–272 reconhece a diferença entre lucro e caixa. Não há custo de entrega/COGS claramente discriminado, D&A, CAPEX ou variação de capital de giro.

**PROPOSED IMPLEMENTATION.** Elaborar uma ponte mensal: receita bruta menos tributos sobre faturamento/deduções = receita líquida; menos COGS e despesas operacionais = EBITDA; menos D&A = EBIT. `FCFF = EBIT − impostos operacionais em caixa + D&A − CAPEX − ΔNWC`. Tributos já deduzidos da receita não podem ser novamente subtraídos como imposto sobre lucro. Caso simples permite valores zero para reinvestimento e capital de giro, exibindo que são premissas do usuário, não fatos observados. [Referência conceitual FCFF, NYU Stern](https://pages.stern.nyu.edu/~adamodar/pdfiles/eqnotes/fcff.pdf).

**MATHEMATICAL RATIONALE.** O ativo operacional é financiado pelo fluxo disponível após reinvestimento; lucro operacional não é fluxo livre. A equação acima é também uma identidade contábil de reconciliação adotada pelo modelo.

**IMPACT ON RESULTS.** O legado tende a superestimar caixa quando CAPEX e capital de giro são positivos. Não há direção universal: liberação de capital de giro ou impostos diferentes pode compensar parte da diferença.

**TEST CASE.** EBITDA=100, D&A=10, imposto operacional em caixa=18, CAPEX=20, ΔNWC=5: EBIT=90 e FCFF=57. Proxy EBITDA−imposto=82; diferença=25. Todo componente deve reconciliar sem dupla contagem; COGS incluído em despesas não pode entrar outra vez em margem bruta.

## Q02 — Conversão anual/mensal correta, calendário precisa ser fixado

**CURRENT IMPLEMENTATION.** H:1267 usa `wm=(1+w)^(1/12)−1`; H:1268 desconta o fluxo no mês `j+1`. Essa parte é correta para taxa anual efetiva constante e fluxos de fim de mês. H:1137–1151 repete médias mensais de cada ano; o rótulo “Projeção Anual” em H:632 torna a unidade menos clara.

**PROPOSED IMPLEMENTATION.** Preservar conversão e convenção temporal. Implementar funções puras de calendário/conversão, sem fórmulas em componentes. Oferecer anual e mensal com metadados, sem alegar que um fluxo anual no fim do ano é equivalente a 12 recebimentos antecipados ao longo do ano.

**MATHEMATICAL RATIONALE.** `(1+wm)^12=1+w`. Dividir WACC por 12 corresponde a outra convenção de taxa, não à taxa efetiva informada.

**IMPACT ON RESULTS.** Compatibilidade exata com a parcela explícita do legado para taxa constante e os mesmos fluxos. Diferença entre modos anual/mensal pode resultar de calendário de recebimentos e deve ser explicada.

**TEST CASE.** WACC=25% → `wm=0.018769265121506118`. Único fluxo R$125 no mês12, sem terminal → PV=R$100. Tol. absoluta `1e-9` neste caso. Receita anual=R$120.000, alocação uniforme → 12×R$10.000; média mensal R$120.000 → total anual R$1.440.000.

## Q03 — WACC variável é descontado incorretamente

**CURRENT IMPLEMENTATION.** H:1263–1268 aplica a taxa do ano do fluxo elevada ao número de meses desde a data-base. A taxa do ano 2 substitui retroativamente a do ano 1; não há encadeamento. H:1275 usa somente o WACC final para todo o desconto terminal.

**PROPOSED IMPLEMENTATION.** Para `r_t=(1+WACC_ano(t))^(1/12)−1`, usar `D_0=1`, `D_t=D_(t−1)×(1+r_t)` e `PV_t=FCFF_t/D_t`. `PV_terminal=TV_60/D_60`. Separar WACC terminal da curva de transição.

**MATHEMATICAL RATIONALE.** O valor percorre cada período e cada custo de capital. O produto acumulado preserva a cronologia.

**IMPACT ON RESULTS.** Quando taxas caem, o legado tende a superestimar fluxos tardios e terminal; quando sobem, a direção se inverte, para fluxos positivos.

**TEST CASE.** Fluxo único R$100 no mês24; taxa ano 1=20%, ano 2=10%, sem terminal. Correto: `100/(1.2×1.1)=75.7575757576`; legado: `100/1.1²=82.6446280992`. Taxas iguais em todos os anos devem coincidir com o motor de taxa constante.

## Q04 — Terminal: mês errado, numerador errado e último mês instável

**CURRENT IMPLEMENTATION.** H:1271–1277 calcula `CF60/(wm−gm)/(1+wm)^59`. Não projeta CF61, desconta só 59 meses e usa um draw isolado do último mês; na curva variável também perde taxas anteriores.

**PROPOSED IMPLEMENTATION.** Definir fluxo terminal mensal normalizado compatível com margem, reinvestimento e capital de giro sustentáveis. No caso simplificado de base estável: `CF61=CF60_normalizado×(1+gm)`; `TV60=CF61/(wm_terminal−gm)`; `EV=Σ(FCFF_t/D_t)+TV60/D60`. Ano 5 pode informar a normalização (ex. média do ano), mas o ajuste precisa ser registrado. Não tratar um choque transitório no mês60 como perpetuidade. Se não houver operação sustentável após mês60, usar horizonte estendido ou liquidação explicitamente modelada; não inventar terminal positivo.

**MATHEMATICAL RATIONALE.** Somatório da série geométrica a partir do primeiro fluxo após o horizonte: `Σ[k≥1] CF60_normalizado(1+gm)^k/(1+wm)^k = CF61/(wm−gm)`. A premissa de crescimento sustentável inclui reinvestimento, não apenas expansão de receita. [Modelo de crescimento estável e reinvestimento, NYU Stern](https://pages.stern.nyu.edu/~adamodar/pdfiles/eqnotes/fcff.pdf).

**IMPACT ON RESULTS.** Com WACC constante e fluxo terminal positivo, legado/correto para PV terminal = `(1+wm)/(1+gm)>1`. Em 60 meses, taxa25%, g3%, CF=R$1.000 mensais: PV terminal antigo R$20.476,6244266484; novo R$20.148,9444266484. DCF total antigo R$56.296,8867356744; novo R$55.969,2067356744. Diferença R$327,68, antes de outras correções.

**TEST CASE.** Golden contra VM: 60×R$100, WACC12%, g3% → legado `12715.54931529076`; fórmula corrigida `12658.806629718902`. Tol. monetária `1e-6`. Terminal desligado deve excluir apenas a parcela terminal. Aumentar choque isolado mês60 não deve contaminar todos os anos futuros quando marcado transitório.

## Q05 — g ≥ WACC vira terminal zero silenciosamente

**CURRENT IMPLEMENTATION.** H:1277 retorna zero se `wm−gm<=0`; formulário permite combinações inválidas. O usuário recebe valuation finito como se a hipótese tivesse sido aceita.

**PROPOSED IMPLEMENTATION.** Rejeitar Gordon com `g>=WACC_terminal`, taxas não finitas, `1+taxa<=0` e unidades incompatíveis. Mensagem: “O crescimento terminal deve ser menor que a taxa de desconto terminal.” Draws aleatórios devem respeitar um domínio conjunto válido por construção e guardar a transformação utilizada; não descartar cenários inválidos silenciosamente.

**MATHEMATICAL RATIONALE.** A série de Gordon só converge quando a razão descontada é menor que 1. Pequena diferença positiva produz alta sensibilidade; apresentar a participação do terminal no EV e essa proximidade, sem piso arbitrário oculto.

**IMPACT ON RESULTS.** Elimina valores aparentemente conservadores originados de hipótese inválida.

**TEST CASE.** WACC12%, g12%, 60×R$100: legado entrega `4558.7794703037325`; correto é erro de validação, sem resultado parcial salvo como concluído. g13% também falha. WACC12%, g3% passa.

## Q06 — EV, equity e rodada misturados

**CURRENT IMPLEMENTATION.** DCF determinístico é chamado de pré-money (H:1221–1222); mediana DCF simulada vira pós-money (H:966–968, H:1476), sem adicionar aporte e sem caixa/dívida. M:255 define corretamente pós=pré+aporte, contradizendo a interface. M:191–192 sugere que DCF é conservador e VC otimista sem fundamento geral.

**PROPOSED IMPLEMENTATION.** `EV_operacional=PV_FCFF`; `equity_pre_raw=EV+caixa_excedente+ativos_não_operacionais−dívida−outros_claims`. Exigir que caixa seja disponível/excedente, sem contar caixa operacional ou aporte duas vezes. Rodada primária simplificada: `equity_post=equity_pre+investimento`, com custos de emissão e secundárias discriminados quando suportados. Valor VC implícito da rodada deve ser mostrado separadamente do DCF intrínseco.

**MATHEMATICAL RATIONALE.** Dívida e caixa são uma ponte entre ativo operacional e reivindicação dos sócios. Pré/pós-money descreve a transação, não o uso ou ausência de Monte Carlo. [Ponte de valor operacional para equity, NYU Stern](https://pages.stern.nyu.edu/~adamodar/pdfiles/eqnotes/fcff.pdf).

**IMPACT ON RESULTS.** Muda significado e potencialmente magnitude da manchete. Métodos só são comparáveis com a mesma moeda, data, horizonte e base equity/EV; nenhum deve ser forçado a ficar acima do outro.

**TEST CASE.** EV=10M, caixa excedente=2M, dívida=3M, outros claims=0 → equity pré=9M. Aporte primário1M → equity pós10M, ownership10%. DCF não deve crescer automaticamente por chamar a simulação de pós-money. Cap table sem preferências é hipótese explícita.

## Q07 — VC: periodicidade, desconto e base de saída

**CURRENT IMPLEMENTATION.** H:1286–1289 e fórmula duplicada H:1400 usam `EBITDA_mês60×múltiplo/((1+r)^5−1)`. M:162–163, M:261 e M:284–285 dizem EBITDA anual/último ano. R=0 gera divisão por zero. A função `calcVC` não é usada no fluxo principal, possibilitando correções divergentes.

**PROPOSED IMPLEMENTATION.** `EBITDA_Y5=Σ EBITDA_meses49..60`. `EV_exit=EBITDA_Y5×EV/EBITDA_multiple`; `equity_exit=EV_exit+excess_cash_exit−debt_exit−other_claims_exit`. `PV_exit_equity=equity_exit/(1+r)^H`. O retorno `r` é anual efetivo; alternativamente MOIC explicitamente identificado, sem misturar ambas as unidades. Se EBITDA terminal≤0, múltiplo EBITDA não é método adequado: informar indisponibilidade e permitir múltiplo de receita escolhido/documentado, ou recovery em distress, sem excluir o cenário inteiro. Uma política de recovery precisa atribuir valor equity a todos os cenários para produzir a distribuição incondicional VC; ausência dessa política bloqueia a distribuição VC completa, não o DCF.

**MATHEMATICAL RATIONALE.** Múltiplo anual exige base anual; desconto de valor futuro usa fator bruto `(1+r)^H`, não ganho acumulado líquido do principal. O método VC deriva valuation presente da saída futura descontada. [Método original, Harvard Business School](https://www.hbs.edu/faculty/Pages/item.aspx?lang=en&num=6515).

**IMPACT ON RESULTS.** Dois erros atuam em direções opostas: base mensal reduz por aproximadamente 12; subtração de 1 no denominador aumenta o PV. No caso constante a correção combinada aumenta o valor em cerca de 8,77 vezes; isso não é multiplicador universal porque a soma anual pode diferir de 12×mês60.

**TEST CASE.** EBITDA=R$100.000 em cada mês do ano 5, múltiplo8, r30%, H5, dívida líquida saída0: EV_exit=R$9.600.000; PV=R$2.585.559,1136918818. Legado=R$294.884,12896757375. Com r=0, PV=9.600.000 finito. Com EBITDA variável `[0,...,0,100000]` no ano 5, usar soma100.000, não anualizar run-rate sem identificação.

## Q08 — VC: investimento, required ownership e diluição

**CURRENT IMPLEMENTATION.** Nenhum investimento ou caixa de saída informado; VC vira suposto pós-money automaticamente. Participação mínima pertence a uma fórmula DCF sem conexão com retorno exigido (H:1430–1433).

**PROPOSED IMPLEMENTATION.** Para rodada que financia o plano e um investidor pari passu, sem preferências, sem fluxos intermediários e sem diluição posterior: `post_money_VC=PV_exit_equity`, `pre_money_VC=post_money_VC−I`, `ownership_required=I×(1+r)^H/equity_exit=I/post_money_VC`. Ownership>100% ou pré negativo → estrutura inviável sob essas hipóteses; nunca saturar ownership em100% fingindo cumprir retorno. Com retenção futura `q=Π(1−d_k)`, `ownership_today=ownership_exit/q`; o pós-money implícito de hoje é `PV_exit_equity×q`. Sem q informado, assumir1 explicitamente.

**MATHEMATICAL RATIONALE.** O produto entre participação final e equity de saída deve remunerar principal e retorno alvo. Valuation pós-money e cheque determinam pré-money. [Kauffman / Bill Payne, VC Method](https://www.entrepreneurship.org/articles/2007/07/valuation-of-prerevenue-companies-the-venture-capital-method).

**IMPACT ON RESULTS.** Faz aparecer quando o aporte solicitado e o retorno alvo são incompatíveis. Não somar I novamente ao PV VC que já é identificado como pós-money do plano financiado. Planos pré e pós-captação devem especificar as próprias necessidades de funding; o aporte não cria valor operacional instantaneamente por identidade matemática.

**TEST CASE.** Caso Q07, I=R$1M → ownership38,6763541667%, pré=R$1.585.559,11369188. Retenção80% → ownership inicial48,3454427083%. Ownership final deve reconciliar exatamente com `I×1.3^5/9.6M`. Falta de equity_exit positivo não pode gerar ownership infinito exibido como válido.

## Q09 — Aporte para participação mínima usa base incorreta

**CURRENT IMPLEMENTATION.** H:1430–1432 usa `I=pre×p` e `post_min=pre×(1+p)`. Isso compra participação `p/(1+p)`, inferior a p. Manual M:193 e M:259 prometem participação no capital pós-aporte.

**PROPOSED IMPLEMENTATION.** Mantido um pré-money positivo e uma rodada primária sem preferências/custos: `I=pre×p/(1−p)` e `post=pre/(1−p)`. Para cheque fixo: `p=I/(pre+I)`. Restringir target ownership a `[0,1)` e mostrar casos economicamente inviáveis separadamente.

**MATHEMATICAL RATIONALE.** Resolver `p=I/(pre+I)` para I. Pré-money e participação são inputs independentes; não inventar aporte por mediana de outra definição de valor.

**IMPACT ON RESULTS.** O legado subestima o cheque exigido. Pré1M e participação20%: cheque antigo200k adquire16,6667%; correto250k adquire20%.

**TEST CASE.** Pré5M,p15% → aporte882.352,94117647 e pós5.882.352,94117647. p 0→aporte0. p 100% e pré positivo→erro de domínio.

## Q10 — Tributos: dupla divisão e unidades diferentes

**CURRENT IMPLEMENTATION.** H:1157–1179 retorna valor anual para “real” e “presumido”, mas mensal para Simples. Chamadores H:1203 e H:1393 dividem novamente por 12. No Simples, imposto final fica12 vezes menor mesmo sob a própria tabela simplificada do legado.

**PROPOSED IMPLEMENTATION.** Contrato tributário tipado, preferencialmente saída mensal explícita `tax_cashflow[60]`, com receita, base, competência, pagamento e tipo do tributo. Uma função anual alternativa deve retornar anual para todos os regimes. No modelo simplificado de ano estável, calcular imposto anual uma única vez e alocar por 12 apenas uma vez. Modelo detalhado do Simples exige histórico RBT12 e receita da competência; não usar soma do próprio ano futuro como histórico. [LC123, art.18, texto oficial](https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp123.htm).

**MATHEMATICAL RATIONALE.** A unidade do contrato precisa ser invariável entre branches; `BRL/ano ÷12=BRL/mês`, enquanto duas divisões distorcem magnitude.

**IMPACT ON RESULTS.** Infla fluxo de caixa e DCF no Simples. Receita anual 120k, anexoIII primeira faixa 6%: imposto anual 7.200 e mensal 600; legado desconta50/mês. Esta é uma verificação da tabela histórica usada no HTML, não apuração tributária completa para 2026.

**TEST CASE.** Somatório dos12 impostos mensais deve reconciliar7.200 no caso simplificado. Real e Presumido também devem reconciliar sua saída anual. Não testar exigibilidade tributária real utilizando somente essa identidade.

## Q11 — Imposto determinístico usa EBITDA incompleto

**CURRENT IMPLEMENTATION.** H:1197–1203 monta EBITDA dentro do mesmo loop que soma o ano. No mês1 há apenas1 mês; no mês12 há12. Em Lucro Real, imposto do caso determinístico cresce artificialmente dentro do ano. Na simulação H:1388–1393 o vetor já está completo; assim os dois caminhos discordam mesmo sem aleatoriedade.

**PROPOSED IMPLEMENTATION.** Construir projeção completa antes de calcular base anual quando se usa aproximação anual. Compartilhar pipeline entre caso-base e simulação de volatilidade zero. Motor detalhado usa calendário real e acumulados corretos, não o tamanho acidental do vetor.

**MATHEMATICAL RATIONALE.** Com lucro mensal constante E, o legado totaliza `0.34×E×(1+...+12)/12=0.34×E×6.5`, em vez de `0.34×E×12` sob sua própria hipótese fiscal.

**IMPACT ON RESULTS.** Para E=R$1.000/mês, imposto anual legado R$2.210 vs R$4.080 pela aproximação consistente 34%. Esses números isolam o defeito computacional;34% sobre EBITDA não é recomendação tributária.

**TEST CASE.** Caso-base e cada cenário com volatilidade 0, sucesso 100% e mesmas premissas produzem idênticos EBITDA, impostos, FCFF, EV e equity. O teste deve capturar diferenças antes dos percentis.

## Q12 — Regimes e “otimização” não correspondem aos rótulos

**CURRENT IMPLEMENTATION.** H:1170–1173 só possui anexosI eIII; escolhasII,IV,V usamIII. “Otimizar” não possui branch e cai em Simples. H:1159 trata34% do EBITDA positivo como Lucro Real. H:1164–1165 aplica34% à presunção para tudo; faltam bases separadas, adicionais, tributos sobre consumo e elegibilidade. Valores acima do teto continuam na última faixa. M:127 e M:317 sugerem EBITDA=lucro real e prejuízo=nenhum imposto, ambos inadequados como regra geral.

**PROPOSED IMPLEMENTATION.** MVP identificado como `SIMPLIFIED TAX ESTIMATE`, com taxas/escopo explícitos, sem botão “otimizar” enganoso. Um `DETAILED TAX MODEL` futuro exige atividade, jurisdição, elegibilidade, histórico, competência e regra versionada com vigência. Comparação tributária deverá ser ex ante entre alternativas elegíveis e períodos de opção permitidos, sem escolher retrospectivamente o menor imposto em cada mês de cada futuro. Regras 2026 e transição tributária requerem revisão própria antes da liberação.

**MATHEMATICAL RATIONALE.** Lucro tributável envolve ajustes e não se identifica automaticamente com EBITDA. IRPJ tem alíquota básica e adicional por faixa; regras CSLL têm bases próprias. [Receita Federal — IRPJ](https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/tributos/IRPJ), [Receita Federal — CSLL](https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/tributos/CSLL).

**IMPACT ON RESULTS.** Diferença potencialmente material, de sinal dependente de regime/atividade. Não corrigir somente o fator12 e afirmar que o motor fiscal está auditado.

**TEST CASE.** Anexo IV não pode retornar III silenciosamente. Regime desconhecido→erro. “Comparar” deve listar regimes elegíveis e motivo dos excluídos. `tax_rules_version`, `effective_from`, `effective_to` e fonte obrigatórios; competência fora da cobertura→aviso impeditivo no modo detalhado.

## Q13 — Breakeven é cumulativo, meta não é utilizada

**CURRENT IMPLEMENTATION.** H:1357 lê mês esperado mas não o usa. H:1404–1405 encontra primeira soma acumulada não negativa a partir de zero; isso é recuperação cumulativa, não necessariamente breakeven operacional de M:141–145, M:275–276. H:1427 calcula probabilidade até60 meses, embora a interface diga “Esperado”. Um mês1 positivo seguido de insolvência continua classificado como breakeven1.

**PROPOSED IMPLEMENTATION.** Separar: (a) `operating_breakeven_month`, primeiro mês com EBITDA≥0, explicitamente operacional e não prova de sustentabilidade; (b) `sustained_operating_breakeven_month`, primeiro mês de uma janela predefinida de três meses consecutivos com EBITDA≥0, marcada convenção do produto; (c) `cumulative_cash_recovery_month`, primeira recuperação das perdas operacionais acumuladas, com outlay inicial definido; (d) runway/insolvência, calculado com caixa inicial e financiamento. Projeção censurada no horizonte mantém `null`, não mês61 artificial. Janela incompleta no fim não comprova sustentabilidade.

**MATHEMATICAL RATIONALE.** Fluxo do período, saldo acumulado e solvência são objetos diferentes. Distribuição de tempos condicionada a ocorrência não é distribuição incondicional.

**IMPACT ON RESULTS.** Probabilidade por prazo passa a usar `count(T≤prazo)/N`, incluindo fracassos e não atingidos no denominador. P25/P50/P75 entre atingidos devem ser rotulados “condicional a atingir”; mediana incondicional é “não atingida no horizonte” quando menos da metade alcança o evento.

**TEST CASE.** Fluxos operacionais `[-100,60,60]`: operacionalmês2, recuperação cumulativamês3. Em10cenários,4 atingem até12meses,2 adicionais até24 e 4 nunca: P12=40%, P24=60%; percentis condicionais usam 6 tempos, probabilidade usa 10. Alterar meta 12→24 altera a probabilidade mostrada sem refazer draws.

## Q14 — Remoção de perdas e fracassos induz viés

**CURRENT IMPLEMENTATION.** H:1380 cria zeros por fracasso; H:1417–1419 remove zeros e negativos; H:1436–1438 persiste apenas positivos enquanto `nSim` ainda representa todos. Probabilidade superior H:1431 usa o universo completo, tornando métricas inconsistentes entre si.

**PROPOSED IMPLEMENTATION.** Guardar todos os N cenários com estado econômico e resultados por método. Separar distribuição incondicional e condicional à sobrevivência, com denominadores visíveis. EV/raw equity negativos são preservados para diagnóstico; equity realizável com piso0 pode ser derivado somente como hipótese de responsabilidade limitada, com massa em zero incluída e recovery documentado. Nenhum NaN/Inf é convertido silenciosamente em zero: sinalizar erro e não publicar resultado incompleto.

**MATHEMATICAL RATIONALE.** O filtro calcula `V|V>0`, nãoV. Piso econômico não é seleção: cenários continuam com peso1/N. Failure deve especificar encerramento/recuperação, não representar probabilidades genéricas como evidência de mercado.

**IMPACT ON RESULTS.** Medianas e caudas baixas podem cair fortemente. Para`[-100,0,0,100,200]`, mediana completa0 e média40; filtro retorna mediana150 e média150 em apenas2observações. Com equity realizável`[0,0,0,100,200]`, média60 e mediana0: diferença justificada pela hipótese econômica, não exclusão.

**TEST CASE.** Nresultados=Nsolicitado. Sucesso 0% e recovery 0 → distribuição degenerada em 0, probabilidade de alvo positivo 0, histogramas válidos; sucesso 100% não injeta fracassos exógenos. Valor negativo jamais desaparece do raw. Quantil definido por interpolação linear mantém compatibilidade com H:1127–1131 quando a amostra é a mesma.

## Q15 — Duplicação de risco, taxas e limitação de invariantes

**CURRENT IMPLEMENTATION.** Probabilidade de sucesso (H:1380) e taxas altas (H:890, H:913) coexistem sem dizer quais riscos cada uma remunera. Manual M:150–172 apresenta intervalos genéricos de sucesso, WACC e retorno como referências, sem fontes/calibração.

**PROPOSED IMPLEMENTATION.** Registrar se projeções são condicionais à sobrevivência e se taxa contém prêmio específico de failure. No modelo de mistura explícita, taxas de operação sobrevivente não devem incorporar automaticamente a mesma perda esperada outra vez. Manter presets educacionais com origem e ressalva de hipótese, nunca evidência de mercado fabricada. Não aplicar `p_success` novamente ao PV de cenários já sorteados com fracasso.

**MATHEMATICAL RATIONALE.** A mistura já produz `E[V]=p×E[V|success]+(1−p)×E[V|failure]`. Duplicar p reduz duas vezes o mesmo componente. Relações monotônicas de DCF dependem do sinal dos fluxos; um desembolso futuro negativo fica menos negativo ao aumentar taxa.

**IMPACT ON RESULTS.** Evita excesso de desconto e testes falsamente “universais”. Aumentar WACC não é garantia de reduzir PV quando fluxos assinados predominam.

**TEST CASE.** Em população conhecida com 70% a 100 e 30% a 0, média70; não49. Propriedade `higher WACC → lower/equal DCF` restrita a FCFF e terminal não negativos, constantes nas demais premissas. Contraexemplo obrigatório: único CF−100 em 1 ano, taxa 10%→−90,9091; taxa 20%→−83,3333. Maior CF sustentável com taxas/estrutura fixas e desconto positivo nunca reduz DCF.

## Q16 — Estado desatualizado e validação mascaram defeitos

**CURRENT IMPLEMENTATION.** H:1369 só recalcula caso-base quando `state.valPre` é falsy. Alterar receita, WACC ou regime após calcular pré-money mantém valor/gráfico antigo com simulação nova. H:1103 transforma campo inválido/ausente em 0. H:1476–1495 transforma estatística inexistente em 0. H:1531 divide por largura 0 quando todos os valores coincidem.

**PROPOSED IMPLEMENTATION.** Snapshot imutável e validado de inputs antes de executar. Caso-base e draws derivados do mesmo snapshot, com checksum. “Ausente”, “inválido”, “zero” e “não aplicável” são estados distintos. Histogramas degenerados mostram uma massa em um valor; eixo e legenda declaram unidade; a linha de densidade atual é histograma normalizado, não KDE independente.

**MATHEMATICAL RATIONALE.** Reprodutibilidade exige identidade de inputs, não apenas função correta. Falha numérica não é resultado econômico zero.

**IMPACT ON RESULTS.** Elimina comparação entre valuations de premissas distintas e falsa aparência de simulação válida.

**TEST CASE.** Após alterar receita, caso-base, gráficos e simulação apontam mesmo `input_hash`; recarregar resultado mantém snapshot original. Array`[100,100,100]`→3observações em um bin, densidade contínua não aplicável. Inputs NaN e campo obrigatório vazio→erro antes de enfileirar job.

## Inconsistências estatísticas que afetam o valuation

A especificação detalhada pertence a [METHODOLOGY.md](METHODOLOGY.md). Pontos auditados no código: CoV35% aplicado à média global de60 meses, criando volatilidade relativa desproporcional no ano 1 (H:1298–1305); Student-t escala não igual a desvio padrão com 5 graus de liberdade (H:1307–1311); “Triangular” com modo no máximo, não no centro (H:1313–1316); distribuição LogNormal força receita-base zero para 1 (H:1323); meses independentes; ausência de seed (H:1116–1120); truncamento em zero muda momentos (H:1336). Não é suficiente corrigir DCF/VC mantendo esse gerador sem documentar o novo processo.

Exemplo verificável: no Triangular legado com base 100, `50+100×sqrt(U)` tem média116,6666667; triangular(min50,mode100,max150) tem média100. Mudança é correção de parametrização, não calibração empírica da startup.

## PROPOSED SYSTEM

Módulos puros e testáveis: normalização de projeções/unidades → cashflow → tax adapter → DCF e VC → ponte equity/rodada → estatísticas/decisão. Nenhuma fórmula financeira em UI, routes ou template PDF. Resultado explica separadamente o valor operacional, caixa/dívida, valor equity, termo da rodada e base dos targets. Target monetário sempre informa se é EV, equity pré-money ou equity pós-money e método. Comparações DCF/VC usam mesmo conjunto de cenários, identificando método indisponível sem esconder cenários.

Saída financeira mínima por cenário: receita e EBITDA anuais, FCFF mensal, fatores de desconto, PV explícito, terminal na data final e seu PV, EV, ponte equity, `raw_equity_value`, equity realizável, base de múltiplo, EV/equity de saída, PV VC, ownership quando aplicável, status econômico, breakeven e reason codes. Estatísticas agregadas mantêm P5/P10/P25/P50/P75/P90/P95, média, desvio, N total, N por estado e N válido por método.

## MIGRATION PLAN

1. Preservar arquivos-fonte e rotular resultados legados como não auditados; não alterar dados históricos para aparentar consistência.
2. Congelar decisões de calendário, FCFF, terminal, equity, VC, failure e tributos simplificados; registrar em contratos versionados e metodologia pública.
3. Implementar motor independente, com golden tests acima antes de conectá-lo à UI. Consolidar a fórmula VC em uma única função.
4. Manter comparações de compatibilidade somente nas partes corretas: repetição de médias mensais, conversão efetiva, desconto constante explícito, soma de despesas e percentil linear para amostra idêntica.
5. Para cada diferença intencional, associar Q01–Q16, inputs, resultado legado, resultado novo e motivo. Não calibrar novo motor para reproduzir bugs.
6. Adicionar simulação determinística seedada e testar convergência/caudas conforme METHODOLOGY; golden Monte Carlo deve congelar fixtures após motor novo, seed, versão RNG e ambiente definidos, sem inventar percentis antecipados.
7. UI e PDF consomem exclusivamente `SimulationResult` persistido. Reload e logout/login não recalculam nem mudam os números.
8. Release somente após testes matemáticos, integração, isolamento de tenants, PDF e ambiente Docker. Esta auditoria não certifica production readiness nem legislação fiscal futura.

## Critérios numéricos de aceite

Casos fechados em unidades pequenas: tolerância absoluta 1e−9; somatórios monetários/TV acima:1e−6 BRL ou relativa 1e−10, conforme teste documentado. Guardar full precision e comparar antes da formatação. Seed idêntica e inputs/modelo/contagem/ambiente idênticos devem gerar exatamente os mesmos arrays; portabilidade entre versões numéricas não deve ser prometida sem replay validado. Testes estatísticos usam tolerâncias fundamentadas em erro Monte Carlo, distintas da tolerância de funções determinísticas. Os números do probe não são benchmark de performance.

Fontes primárias consultadas em 22/09/2026 são vinculadas junto às afirmações; consultas fiscais constatam limites do legado e não substituem a auditoria fiscal especializada e a seleção de regras por vigência.
