import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "@/components/icons";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

export const metadata: Metadata = { title: "Metodologia" };

const contents = [
  ["01", "Princípios"], ["02", "DCF"], ["03", "VC Method"], ["04", "Monte Carlo"],
  ["05", "Falha e caudas"], ["06", "Drivers"], ["07", "Incerteza"], ["08", "Limitações"],
];

export default function MethodologyPage() {
  return (
    <>
      <SiteHeader />
      <main id="main-content" className="methodology-page">
        <header className="methodology-hero section-grid">
          <div className="container">
            <p className="eyebrow"><span /> METODOLOGIA PÚBLICA · MODELO 3.0.0-DRAFT</p>
            <h1>Rigor que pode ser<br /><em>explicado e auditado.</em></h1>
            <p>Como o StartupValue transforma premissas financeiras em distribuições de valuation, sem esconder incerteza ou apresentar estimativas como verdades objetivas.</p>
            <div className="method-meta"><span>ÚLTIMA REVISÃO<br /><strong>22 SET 2026</strong></span><span>STATUS<br /><strong>PROPOSTA AUDITADA</strong></span><span>ESCOPO<br /><strong>DCF · VC · MONTE CARLO</strong></span></div>
          </div>
        </header>
        <div className="container methodology-layout">
          <aside className="methodology-toc" aria-label="Nesta página"><p>NESTA PÁGINA</p>{contents.map(([number, label]) => <a key={number} href={`#m-${number}`}>{number} <span>{label}</span></a>)}</aside>
          <article className="methodology-content">
            <section id="m-01"><p className="section-index">01 — PRINCÍPIOS</p><h2>O que estimamos</h2><p className="lead">O StartupValue estima uma distribuição de valores condicionada às projeções, premissas e mecanismos declarados pelo usuário.</p><p>Uma frequência observada nos cenários simulados não é uma probabilidade objetiva de mercado. Cada resultado identifica método, base de valor, moeda, data-base, horizonte, população, versão do modelo, seed e número de simulações.</p><div className="principle-grid"><div><strong>Premissas visíveis</strong><span>Defaults, unidades e origens aparecem na revisão e no relatório.</span></div><div><strong>Resultados reproduzíveis</strong><span>Mesmos inputs, versão, seed e contagem produzem o mesmo resultado.</span></div><div><strong>Bases separadas</strong><span>Enterprise value, equity, pre-money e post-money nunca são misturados.</span></div><div><strong>Incerteza preservada</strong><span>Falhas, zeros e valores negativos não desaparecem para melhorar o gráfico.</span></div></div></section>
            <section id="m-02"><p className="section-index">02 — FLUXO DE CAIXA DESCONTADO</p><h2>DCF</h2><p>O DCF traz fluxos de caixa livres da firma ao valor presente usando uma taxa consistente com o período. O valor terminal é calculado apenas quando o crescimento terminal é menor que a taxa de desconto.</p><div className="formula"><span>Enterprise Value</span><strong>EV = Σ FCFF<sub>t</sub> / (1 + r)<sup>t</sup> + TV / (1 + r)<sup>T</sup></strong></div><p>O contrato financeiro usa <code>FCFF = EBIT − impostos operacionais + D&amp;A − CAPEX − ΔNWC</code>. Caixa e dívida entram depois, na ponte entre enterprise value e equity value. Aportes não são fluxo operacional.</p><div className="method-callout"><strong>VALIDAÇÃO OBRIGATÓRIA</strong><p>Se <code>g ≥ WACC terminal</code>, o modelo rejeita a análise. Não há ajuste silencioso.</p></div></section>
            <section id="m-03"><p className="section-index">03 — VENTURE CAPITAL METHOD</p><h2>VC Method</h2><p>O método parte de um valor futuro de saída, desconta pelo retorno-alvo do investidor e reconcilia investimento, participação requerida, post-money e pre-money.</p><div className="equation-list"><div><span>01</span><p><b>Future Exit Value</b> = métrica de saída × múltiplo</p></div><div><span>02</span><p><b>PV Exit Value</b> = exit value / (1 + retorno alvo)<sup>horizonte</sup></p></div><div><span>03</span><p><b>Required Ownership</b> = valor futuro requerido do aporte / exit equity value</p></div><div><span>04</span><p><b>Pre-money</b> = post-money − investimento</p></div></div><p>O método só produz uma base pre-money ou post-money quando existe um aporte explícito e uma reconciliação coerente. Rótulos não substituem a matemática da rodada.</p></section>
            <section id="m-04"><p className="section-index">04 — MONTE CARLO</p><h2>Possíveis trajetórias, não ruído mensal</h2><p>Cada execução usa um gerador aleatório com seed registrada. Choques persistentes e parâmetros por cenário evitam tratar 60 meses como observações independentes economicamente absurdas.</p><div className="simulation-flow" aria-label="Fluxo de uma simulação"><div><span>01</span><b>Snapshot de inputs</b></div><i /><div><span>02</span><b>Seed + modelo</b></div><i /><div><span>03</span><b>Trajetórias</b></div><i /><div><span>04</span><b>Resultado imutável</b></div></div><p>Distribuições suportadas exigem parâmetros e domínio válidos. Normal e Student-t podem modelar choques; triangular e uniforme expressam limites informados; lognormal é usada somente em variáveis estritamente positivas. “Linear” descreve uma trajetória, não uma distribuição.</p></section>
            <section id="m-05"><p className="section-index">05 — FAILURE E CAUDAS</p><h2>Resultados adversos permanecem visíveis</h2><p>Estados de sucesso operacional, baixo crescimento, distress e failure são parte da população. A amostra incondicional preserva massa de falha, zero e equity negativo quando a base econômica permitir.</p><blockquote>Filtrar <code>x &gt; 0</code> altera percentis, dispersão e probabilidade de meta. O modelo não usa esse atalho.</blockquote><p>Quando a responsabilidade limitada for aplicada, o piso zero pertence a uma base identificada separadamente. Não substitui o equity assinado sem comunicação.</p></section>
            <section id="m-06"><p className="section-index">06 — DRIVERS E SENSIBILIDADE</p><h2>Associação não é causalidade</h2><p>Drivers podem usar correlação de Spearman entre premissas sorteadas e valuation dentro da população indicada. O sinal e a intensidade descrevem associação no modelo. Variáveis constantes são omitidas.</p><p>A análise tornado é uma pergunta diferente: mede o efeito de perturbar uma premissa por vez, mantendo as demais fixas. Target hit vs. miss compara P25, mediana e P75 dos inputs nos subconjuntos, sempre com o tamanho da amostra.</p></section>
            <section id="m-07"><p className="section-index">07 — INCERTEZA</p><h2>Dispersão com medida publicada</h2><p>A interface exibe P10, P25, P50, P75 e P90, além de P5/P95 e estatísticas complementares. O intervalo P25–P75 contém a metade central da amostra; não é um intervalo de confiança nem um piso de negociação.</p><div className="formula"><span>Dispersão relativa central</span><strong>IQR / |P50| = (P75 − P25) / |P50|</strong></div><p>Quando P50 é zero ou próximo de zero, a razão fica indisponível e a dispersão absoluta é exibida. Rótulos qualitativos só podem existir com faixas publicadas e versionadas.</p></section>
            <section id="m-08"><p className="section-index">08 — LIMITAÇÕES</p><h2>O que o resultado não afirma</h2><ul className="limitations"><li>Não garante preço de rodada, saída ou realização do valuation.</li><li>Não substitui due diligence financeira, jurídica, fiscal ou de mercado.</li><li>Mais simulações reduzem erro numérico; não corrigem inputs ruins.</li><li>DCF e VC Method respondem perguntas distintas e não têm hierarquia universal.</li><li>Estimativas tributárias simplificadas não são planejamento tributário.</li></ul><div className="method-cta"><p>Pronto para construir uma tese com premissas explícitas?</p><Link className="button button-primary" href="/signup">Começar análise <ArrowRight /></Link></div></section>
          </article>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
