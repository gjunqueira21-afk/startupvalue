# Parecer 10 — Data Science e Sensitivity

## Decisão

O primeiro release usa três análises distintas, com nomes e interpretações separados:

1. Drivers Monte Carlo: correlação de Spearman entre inputs realizados e valuation, sobre a mesma população e base.
2. Tornado: perturbação determinística low/high mantendo demais premissas, declarada ceteris paribus.
3. Target hit/miss: estatísticas condicionais P25/P50/P75 dos inputs nos grupos que atingem ou não a meta.

Nenhuma delas demonstra causalidade. Não somar `|rho|` como percentual de importância, não usar `rho²` como variância explicada e não chamar tornado de probabilidade.

## CURRENT SYSTEM

O legado não guarda inputs realizados por cenário, varia basicamente receita, elimina valores não positivos e não calcula drivers. Isso impede análise multivariada válida e faria qualquer ranking refletir seleção dos vencedores. Não há target livre nem comparação condicional.

## Contrato

Cada sample persistido contém fatores exógenos realizados, métricas derivadas relevantes, estado econômico e valuations por base. Spearman usa ranks médios para empates, retorna rho, n, população, método/base e status. Variável constante ou grupo insuficiente retorna `null` com motivo. Ordenação é `abs(rho)` com desempate estável; sinal e unidade permanecem visíveis.

Receita Y5, crescimento e margem podem ser derivados do mesmo fator; interface identifica redundância e não conta três vezes como explicações independentes. Failure state pode aparecer como variável categórica/binária associada ao resultado; a probabilidade fixa de failure não é driver se não varia entre samples.

Target T define `hit = valuation >= T` sobre todos os N cenários. Resultado inclui hits/N, Wilson 95% para erro Monte Carlo e, por input, P25/P50/P75 em hit e miss, diferenças de medianas, contagens e missing. Grupo vazio não recebe números substitutos; narrativa pode ser suprimida para grupo pequeno, sempre mostrando dados e limite.

Tornado reavalia o motor puro nos endpoints definidos pelo usuário ou quantis da distribuição do input. Endpoints, baseline e restrições ficam no artefato. Inputs dependentes exigem cenário conjunto coerente ou warning de quebra da dependência.

## Métodos futuros

Regressão padronizada e correlação parcial só entram após diagnóstico de não linearidade, multicolinearidade, heterocedasticidade e interações. Sobol clássico exige inputs independentes; com cópula/dependências, usar método apropriado ou não publicar. Variance-based sensitivity deve reportar estimador, erro e custo, sem rótulo genérico de “causal”.

Reverse valuation usa busca limitada dentro de faixas econômicas fornecidas, common random numbers para comparar candidatos e amostra de validação independente. O solver retorna combinações matematicamente compatíveis, não metas comerciais garantidas.

## Testes

- Relação monotônica perfeita crescente/decrescente produz rho ±1; constante produz null.
- Permutar ordem dos samples não altera resultados.
- Empates usam ranks médios e não causam NaN silencioso.
- Target abaixo/acima de todos produz grupo vazio tratado.
- Target sobre massa zero usa `>=` conforme contrato.
- Excluir failures deve falhar teste de denominador.
- Tornado com WACC maior e fluxos/terminal não negativos não eleva DCF; domínio assinado não recebe invariante universal.
- Narrativa contém somente variáveis/números presentes no artefato e sempre usa “associação”.

## Gate

Não publicar ranking enquanto samples realizados não forem persistidos e reconciliados com N. Não publicar Sobol, causalidade ou “X explica Y%” no MVP.

