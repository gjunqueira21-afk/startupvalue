import Link from "next/link";
import { ArrowRight, ArrowUpRight, Check } from "@/components/icons";
import { FuturesFallback } from "@/components/landing/futures-fallback";
import { buildFuturesSummary } from "@/components/landing/futures-model";
import { HeroVisual } from "@/components/landing/hero-visual";
import { PricingCards } from "@/components/landing/pricing-cards";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

// Illustrative, deterministic 10.000-scenario run (seed 471829), computed once on the server.
const futuresSummary = buildFuturesSummary();

const steps = [
  ["01", "Descreva sua empresa", "Contexto, estágio e modelo de negócio."],
  ["02", "Defina suas premissas", "Receita, operação, retorno e incerteza."],
  ["03", "Simule milhares de futuros", "Trajetórias reproduzíveis, com seed e versão."],
  ["04", "Analise distribuição e risco", "Percentis, caudas e breakeven no horizonte."],
  ["05", "Entenda o que move o valor", "Drivers e sensibilidade sem confundir associação com causa."],
  ["06", "Gere um relatório profissional", "Uma fonte de dados para dashboard e PDF."],
];

const methods = [
  ["01 / DCF", "Fluxo de Caixa Descontado", "Projeta fluxos de caixa livres e os traz a valor presente. Taxa, crescimento terminal e base de valor ficam explícitos."],
  ["02 / VC", "Venture Capital Method", "Conecta valor de saída, retorno-alvo, horizonte, investimento e participação requerida em uma reconciliação auditável."],
  ["03 / MC", "Monte Carlo", "Substitui a falsa precisão de um caso único por milhares de trajetórias condicionadas às premissas informadas."],
];

