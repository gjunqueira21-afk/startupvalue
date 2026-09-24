# Parecer 04 — Creative Developer e 3D

## Conceito

O hero representa 10.000 futuros como pontos discretos. No estado inicial, partículas ocupam trajetórias levemente divergentes em profundidade; ao rolar/pausar, convergem em uma distribuição horizontal e revelam P10/P25/P50/P75/P90. O movimento comunica amostragem e concentração, sem roleta, moedas, foguetes ou estética cripto. Texto e CTA permanecem dominantes.

React Three Fiber carrega em chunk separado somente após LCP, `IntersectionObserver`, idle e capacidade mínima. Um canvas, geometria/positions em buffer e shader simples; sem milhares de meshes/React nodes. DPR limitado, antialias condicionado, pause quando tab/hero sai da viewport e dispose completo. Mouse altera câmera em poucos graus com spring; não muda dados ou percentis.

## Estados

- Static: SVG/Canvas 2D com densidade e percentis, entregue no HTML inicial.
- Enhanced: WebGL substitui o fallback sem layout shift.
- Reduced motion: imagem/gradiente de pontos estático e labels.
- Mobile/low power/WebGL failure: fallback 2D permanente.
- Loading: fallback continua visível; não exibir spinner bloqueante.

Na simulação autenticada, a mesma linguagem visual pode mostrar partículas agregando apenas com `completed/total` recebido do backend. O contador nunca avança por timer decorativo. Se o job pausar/falhar, a animação para e o erro oferece retomada; reload recupera estado. Finalização só aparece após `SimulationResult` persistido.

## Performance budget proposto

O chunk 3D não participa do bundle crítico; conteúdo e CTA são usáveis sem JS/WebGL. Alvo inicial a validar: <=180 KB gzip de JS adicional da experiência, <=1 draw call principal, <=12 MB de buffers/texturas, 60 fps desktop médio e 30 fps mobile compatível, sem regressão material de LCP/INP. Esses números são budgets de engenharia, não benchmark realizado.

## Acessibilidade

Canvas é decorativo (`aria-hidden`) e não recebe foco. O conceito equivalente aparece em texto: “10.000 cenários formam uma distribuição de valuation entre P10 e P90”. Percentis reais nunca dependem do canvas. Cor tem labels/posição; contraste e zoom não são afetados. Usuário pode pausar animação quando houver movimento contínuo.

## Gate

Testar sem WebGL, reduced motion, Safari/iOS, Android intermediário, resize, background tab, memória após navegação e interação teclado. Reprovar se canvas bloquear CTA/FCP, causar scroll horizontal, usar progresso falso, ou sugerir que partículas são dados reais na landing ilustrativa.

