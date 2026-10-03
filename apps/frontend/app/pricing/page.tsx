import type { Metadata } from "next";
import { PricingCards } from "@/components/landing/pricing-cards";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

export const metadata: Metadata = { title: "Planos" };

/**
 * Cell values beyond what the four plan cards already state verbatim
 * (empresas / cenários / white label / relatório) are read off the backend
 * entitlement matrix in `app/core/entitlements.py` (métodos, múltiplos
 * implícitos, plano para a meta are identical across tiers except Grátis;
 * Escritório inherits every Consultor feature, only unlimited empresas
 * differs) — "suporte" has no entitlement backing and is kept conservative.
 */
const comparisonRows: [string, string, string, string, string][] = [
  ["Empresas", "1 empresa", "5 empresas", "Até 10 empresas-clientes", "Empresas-clientes ilimitadas"],
  ["Cenários por execução", "1.000", "10.000", "25.000", "25.000"],
  ["Métodos", "DCF + VC + Monte Carlo", "DCF + VC + Monte Carlo", "DCF + VC + Monte Carlo", "DCF + VC + Monte Carlo"],
  ["Múltiplos implícitos", "—", "Sim", "Sim", "Sim"],
  ["Plano para a meta", "—", "Sim", "Sim", "Sim"],
  ["Relatório PDF", "Resumo com marca d'água", "Completo", "Completo", "Completo"],
  ["White label", "—", "—", "Sim", "Sim"],
  ["Suporte", "E-mail", "E-mail", "E-mail", "E-mail prioritário"],
];

export default function PricingPage() {
  return (
    <>
      <SiteHeader />
      <main id="main-content">
        <header className="methodology-hero section-grid">
          <div className="container">
            <p className="eyebrow"><span /> PLANOS QUANTOVALE</p>
            <h1>Preços publicados.<br /><em>Cobrança no lançamento.</em></h1>
            <p>Quatro planos, do diagnóstico inicial ao portfólio com a sua marca. Entre na lista de espera e seja avisado antes de qualquer cobrança — sem cartão, sem compromisso.</p>
          </div>
        </header>

        <section className="pricing-section section-grid" id="planos">
          <PricingCards source="pricing" />
          <p className="container pricing-note">Cobrança ainda não está ativa. Entre na lista de espera e seja avisado no lançamento — sem cartão, sem compromisso.</p>
        </section>

        <section className="methods-section">
          <div className="container section-heading">
            <div><p className="section-index">COMPARATIVO</p><h2>Compare<br /><span>recurso por recurso.</span></h2></div>
          </div>
          <div className="container comparison-table-wrap">
            <table className="comparison-table">
              <thead>
                <tr><th scope="col">Recurso</th><th scope="col">Grátis</th><th scope="col">Empresário</th><th scope="col">Consultor</th><th scope="col">Escritório</th></tr>
              </thead>
              <tbody>
                {comparisonRows.map(([label, free, empresario, consultor, escritorio]) => (
                  <tr key={label}><th scope="row">{label}</th><td>{free}</td><td>{empresario}</td><td>{consultor}</td><td>{escritorio}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="faq-section">
          <div className="container faq-grid">
            <div><p className="section-index">FAQ</p><h2>Perguntas<br /><span>sobre planos.</span></h2></div>
            <div className="faq-list">
              <details open><summary>Posso usar o QuantoVale com meus clientes?</summary><p>Sim. Nos planos Consultor e Escritório o relatório sai com a sua marca — logo, cores e nome da sua firma — mantendo a transparência metodológica.</p></details>
              <details><summary>Quando a cobrança começa?</summary><p>No lançamento comercial. Hoje você entra na lista de espera e é avisado antes de qualquer cobrança.</p></details>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
