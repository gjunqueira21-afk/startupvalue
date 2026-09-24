# StartupValue — Direção visual e design system

Estado: especificação. Linguagem institucional de análise, com alta densidade controlada e hierarquia editorial. Referências conceituais Bloomberg, Stripe e Linear orientam rigor e acabamento; não copiar layouts ou marcas.

## Tokens

```text
color.bg.canvas       #070A0E
color.bg.surface      #0D1218
color.bg.elevated     #141B23
color.border.default  #26313D
color.text.primary    #F3F6F8
color.text.secondary  #A6B1BD
color.text.muted      #71808F
color.brand.primary   #35E6A1
color.brand.blue      #5CA7FF
color.risk.negative   #FF6B78
color.risk.warning    #F4C15D
color.chart.dcf       #35E6A1
color.chart.vc        #5CA7FF
color.chart.revenue   #9C8CFF
color.chart.ebitda    #4ED6D0
color.chart.target    #F4C15D
color.chart.failure   #FF6B78
```

Contraste deve ser medido nas combinações reais; cores de chart usam também forma, tracejado, label ou textura. Verde não significa sempre “bom”: DCF conserva verde como identidade do método. Positivo/negativo recebe sinal e texto.

Tipografia: sans variável local para interface (Inter/Geist ou equivalente licenciada), 14–16 px base; mono local com algarismos tabulares para IDs, seeds e tabelas. Headlines landing usam sans de alto contraste, sem serif decorativa obrigatória. Escala 12/14/16/20/24/32/48/64; line-height 1.2 em títulos e 1.5 em texto. Números monetários preservam alinhamento e moeda.

Spacing 4/8/12/16/24/32/48/64; radius 6/10/14; sombra rara e curta; borda e diferença de superfície definem planos. Grid landing 12 colunas/1200 px; app 240 px sidebar + conteúdo fluido; resultados podem usar 1440 px. Densidade Simple confortável, Professional compacta, mantendo targets e legibilidade.

## Componentes

Button, IconButton, Link, Input, MoneyInput, PercentInput, Select, RadioCard, Slider, Textarea, Checkbox, Switch, FieldHelp, InlineError, Alert, Toast, Card, Metric, Badge, Tooltip, Drawer, Modal, Tabs, Stepper, Table, DataTable, ChartCard, EmptyState, Skeleton, Progress, CommandMenu e Breadcrumb. Cada um tem default/hover/focus/active/disabled/loading/error e especificação teclado.

RadioCard usa controle nativo oculto visualmente, não `div onclick`. Ícones finais são SVG de um conjunto coerente; emoji só pode aparecer em conteúdo editorial deliberado. Tooltip não contém informação essencial exclusiva. Modal não é usado para tarefas longas; Drawer preserva contexto de metodologia.

## Hierarquia

Landing: texto principal e CTA ocupam primeiro plano; visual 3D serve à tese e nunca compete com a headline. App: título contextual, metadata auditável, ação primária única. Resultados: P50 e core range primeiro, target probability e incerteza depois; métodos/base sempre visíveis. Cards evitam arco-íris decorativo; acentos vêm do significado dos dados.

## Charts

Todos os gráficos recebem título declarativo, base/método, unidade, legenda direta, tooltip estável, marcadores e alternativa tabular. Histograma preserva massa zero/failure. Percentis usam linhas rotuladas P10/P25/P50/P75/P90; P50 tem maior peso, P25–P75 faixa suave. CDF usa eixo 0–100%; box plot não oculta extremos. Tornado usa eixo de mudança, baseline zero e duas tonalidades por direção. Spearman usa barras divergentes, escala -1 a 1 e texto “associação”.

Sem curvas suavizadas que pareçam dados adicionais. Sem 3D em gráficos analíticos. Paleta de impressão mantém distinção em tons de cinza por dash/padrão. Valores completos ficam em tooltip/tabela; abreviação R$ 8,4 mi é locale-aware.

## Motion e 3D

Motion 120–240 ms para estado, easing suave; entrada de página discreta. Contadores não atrasam leitura nem fingem progresso. Reduced motion desliga transforms e partículas. Hero 3D é lazy, não bloqueia LCP, tem fallback estático e pausa fora da viewport. Na simulação autenticada, visual responde somente ao progresso real do job.

## Responsive e acessibilidade

Breakpoints orientados por conteúdo: 480/768/1024/1280. Mobile prioriza landing, auth, overview, resumo e preview; análise detalhada oferece scroll local explícito. Sem overflow global. Sidebar vira drawer; metric grid 1–2 colunas; stepper anuncia etapa atual. Focus ring de 2 px com contraste; mínimo WCAG 2.2 AA; touch target mínimo 44 px preferencialmente, nunca abaixo do requisito AA.

## PDF

Compartilha tokens sem replicar a tela escura. Fundo branco, texto #111827, blue/green mais escuros para impressão, grid A4 e cabeçalho/rodapé discretos. Cada figura tem caption, fonte “StartupValue SimulationResult”, método/base e unidade. Cover e executive summary têm mais espaço; appendix aceita densidade maior. Nenhum elemento interativo vira botão impresso.

## Migração e gate

Preservar o legado somente como evidência. Construir tokens e primitivas antes de telas. Validar uma página landing, um step complexo, resultados e uma página PDF como vertical slice. Gate: sem emoji como iconografia, gradiente decorativo excessivo, glassmorphism, texto cinza de baixo contraste, chart sem tabela, número sem base/unidade, ou WebGL no caminho crítico.

