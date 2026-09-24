# Parecer 09 — Tributação brasileira

Data da pesquisa: 2026-09-22. Este parecer define limites de produto e testes; não substitui apuração por contador nem opinião legal.

## CURRENT IMPLEMENTATION

O HTML trata Lucro Real como 34% do EBITDA positivo; Presumido como 34% sobre uma base de 8/16/32% da receita; Simples com apenas tabelas dos anexos I e III, usando III como fallback para II/IV/V; e “otimizar” cai no mesmo caminho do Simples. `calcImposto` retorna imposto mensal no Simples, mas os callers dividem por 12 novamente. No cálculo pré-money, EBITDA anual é parcial durante cada ano. Não há PIS/Cofins, ISS/ICMS, CPP, adicional IRPJ, fator R, bases trimestrais, créditos, compensações/prejuízo, elegibilidade ou vigência.

## Decisão de produto

Release inicial oferece `simplified_tax_estimate`, não `detailed_tax_model`. O usuário escolhe política e informa alíquota efetiva por período ou usa tabela oficial versionada somente quando todos os dados mínimos existem. Breakdown separa tributos sobre receita e sobre lucro para não subtrair duas vezes. “Otimizar regime” é removido até um motor completo comparar elegibilidade, todos os tributos, efeitos de crédito e custos de conformidade.

## Simples Nacional

A alíquota efetiva usa `((RBT12 × alíquota nominal) − parcela a deduzir) / RBT12`; imposto do período aplica essa alíquota à receita do próprio período. RBT12 são os doze meses anteriores, com regra própria para início de atividade. O anexo depende de atividade; serviços podem depender de fator R e CPP/ISS. Não escolher anexo por label genérico. Limite, sublimites e excesso exigem contexto de estado/município e data.

Fonte oficial: [Resolução CGSN 140/2018, texto atualizado](https://normas.receita.fazenda.gov.br/sijut2consulta/link.action?idAto=92278&naoPublicado=&visao=original) e [LC 123 compilada](https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp123.htm).

## Presumido e Real

No Presumido, percentuais de presunção variam por atividade e IRPJ/CSLL têm bases/regras próprias; IRPJ é 15% com adicional de 10% sobre a parcela aplicável acima do limite legal. PIS/Cofins e tributos de consumo/serviço não cabem no atalho `base×34%`. A partir de 2026 há mudanças nos percentuais para parcela de receita acima de limiar, com datas distintas para IRPJ e CSLL; logo regras precisam de vigência e versão. Fonte: [Receita, perguntas e respostas 2026](https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/perguntas-e-respostas/beneficios-fiscais/perguntas-e-respostas-reducao-dos-incentivos-e-beneficios-tributarios.pdf/%40%40download/file) e [IN RFB 1700 atualizada](https://normas.receita.fazenda.gov.br/sijut2consulta/link.action?idAto=81268).

No Real, base é lucro fiscal ajustado, não EBITDA. D&A, despesas indedutíveis, prejuízo fiscal/CSLL, adicional IRPJ, periodicidade e estimativas precisam ser modelados. Sem livro fiscal, permitir somente proxy rotulada e alíquota efetiva informada. Fonte de alíquota/adicional: [Receita Federal — IRPJ](https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/tributos/IRPJ).

## Reforma do consumo

Projeções de cinco anos cruzam a transição CBS/IBS. Em 2026 há ano-teste e obrigações; PIS/Cofins mudam a partir de 2027 e ICMS/ISS transitam até 2033. Simples recebe regras específicas a partir de 2027. Um motor com uma tabela eterna produz precisão falsa. Fontes: [Receita — transição](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/acoes-e-programas/programas-e-atividades/reforma-tributaria-do-consumo/entenda), [orientações 2026](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/acoes-e-programas/programas-e-atividades/reforma-tributaria-do-consumo/orientacoes-2026) e [LC 214/2025 compilada](https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp214.htm).

## Contrato de regras

Cada `TaxPolicy` registra `jurisdiction`, `version`, `effective_from`, `effective_to`, `source_urls`, regime, granularidade, inputs necessários, fórmulas, rounding e limitações. Engine seleciona por data do mês projetado; lacuna de vigência falha com mensagem. Resultado retorna receita/base, alíquota nominal/efetiva, componentes, total e warnings. Mudança de regra incrementa `tax_version`; não altera simulação antiga.

## UX

Simple: “Estimativa tributária simplificada” com alíquota efetiva por receita e/ou lucro, fonte e aviso. Professional: regime, atividade/CNAE informativo, anexo/fator R quando suportado, localização, RBT12 inicial, folha12, periodicidade e políticas por vigência. A interface não diz “melhor regime”. Caso não suportado orienta validar com contador e permite input manual auditável.

## Testes mínimos

1. Receita anual120 mil/anexo III primeira faixa: total anual7.200, mensal600 sob hipótese uniforme; legado gera50/mês após dupla divisão.
2. RBT12 cruza faixa no mês: alíquota do período muda sem recalcular meses anteriores.
3. Início de atividade anualiza conforme regra oficial; RBT12 zero não divide por zero.
4. Anexos II/IV/V nunca usam III como fallback.
5. “otimizar” legado deve ser rejeitado/importado como não suportado.
6. Lucro fiscal negativo não implica que todos os tributos sejam zero; tributos sobre receita ficam separados.
7. IRPJ adicional testa limiar e período; bases IRPJ/CSLL não são forçadas iguais.
8. Projeção 2026–2030 seleciona versões por mês e expõe lacunas CBS/IBS.
9. Imposto nunca recebe EBITDA parcial por acidente; períodos reconciliam total anual.
10. Golden cases vêm de exemplos oficiais e são revisados a cada atualização normativa.

## Gate

Não vender detailed tax ou regime optimization até revisão de contador brasileiro, matriz completa por atividade/localidade/vigência e testes independentes. No MVP, precisão honesta vale mais que automatização incompleta.