export default function HomePage() {
  return (
    <>
      <SiteHeader />
      <main id="main-content">
        <section className="hero section-grid">
          <div className="hero-stage">
            <HeroVisual summary={futuresSummary} fallback={<FuturesFallback summary={futuresSummary} />} />
            <div className="hero-scroll-cue" aria-hidden="true"><span>SCROLL</span><i /></div>
          </div>
          <div className="container hero-copy">
            <p className="eyebrow"><span /> VALUATION INTELIGENTE PARA EMPRESAS</p>
            <h1>Não existe um único futuro para uma empresa. <em>Nós calculamos milhares deles.</em></h1>
            <p className="hero-subtitle">Descubra quanto vale a sua empresa: os números do negócio viram uma distribuição probabilística de valor, com milhares de cenários e premissas transparentes.</p>
            <div className="button-row">
              <Link className="button button-primary" href="/signup">Calcular minha empresa <ArrowUpRight /></Link>
              <Link className="button button-secondary" href="#como-funciona">Ver como funciona <ArrowRight /></Link>
            </div>
            <div className="trust-row" aria-label="Princípios do produto">
              <span><Check /> Premissas transparentes</span>
              <span><Check /> Resultados reproduzíveis</span>
              <span><Check /> Dados privados</span>
            </div>
          </div>
          <div className="container proof-strip" aria-label="Capacidades principais">
            <div><span>SIMULAÇÃO</span><strong>1k — 25k</strong><small>cenários por execução</small></div>
            <div><span>MÉTODOS</span><strong>DCF + VC</strong><small>bases separadas</small></div>
            <div><span>AUDITORIA</span><strong>Seed + versão</strong><small>rastreabilidade</small></div>
            <div><span>DECISÃO</span><strong>Target analysis</strong><small>hit vs. miss</small></div>
          </div>
        </section>

        <section className="thesis-section section-grid">
          <div className="container split-heading">
            <p className="section-index">01 — A TESE</p>
            <div>
              <h2>Um valuation não deveria ser <span>apenas um número.</span></h2>
              <p>Empresas operam sob incerteza. Receita, crescimento, margem, custos e retorno esperado não acontecem exatamente como planejado. Por isso, o QuantoVale simula milhares de futuros possíveis.</p>
            </div>
          </div>
          <div className="container thesis-comparison">
            <article className="comparison-card old-model">
              <p>MODELO CONVENCIONAL</p><span>Uma planilha. Uma premissa.</span><strong>R$ 8,4 mi</strong><small>Um número que esconde a incerteza.</small>
            </article>
            <div className="comparison-arrow" aria-hidden="true"><ArrowRight /></div>
            <article className="comparison-card new-model">
              <p>QUANTOVALE</p><span>10.000 possíveis futuros.</span>
              <div className="range-line"><i /><b /><i /></div>
              <div className="range-values"><small>P25 · R$ 6,1 mi</small><strong>P50 · R$ 8,4 mi</strong><small>P75 · R$ 11,7 mi</small></div>
            </article>
          </div>
        </section>

        <section className="how-section section-grid" id="como-funciona">
          <div className="container section-heading">
            <div><p className="section-index">02 — COMO FUNCIONA</p><h2>Da projeção à decisão,<br /><span>sem caixa-preta.</span></h2></div>
            <p>Um fluxo guiado para quem é do negócio. Controle granular para profissionais.</p>
          </div>
          <div className="container steps-grid">
            {steps.map(([number, title, text]) => <article className="step-card" key={number}><span>{number}</span><h3>{title}</h3><p>{text}</p></article>)}
          </div>
        </section>

        <section className="methods-section">
          <div className="container section-heading">
            <div><p className="section-index">03 — MÉTODOS</p><h2>Rigor financeiro.<br /><span>Incerteza explícita.</span></h2></div>
            <Link className="inline-link" href="/methodology">Conheça a metodologia <ArrowUpRight /></Link>
          </div>
          <div className="container methods-grid">
            {methods.map(([index, title, text]) => <article className="method-card" key={index}><p>{index}</p><h3>{title}</h3><div className="method-rule" /><p>{text}</p></article>)}
          </div>
        </section>

        <section className="intelligence-section section-grid">
          <div className="container intelligence-grid">
            <div className="intelligence-copy">
              <p className="section-index">04 — DECISION INTELLIGENCE</p>
              <h2>Saiba o valor.<br /><span>Entenda o porquê.</span></h2>
              <p>O resultado vai além de percentis. Identifique quais premissas apresentam maior associação com o valuation e explore o que caracteriza os cenários que atingem sua meta.</p>
              <ul className="feature-list">
                <li><Check /> Drivers calculados, nunca hardcoded</li>
                <li><Check /> Target hit vs. target miss</li>
                <li><Check /> Breakeven como distribuição</li>
                <li><Check /> DCF e VC em bases explícitas</li>
              </ul>
              <Link className="button button-secondary" href="/app/simulations/demo">Ver resultado ilustrativo <ArrowRight /></Link>
            </div>
            <div className="result-showcase" aria-label="Exemplo ilustrativo de análise">
              <div className="sample-label">EXEMPLO ILUSTRATIVO · DADOS NÃO REAIS</div>
              <div className="result-top"><span>ESTIMATIVA DE VALUATION <small>DCF · EQUITY VALUE</small></span><b>SIMULATION COMPLETE</b></div>
              <div className="result-value"><span>P50</span><strong>R$ 8,4 mi</strong><small>Mediana de 10.000 cenários</small></div>
              <div className="result-range"><div><span>DOWNSIDE · P10</span><strong>R$ 4,3 mi</strong></div><div><span>CORE RANGE · P25—P75</span><strong>R$ 6,1 mi — R$ 11,7 mi</strong></div><div><span>UPSIDE · P90</span><strong>R$ 15,2 mi</strong></div></div>
              <div className="target-card"><div><span>PROBABILIDADE DE R$ 15 MI OU MAIS</span><strong>27,4%</strong></div><div className="probability-track"><i /></div><p>2.740 de 10.000 cenários simulados atingiram ou superaram a meta.</p></div>
              <div className="drivers-mini"><span>PRINCIPAIS ASSOCIAÇÕES</span><div><b>Receita Ano 5</b><i style={{ width: "88%" }} /><strong>+0,71</strong></div><div><b>Margem EBITDA</b><i style={{ width: "72%" }} /><strong>+0,58</strong></div><div><b>WACC</b><i className="negative" style={{ width: "57%" }} /><strong>−0,46</strong></div></div>
            </div>
          </div>
        </section>

        <section className="audience-section">
          <div className="container section-heading"><div><p className="section-index">05 — PARA QUEM</p><h2>Uma linguagem comum para<br /><span>quem constrói e quem investe.</span></h2></div></div>
          <div className="container audience-grid">
            {[['Donos de empresa', 'Saiba quanto vale o seu negócio e negocie com premissas visíveis.', null], ['Investidores', 'Avalie oportunidades, risco e sensibilidade com rastreabilidade.', null], ['Contadores & Consultores', 'Entregue laudos de valuation com a sua marca, para múltiplos clientes.', 'white label'], ['Compradores & Sócios', 'Avalie aquisições, entradas e saídas de sociedade com hipóteses documentadas.', null]].map(([title, text, tag], index) => <article key={title}><span>0{index + 1}</span><h3>{title}{tag && <span className="audience-tag">{tag}</span>}</h3><p>{text}</p></article>)}
          </div>
        </section>

        <section className="pricing-section section-grid" id="planos">
          <div className="container section-heading"><div><p className="section-index">06 — PLANOS</p><h2>Comece com clareza.<br /><span>Escale com profundidade.</span></h2></div><p>Planos para cada estágio, do diagnóstico ao portfólio completo.</p></div>
          <PricingCards source="landing" />
          <p className="container pricing-note">Cobrança ainda não está ativa. Entre na lista de espera e seja avisado no lançamento — sem cartão, sem compromisso.</p>
        </section>

        <section className="faq-section">
          <div className="container faq-grid">
            <div><p className="section-index">07 — FAQ</p><h2>Perguntas<br /><span>frequentes.</span></h2></div>
            <div className="faq-list">
              <details open><summary>O QuantoVale informa o valor “correto” da empresa?</summary><p>Não. O produto estima uma distribuição condicionada às projeções, premissas e mecanismos escolhidos. O resultado apoia decisões; não é uma verdade objetiva ou garantia de preço.</p></details>
              <details><summary>Mais simulações tornam a projeção mais precisa?</summary><p>Mais cenários reduzem o erro numérico de Monte Carlo, mas não corrigem premissas econômicas inadequadas. Qualidade dos inputs e transparência do modelo continuam essenciais.</p></details>
              <details><summary>Qual a diferença entre DCF e VC Method?</summary><p>O DCF desconta fluxos futuros e valor terminal. O VC Method parte de um valor de saída e do retorno-alvo do investidor. As bases são exibidas separadamente.</p></details>
              <details><summary>Meus resultados podem ser reproduzidos?</summary><p>Sim. Resultados persistidos identificam inputs, versão do modelo, seed aleatória e número de simulações.</p></details>
              <details><summary>Posso usar o QuantoVale com meus clientes?</summary><p>Sim. Nos planos Consultor e Escritório o relatório sai com a sua marca — logo, cores e nome da sua firma — mantendo a transparência metodológica.</p></details>
              <details><summary>Quando a cobrança começa?</summary><p>No lançamento comercial. Hoje você entra na lista de espera e é avisado antes de qualquer cobrança.</p></details>
            </div>
          </div>
        </section>

        <section className="closing-cta section-grid"><div className="container"><p className="eyebrow"><span /> TRANSFORME INCERTEZA EM DECISÃO</p><h2>10.000 possíveis futuros.<br /><em>Uma decisão melhor.</em></h2><p>Construa uma análise de valuation clara, reproduzível e pronta para discussão.</p><Link className="button button-primary" href="/signup">Começar análise <ArrowUpRight /></Link></div></section>
      </main>
      <SiteFooter />
    </>
  );
}
