import { Check } from "../icons";
import { WaitlistForm, type PlanInterest } from "./waitlist-form";

export interface Plan {
  name: string;
  tagline: string;
  price: string;
  annual?: string;
  items: string[];
  featured?: boolean;
  badge?: string;
  planInterest: PlanInterest;
}

/** The four published tiers (commercial decision of 2026-10-02). */
export const PLANS: Plan[] = [
  {
    name: "Grátis",
    tagline: "Para conhecer a análise",
    price: "R$ 0",
    items: ["1 empresa", "1.000 cenários por execução", "DCF + VC Method + Monte Carlo", "Resumo em PDF com marca d'água"],
    planInterest: "free",
  },
  {
    name: "Empresário",
    tagline: "Para donos de empresa e CFOs",
    price: "R$ 97/mês",
    annual: "ou R$ 932/ano (~20% off)",
    items: ["5 empresas", "10.000 cenários por execução", "Múltiplos implícitos", "Plano para a meta", "Relatório PDF completo"],
    featured: true,
    badge: "MAIS POPULAR",
    planInterest: "empresario",
  },
  {
    name: "Consultor",
    tagline: "Para consultores, contadores e assessores",
    price: "R$ 297/mês",
    annual: "ou R$ 2.851/ano (~20% off)",
    items: ["Até 10 empresas-clientes", "25.000 cenários por execução", "Relatório white label com a sua marca", "Tudo do Empresário"],
    planInterest: "consultor",
  },
  {
    name: "Escritório",
    tagline: "Para escritórios e portfólios",
    price: "R$ 697/mês",
    annual: "ou R$ 6.691/ano (~20% off)",
    items: ["Empresas-clientes ilimitadas", "Relatório white label com a sua marca", "25.000 cenários por execução", "Multiusuário em breve"],
    planInterest: "escritorio",
  },
];

/**
 * The 4 pricing cards, shared between the landing page's `#planos` section
 * and `/pricing` so both stay in sync with a single source of truth for
 * copy and prices.
 */
export function PricingCards({ source }: { source: "landing" | "pricing" }) {
  return (
    <div className="container pricing-grid">
      {PLANS.map((plan) => (
        <article className={plan.featured ? "plan-card featured" : "plan-card"} key={plan.name}>
          {plan.badge && <div className="plan-badge">{plan.badge}</div>}
          <h3>{plan.name}</h3>
          <span>{plan.tagline}</span>
          <strong>
            {plan.price}
            {plan.annual && <small className="plan-annual">{plan.annual}</small>}
          </strong>
          <WaitlistForm plan={plan.planInterest} source={source} variant={plan.featured ? "primary" : "secondary"} />
          <ul>
            {plan.items.map((item) => (
              <li key={item}><Check />{item}</li>
            ))}
          </ul>
        </article>
      ))}
    </div>
  );
}
