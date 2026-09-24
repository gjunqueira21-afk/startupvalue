# Parecer 08 — Startup e Venture Capital Valuation

## Parecer

Os inputs legados são insuficientes para chamar o resultado de equity valuation ou round model. Eles suportam apenas uma proxy operacional: receita e quatro despesas, WACC/g, múltiplo EBITDA, retorno alvo, participação e probabilidade subjetiva. Faltam COGS/margem bruta, CAPEX, D&A, capital de giro, caixa/dívida/claims, investimento efetivo, métrica/horizonte da saída e diluição futura. ARR/MRR/CAC/LTV/churn não são universalmente necessários e não devem ser impostos.

## Taxonomia e disclosure progressivo

| Grupo | Core quando aplicável | Opcional/informativo | Futuro |
|---|---|---|---|
| Perfil | estágio, setor, país, moeda, modelo, fundação | descrição, geography | benchmarks setoriais |
| Operação | receita, COGS ou margem, OPEX, CAPEX, D&A, NWC | headcount detalhado | unit economics por cohort |
| Balanço | caixa excedente, dívida, outros claims | caixa operacional mínimo | convertibles/SAFE/options |
| SaaS | receita/MRR/ARR coerentes; churn somente se usado na projeção | CAC, LTV, NRR, cohorts | motor bottom-up SaaS |
| Marketplace | receita ou GMV×take rate sem dupla contagem | buyers/sellers | cohort/liquidity model |
| Rodada | investimento ou ownership-alvo; pre/post reconciliados | funding history/current ownership | cap table/waterfall |
| Saída | horizonte, métrica anual, múltiplo, ponte EV-equity, retorno | fonte/rationale do múltiplo | comparables live |

Simple pede somente o necessário ao método e transforma respostas em campos canônicos visíveis na revisão. Professional abre granularidade, distribuições e dependências. “Não sei” cria ausência/warning ou aproximação declarada; nunca zero silencioso.

## Regras por estágio

- Pre-revenue: DCF terminal e múltiplo de receita exigem projeção altamente incerta; mostrar aplicabilidade limitada. VC pode usar saída projetada, mas precisa round size/horizon/return/dilution. EBITDA múltiplo não se aplica se EBITDA de saída <=0.
- Seed/Series A: receita recorrente e unit economics podem informar coerência, mas valuation core continua dependente do fluxo/saída explicitamente modelado.
- Growth/Late: reinvestimento, dívida, impostos e bridge EV-equity tornam-se indispensáveis; WACC/terminal precisam normalização madura.

## Validações

ARR deve reconciliar aproximadamente a 12×MRR na mesma data quando ambos são fornecidos, com exceções declaradas; receita reconhecida não é automaticamente ARR. LTV/CAC exige mesma margem, coorte e janela; não usar ratio como driver sem equação. Runway requer caixa e burn temporal compatíveis. Headcount pode ser custo monetário ou contagem×custo, nunca ambos. Gross margin e COGS são modos exclusivos. Funding history não entra como receita/FCFF.

Múltiplo identifica `revenue` ou `EBITDA`, base EV/equity e período (LTM/NTM/ano5). Retorno alvo é anual efetivo e horizonte é explícito. Required ownership = investimento/post-money; com diluição futura d, ownership retida = ownership inicial×(1-d). Pre-money = post-money−investimento; valores inviáveis geram erro/status, não percentuais truncados.

## Casos de teste

1. MRR 100 mil e ARR 1,2 mi reconciliam; ARR 2 mi gera warning, não sobrescrita.
2. GMV 10 mi×take rate10%=receita1 mi; se receita já informada, usuário escolhe fonte.
3. Pre-money4 mi+investimento1 mi=post5 mi e ownership20%; legado `pre×20%` falharia.
4. EBITDA saída negativo + múltiplo EBITDA produz “não aplicável” e mantém cenário.
5. Caixa1 mi, dívida300 mil e EV5 mi → equity5,7 mi, com classificação do caixa registrada.
6. Burn100 mil/mês, caixa1 mi e nenhum financiamento → runway10 meses sob definição declarada.

## Gate

Não liberar comparables, cap table, SAFE ou white label como botões vazios. Cada métrica mostra se é input, derivada, check de coerência ou futura. A análise deve continuar possível com poucos inputs, mas aproximações e limitações ficam no resultado/PDF.

