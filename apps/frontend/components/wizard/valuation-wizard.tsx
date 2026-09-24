"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ApiError } from "@/lib/api/client";
import { createSimulation } from "@/lib/api/simulations";
import { DEFAULT_DRAFT, DRAFT_STORAGE_KEY, UNCERTAINTY_PRESETS, freshDraft } from "./defaults";
import { RevenueChart } from "./revenue-chart";
import type {
  CompanyInputs,
  MonteCarloAssumptions,
  OperatingCostKey,
  StartupMetrics,
  ValuationAssumptions,
  ValuationWizardDraft,
  ValidationErrors,
  WizardMode,
  WizardStep,
} from "./types";
import { validateAll, validateStep } from "./validation";
import styles from "./valuation-wizard.module.css";

const STEPS = [
  ["Empresa", "Identidade e estágio"],
  ["Receita", "Projeção de 5 anos"],
  ["Custos", "Estrutura operacional"],
  ["Métricas", "Indicadores da startup"],
  ["Valuation", "Premissas dos métodos"],
  ["Monte Carlo", "Incerteza e seed"],
  ["Revisão", "Auditoria antes da execução"],
] as const;

const STEP_DESCRIPTIONS = [
  "Comece pelo contexto do negócio. Essas informações organizam a análise e ajudam a apresentar o resultado.",
  "Projete a receita sem esconder a unidade. O gráfico responde aos valores informados, sem executar valuation no navegador.",
  "Informe custos operacionais e CAPEX anuais. Sem projeção de custos por ano, o modelo mantém esses valores nominais constantes durante os cinco anos.",
  "Informe a margem bruta usada no DCF. Os demais indicadores são opcionais e contextualizam a empresa.",
  "Defina as premissas que ligam os fluxos projetados ao valor econômico da empresa.",
  "Configure a amostra probabilística. Seed, quantidade de cenários e premissas serão registradas para reprodução.",
  "Confira as premissas antes de enviar. O backend calcula os fluxos, o valuation e os resultados persistidos.",
] as const;

const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const integer = new Intl.NumberFormat("pt-BR");

interface NumberFieldProps {
  id: string;
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
  error?: string;
  suffix?: string;
  hint?: string;
  min?: number;
  max?: number;
  step?: number;
  optional?: boolean;
}

function NumberField({ id, label, value, onChange, error, suffix, hint, min, max, step = 1, optional }: NumberFieldProps) {
  return (
    <div className={styles.field}>
      <label htmlFor={id}>{label} {optional && <span>· opcional</span>}</label>
      <input
        id={id}
        type="number"
        inputMode="decimal"
        min={min}
        max={max}
        step={step}
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value === "" ? null : Number(event.target.value))}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
      />
      {suffix && <small>{suffix}</small>}
      {hint && !error && <small id={`${id}-hint`}>{hint}</small>}
      {error && <span className={styles.error} id={`${id}-error`}>{error}</span>}
    </div>
  );
}

function ReviewCard({ title, onEdit, children, wide = false }: { title: string; onEdit: () => void; children: React.ReactNode; wide?: boolean }) {
  return (
    <article className={`${styles.reviewCard} ${wide ? styles.reviewCardWide : ""}`}>
      <header><h3>{title}</h3><button type="button" onClick={onEdit}>EDITAR</button></header>
      <dl>{children}</dl>
    </article>
  );
}

function Entry({ label, value }: { label: string; value: React.ReactNode }) {
  return <><dt>{label}</dt><dd>{value}</dd></>;
}

export function ValuationWizard({ context = "company" }: { context?: "company" | "scenario" }) {
  const [draft, setDraft] = useState<ValuationWizardDraft>(() => freshDraft());
  const [step, setStep] = useState<WizardStep>(0);
  const [maxVisited, setMaxVisited] = useState<WizardStep>(0);
  const [errors, setErrors] = useState<ValidationErrors>({});
  const [hydrated, setHydrated] = useState(false);
  const [saveState, setSaveState] = useState("Carregando rascunho…");
  const [submission, setSubmission] = useState<
    | { kind: "idle" }
    | { kind: "loading" }
    | { kind: "success"; simulationId: string; status: string; resultHash: string | null }
    | { kind: "error"; message: string }
  >({ kind: "idle" });

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(DRAFT_STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as Partial<ValuationWizardDraft>;
        if (parsed.schemaVersion === 1) setDraft(parsed as ValuationWizardDraft);
      }
      setSaveState(stored ? "Rascunho recuperado neste dispositivo" : "Novo rascunho local");
    } catch {
      setSaveState("Rascunho anterior não pôde ser lido");
    } finally {
      setHydrated(true);
    }
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    setSaveState("Salvando alterações…");
    const timer = window.setTimeout(() => {
      const next = { ...draft, updatedAt: new Date().toISOString() };
      window.localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(next));
      setSaveState(`Rascunho salvo às ${new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`);
    }, 450);
    return () => window.clearTimeout(timer);
  }, [draft, hydrated]);

  const totalAnnualCosts = useMemo(
    () => Object.entries(draft.operatingCosts).filter(([key]) => key !== "capex").reduce((sum, [, value]) => sum + value, 0),
    [draft.operatingCosts],
  );

  const updateCompany = <K extends keyof CompanyInputs>(key: K, value: CompanyInputs[K]) => {
    setDraft((current) => ({ ...current, company: { ...current.company, [key]: value } }));
  };
  const updateMetric = <K extends keyof StartupMetrics>(key: K, value: StartupMetrics[K]) => {
    setDraft((current) => ({ ...current, metrics: { ...current.metrics, [key]: value } }));
  };
  const updateValuation = <K extends keyof ValuationAssumptions>(key: K, value: ValuationAssumptions[K]) => {
    setDraft((current) => ({ ...current, valuation: { ...current.valuation, [key]: value } }));
  };
  const updateMonteCarlo = <K extends keyof MonteCarloAssumptions>(key: K, value: MonteCarloAssumptions[K]) => {
    setDraft((current) => ({ ...current, monteCarlo: { ...current.monteCarlo, [key]: value } }));
  };
  const updateCost = (key: OperatingCostKey, value: number) => {
    setDraft((current) => ({ ...current, operatingCosts: { ...current.operatingCosts, [key]: value } }));
  };

  const changeMode = (mode: WizardMode) => setDraft((current) => ({ ...current, mode }));

  const selectUncertainty = (level: "low" | "medium" | "high") => {
    setDraft((current) => ({
      ...current,
      monteCarlo: { ...current.monteCarlo, uncertaintyLevel: level, ...UNCERTAINTY_PRESETS[level] },
    }));
  };

  const goToStep = (target: WizardStep) => {
    if (target <= maxVisited || target < step) {
      setStep(target);
      setErrors({});
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  const nextStep = () => {
    const nextErrors = validateStep(draft, step);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    const target = Math.min(step + 1, 6) as WizardStep;
    setStep(target);
    setMaxVisited((current) => Math.max(current, target) as WizardStep);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const resetDraft = () => {
    if (!window.confirm("Descartar os dados deste rascunho neste dispositivo?")) return;
    window.localStorage.removeItem(DRAFT_STORAGE_KEY);
    setDraft(freshDraft());
    setStep(0);
    setMaxVisited(0);
    setErrors({});
    setSubmission({ kind: "idle" });
  };

  const submit = async () => {
    const allErrors = validateAll(draft);
    setErrors(allErrors);
    if (Object.keys(allErrors).length > 0) {
      const firstInvalid = ([0, 1, 2, 3, 4, 5] as WizardStep[]).find((candidate) => Object.keys(validateStep(draft, candidate)).length > 0);
      if (firstInvalid !== undefined) setStep(firstInvalid);
      return;
    }
    setSubmission({ kind: "loading" });
    try {
      const result = await createSimulation(draft);
      setSubmission({
        kind: "success",
        simulationId: result.simulation_id,
        status: result.status,
        resultHash: result.result_hash,
      });
    } catch (error) {
      const message = error instanceof ApiError
        ? `${error.message} O rascunho permanece salvo. Código HTTP: ${error.status}.`
        : "O backend não respondeu. O rascunho permanece salvo neste dispositivo.";
      setSubmission({ kind: "error", message });
    }
  };

  const panel = renderStep();

  function renderStep() {
    if (step === 0) return (
      <div className={styles.grid2}>
        <div className={styles.field}><label htmlFor="company-name">Nome da empresa</label><input id="company-name" value={draft.company.name} onChange={(event) => updateCompany("name", event.target.value)} aria-invalid={Boolean(errors["company.name"])} />{errors["company.name"] && <span className={styles.error}>{errors["company.name"]}</span>}</div>
        <div className={styles.field}><label htmlFor="scenario-name">Nome do cenário</label><input id="scenario-name" value={draft.company.scenarioName} onChange={(event) => updateCompany("scenarioName", event.target.value)} aria-invalid={Boolean(errors["company.scenarioName"])} />{errors["company.scenarioName"] && <span className={styles.error}>{errors["company.scenarioName"]}</span>}</div>
        <div className={styles.field}><label htmlFor="sector">Setor</label><input id="sector" placeholder="Ex.: Fintech, Healthtech" value={draft.company.sector} onChange={(event) => updateCompany("sector", event.target.value)} aria-invalid={Boolean(errors["company.sector"])} />{errors["company.sector"] && <span className={styles.error}>{errors["company.sector"]}</span>}</div>
        <div className={styles.field}><label htmlFor="country">País</label><input id="country" value={draft.company.country} onChange={(event) => updateCompany("country", event.target.value)} /></div>
        <div className={styles.field}><label htmlFor="business-model">Modelo de negócio</label><select id="business-model" value={draft.company.businessModel} onChange={(event) => updateCompany("businessModel", event.target.value as CompanyInputs["businessModel"])}><option value="saas">SaaS / assinatura</option><option value="marketplace">Marketplace</option><option value="transactional">Transacional</option><option value="ecommerce">E-commerce</option><option value="services">Serviços</option><option value="other">Outro</option></select></div>
        <div className={styles.field}><label htmlFor="stage">Estágio</label><select id="stage" value={draft.company.stage} onChange={(event) => updateCompany("stage", event.target.value as CompanyInputs["stage"])}><option value="pre_revenue">Pre-Revenue</option><option value="seed">Seed</option><option value="series_a">Series A</option><option value="growth">Growth</option><option value="late_stage">Late Stage</option></select></div>
        <NumberField id="founding-year" label="Ano de fundação" value={draft.company.foundingYear} onChange={(value) => updateCompany("foundingYear", value ?? new Date().getFullYear())} min={1900} max={new Date().getFullYear()} error={errors["company.foundingYear"]} />
      </div>
    );

    if (step === 1) return (
      <>
        <div className={styles.segment} aria-label="Periodicidade da receita">
          <button type="button" className={draft.revenue.cadence === "annual" ? styles.selected : ""} onClick={() => setDraft((current) => ({ ...current, revenue: { ...current.revenue, cadence: "annual" } }))}>ANUAL</button>
          <button type="button" className={draft.revenue.cadence === "monthly" ? styles.selected : ""} onClick={() => setDraft((current) => ({ ...current, revenue: { ...current.revenue, cadence: "monthly" } }))}>MENSAL</button>
        </div>
        <div className={styles.revenueLayout}>
          <div>
            <div className={styles.yearFields}>
              {draft.revenue.years.map((value, index) => <NumberField key={index} id={`revenue-${index}`} label={`Ano ${index + 1}`} value={value} min={0} onChange={(nextValue) => setDraft((current) => { const years = [...current.revenue.years] as ValuationWizardDraft["revenue"]["years"]; years[index] = nextValue ?? 0; return { ...current, revenue: { ...current.revenue, years } }; })} suffix={draft.revenue.cadence === "annual" ? "R$ por ano" : "R$ médios por mês"} />)}
            </div>
            {errors["revenue.years"] && <span className={styles.error}>{errors["revenue.years"]}</span>}
            <p className={styles.notice}>A periodicidade fica registrada no cenário. A receita anual é distribuída uniformemente pelos 12 meses; valores mensais são repetidos em cada mês do ano.</p>
          </div>
          <RevenueChart values={draft.revenue.years} cadence={draft.revenue.cadence} />
        </div>
      </>
    );

    if (step === 2) {
      const costs: [OperatingCostKey, string][] = [["administrative", "Administrativo"], ["salesMarketing", "Vendas e marketing"], ["headcount", "Pessoas / folha"], ["general", "Despesas gerais"], ["infrastructure", "Infraestrutura"], ["capex", "CAPEX"], ["other", "Outros"]];
      return <><div className={styles.grid3}>{costs.map(([key, label]) => <NumberField key={key} id={`cost-${key}`} label={label} value={draft.operatingCosts[key]} min={0} onChange={(value) => updateCost(key, value ?? 0)} suffix="R$ por ano · repetidos nos cinco anos" />)}</div>{errors.operatingCosts && <span className={styles.error}>{errors.operatingCosts}</span>}<div className={styles.simpleTranslation}><strong>OPEX anual: {money.format(totalAnnualCosts)} · CAPEX anual: {money.format(draft.operatingCosts.capex)}</strong><p>Os dois valores são tratados separadamente. Sem trajetória própria de custos, permanecem nominais constantes em todos os anos.</p></div></>;
    }

    if (step === 3) {
      const saasLike = draft.company.businessModel === "saas";
      return <><div className={styles.grid3}>{saasLike && <><NumberField id="metric-arr" label="ARR" optional value={draft.metrics.arr} min={0} onChange={(value) => updateMetric("arr", value)} suffix="Receita recorrente anual em R$" /><NumberField id="metric-mrr" label="MRR" optional value={draft.metrics.mrr} min={0} onChange={(value) => updateMetric("mrr", value)} suffix="Receita recorrente mensal em R$" /><NumberField id="metric-churn" label="Churn mensal" optional value={draft.metrics.churnMonthly} min={0} max={100} step={0.1} onChange={(value) => updateMetric("churnMonthly", value)} suffix="% por mês" /></>}<NumberField id="metric-gross-margin" label="Margem bruta usada no DCF" error={errors["metrics.grossMargin"]} value={draft.metrics.grossMargin} min={0} max={100} step={0.1} onChange={(value) => updateMetric("grossMargin", value)} suffix="% da receita" /><NumberField id="metric-cac" label="CAC" optional value={draft.metrics.cac} min={0} onChange={(value) => updateMetric("cac", value)} suffix="R$ por cliente adquirido" /><NumberField id="metric-ltv" label="LTV" optional value={draft.metrics.ltv} min={0} onChange={(value) => updateMetric("ltv", value)} suffix="R$ por cliente" /><NumberField id="metric-burn" label="Burn mensal" optional value={draft.metrics.burnMonthly} min={0} onChange={(value) => updateMetric("burnMonthly", value)} suffix="R$ consumidos por mês" /><NumberField id="metric-runway" label="Runway" optional value={draft.metrics.runwayMonths} min={0} onChange={(value) => updateMetric("runwayMonths", value)} suffix="meses" /><NumberField id="metric-cash" label="Caixa atual" value={draft.metrics.cash} min={0} onChange={(value) => updateMetric("cash", value ?? 0)} suffix="R$" /><NumberField id="metric-debt" label="Dívida financeira" value={draft.metrics.debt} min={0} onChange={(value) => updateMetric("debt", value ?? 0)} suffix="R$" /></div>{errors.metrics && <span className={styles.error}>{errors.metrics}</span>}<p className={styles.notice}>Os demais indicadores são opcionais. A margem bruta é necessária para calcular o fluxo de caixa sem assumir custos diretos ausentes.</p></>;
    }

    if (step === 4) return draft.mode === "simple" ? (
      <>
        <section className={styles.sectionBlock}><h3>Qual perfil representa melhor esta projeção?</h3><p>A escolha define premissas transparentes que você poderá revisar antes de executar.</p><div className={styles.optionGrid}>{[
          ["prudente", "Alta exigência", "Empresa ainda muito incerta", 32, 50],
          ["equilibrado", "Risco intermediário", "Premissa inicial recomendada", 25, 40],
          ["maduro", "Maior previsibilidade", "Operação mais consolidada", 18, 30],
        ].map(([id, label, description, wacc, targetReturn]) => <button type="button" key={id} className={`${styles.optionButton} ${draft.valuation.wacc === wacc ? styles.selected : ""}`} onClick={() => setDraft((current) => ({ ...current, valuation: { ...current.valuation, wacc: Number(wacc), vcTargetReturn: Number(targetReturn) } }))}><strong>{label}</strong><small>{description}</small></button>)}</div></section>
        <section className={styles.sectionBlock}><h3>Rodada e horizonte</h3><div className={styles.grid3}><NumberField id="investment" label="Investimento considerado" value={draft.valuation.investmentAmount} min={0} onChange={(value) => updateValuation("investmentAmount", value ?? 0)} suffix="R$" /><NumberField id="ownership" label="Participação desejada" value={draft.valuation.targetOwnership} min={0} max={100} step={0.1} onChange={(value) => updateValuation("targetOwnership", value ?? 0)} suffix="% após o investimento" error={errors["valuation.targetOwnership"]} /><NumberField id="horizon" label="Horizonte de saída" value={draft.valuation.investmentHorizonYears} min={1} max={15} onChange={(value) => updateValuation("investmentHorizonYears", value ?? 5)} suffix="anos" /></div></section>
        <div className={styles.simpleTranslation}><strong>Tradução das premissas: WACC {draft.valuation.wacc}% · retorno-alvo VC {draft.valuation.vcTargetReturn}% a.a.</strong><p>Crescimento terminal de {draft.valuation.terminalGrowth}% e múltiplo de saída de {draft.valuation.exitMultiple}x permanecem visíveis na revisão. Troque para o modo profissional para editá-los.</p></div>
      </>
    ) : (
      <div className={styles.grid3}><NumberField id="wacc" label="WACC" value={draft.valuation.wacc} min={0.01} max={100} step={0.1} onChange={(value) => updateValuation("wacc", value ?? 0)} suffix="% ao ano" error={errors["valuation.wacc"]} /><NumberField id="terminal-growth" label="Crescimento terminal (g)" value={draft.valuation.terminalGrowth} step={0.1} onChange={(value) => updateValuation("terminalGrowth", value ?? 0)} suffix="% ao ano · deve ser menor que WACC" error={errors["valuation.terminalGrowth"]} /><NumberField id="vc-return" label="Retorno-alvo VC" value={draft.valuation.vcTargetReturn} min={0.1} step={0.1} onChange={(value) => updateValuation("vcTargetReturn", value ?? 0)} suffix="% ao ano" error={errors["valuation.vcTargetReturn"]} /><NumberField id="exit-multiple" label="Múltiplo de saída" value={draft.valuation.exitMultiple} min={0.1} step={0.1} onChange={(value) => updateValuation("exitMultiple", value ?? 0)} suffix="x métrica de saída" error={errors["valuation.exitMultiple"]} /><NumberField id="investment" label="Investimento" value={draft.valuation.investmentAmount} min={0} onChange={(value) => updateValuation("investmentAmount", value ?? 0)} suffix="R$" /><NumberField id="ownership" label="Participação-alvo" value={draft.valuation.targetOwnership} min={0} max={100} step={0.1} onChange={(value) => updateValuation("targetOwnership", value ?? 0)} suffix="% post-money" error={errors["valuation.targetOwnership"]} /><NumberField id="horizon" label="Horizonte de saída" value={draft.valuation.investmentHorizonYears} min={1} max={15} onChange={(value) => updateValuation("investmentHorizonYears", value ?? 5)} suffix="anos" /></div>
    );

    if (step === 5) return (
      <>
        <section className={styles.sectionBlock}><h3>Quantidade e reprodutibilidade</h3><div className={styles.grid2}><div className={styles.field}><label htmlFor="simulation-count">Cenários simulados</label><select id="simulation-count" value={draft.monteCarlo.simulationCount} onChange={(event) => updateMonteCarlo("simulationCount", Number(event.target.value) as MonteCarloAssumptions["simulationCount"])}><option value={1000}>1.000</option><option value={5000}>5.000</option><option value={10000}>10.000</option><option value={25000}>25.000</option></select><small>Mais cenários aumentam a estabilidade amostral e o tempo de processamento.</small></div><div className={styles.field}><label htmlFor="seed">Random seed</label><div className={styles.seedRow}><input id="seed" type="number" min={0} step={1} value={draft.monteCarlo.randomSeed} onChange={(event) => updateMonteCarlo("randomSeed", Number(event.target.value))} aria-invalid={Boolean(errors["monteCarlo.randomSeed"])} /><button type="button" onClick={() => updateMonteCarlo("randomSeed", Math.floor(Math.random() * 2_147_483_647))}>GERAR</button></div><small>A mesma seed, inputs, versão e amostra reproduzem o resultado.</small>{errors["monteCarlo.randomSeed"] && <span className={styles.error}>{errors["monteCarlo.randomSeed"]}</span>}</div></div></section>
        <section className={styles.sectionBlock}><h3>Quão incerta é sua projeção?</h3><p>No modo simples, os níveis aplicam dispersões documentadas às variáveis. Você poderá auditar os percentuais na revisão.</p><div className={styles.optionGrid}>{(["low", "medium", "high"] as const).map((level) => <button type="button" key={level} className={`${styles.optionButton} ${draft.monteCarlo.uncertaintyLevel === level ? styles.selected : ""}`} onClick={() => selectUncertainty(level)}><strong>{level === "low" ? "Baixa" : level === "medium" ? "Média" : "Alta"}</strong><small>{UNCERTAINTY_PRESETS[level].revenueUncertainty}% de incerteza de receita</small></button>)}</div></section>
        <section className={styles.sectionBlock}><div className={styles.grid2}><NumberField id="failure" label="Probabilidade de encerramento" value={draft.monteCarlo.failureProbability} min={0} max={100} step={0.1} onChange={(value) => updateMonteCarlo("failureProbability", value ?? 0)} suffix="% dos cenários entram no estado Failure" error={errors["monteCarlo.failureProbability"]} />{draft.mode === "professional" && <NumberField id="serial-correlation" label="Persistência temporal" value={draft.monteCarlo.serialCorrelation} min={0} max={0.99} step={0.05} onChange={(value) => updateMonteCarlo("serialCorrelation", value ?? 0)} suffix="correlação serial dos choques" error={errors["monteCarlo.serialCorrelation"]} />}</div></section>
        {draft.mode === "professional" && <section className={styles.professionalBox}><p>CONTROLES PROFISSIONAIS</p><div className={styles.grid3}><div className={styles.field}><label htmlFor="distribution">Distribuição da receita</label><select id="distribution" value={draft.monteCarlo.distribution} onChange={(event) => updateMonteCarlo("distribution", event.target.value as MonteCarloAssumptions["distribution"])}><option value="lognormal">LogNormal</option><option value="student_t">Student-t</option><option value="triangular">Triangular</option><option value="uniform">Uniform</option></select></div><NumberField id="revenue-uncertainty" label="Incerteza de receita" value={draft.monteCarlo.revenueUncertainty} min={0} max={200} step={0.1} onChange={(value) => updateMonteCarlo("revenueUncertainty", value ?? 0)} suffix="%" /><NumberField id="margin-uncertainty" label="Incerteza de margem" value={draft.monteCarlo.marginUncertainty} min={0} max={100} step={0.1} onChange={(value) => updateMonteCarlo("marginUncertainty", value ?? 0)} suffix="pontos percentuais" /><NumberField id="cost-uncertainty" label="Incerteza de custos" value={draft.monteCarlo.costUncertainty} min={0} max={200} step={0.1} onChange={(value) => updateMonteCarlo("costUncertainty", value ?? 0)} suffix="%" />{draft.monteCarlo.distribution === "student_t" && <NumberField id="student-df" label="Graus de liberdade" value={draft.monteCarlo.studentDegreesFreedom} min={2.01} step={0.1} onChange={(value) => updateMonteCarlo("studentDegreesFreedom", value ?? 5)} error={errors["monteCarlo.studentDegreesFreedom"]} />}{draft.monteCarlo.distribution === "triangular" && <><NumberField id="tri-min" label="Mínimo" value={draft.monteCarlo.triangularMinimum} step={0.05} onChange={(value) => updateMonteCarlo("triangularMinimum", value ?? 0)} suffix="multiplicador" /><NumberField id="tri-mode" label="Moda" value={draft.monteCarlo.triangularMode} step={0.05} onChange={(value) => updateMonteCarlo("triangularMode", value ?? 1)} suffix="multiplicador" error={errors["monteCarlo.triangularMode"]} /><NumberField id="tri-max" label="Máximo" value={draft.monteCarlo.triangularMaximum} step={0.05} onChange={(value) => updateMonteCarlo("triangularMaximum", value ?? 1)} suffix="multiplicador" /></>}</div></section>}
      </>
    );

    const allErrors = validateAll(draft);
    return (
      <>
        {Object.keys(allErrors).length > 0 && <ul className={styles.reviewErrors}><li>Existem premissas inválidas. Use “Editar” ou execute a revisão para ir ao primeiro campo.</li></ul>}
        <div className={styles.reviewGrid}>
          <ReviewCard title="Empresa" onEdit={() => goToStep(0)}><Entry label="Empresa" value={draft.company.name || "—"} /><Entry label="Cenário" value={draft.company.scenarioName || "—"} /><Entry label="Setor / estágio" value={`${draft.company.sector || "—"} · ${draft.company.stage}`} /><Entry label="Modelo" value={draft.company.businessModel} /></ReviewCard>
          <ReviewCard title="Projeção" onEdit={() => goToStep(1)}><Entry label="Periodicidade" value={draft.revenue.cadence === "annual" ? "Anual" : "Mensal"} /><Entry label="Receita Ano 1" value={money.format(draft.revenue.years[0])} /><Entry label="Receita Ano 5" value={money.format(draft.revenue.years[4])} /><Entry label="OPEX anual (constante)" value={money.format(totalAnnualCosts)} /><Entry label="CAPEX anual (constante)" value={money.format(draft.operatingCosts.capex)} /><Entry label="Margem bruta" value={draft.metrics.grossMargin === null ? "—" : `${draft.metrics.grossMargin}%`} /></ReviewCard>
          <ReviewCard title="Valuation" onEdit={() => goToStep(4)}><Entry label="WACC" value={`${draft.valuation.wacc}% a.a.`} /><Entry label="Crescimento terminal" value={`${draft.valuation.terminalGrowth}% a.a.`} /><Entry label="Retorno-alvo VC" value={`${draft.valuation.vcTargetReturn}% a.a.`} /><Entry label="Múltiplo de saída" value={`${draft.valuation.exitMultiple}x`} /><Entry label="Investimento" value={money.format(draft.valuation.investmentAmount)} /><Entry label="Participação-alvo" value={`${draft.valuation.targetOwnership}%`} /></ReviewCard>
          <ReviewCard title="Monte Carlo" onEdit={() => goToStep(5)}><Entry label="Cenários" value={integer.format(draft.monteCarlo.simulationCount)} /><Entry label="Random seed" value={draft.monteCarlo.randomSeed} /><Entry label="Distribuição" value={draft.monteCarlo.distribution} /><Entry label="Falha" value={`${draft.monteCarlo.failureProbability}%`} /><Entry label="Incerteza receita / margem / custo" value={`${draft.monteCarlo.revenueUncertainty}% · ${draft.monteCarlo.marginUncertainty}pp · ${draft.monteCarlo.costUncertainty}%`} /><Entry label="Persistência temporal" value={draft.monteCarlo.serialCorrelation} /></ReviewCard>
          <ReviewCard title="Rastreabilidade da execução" onEdit={() => goToStep(5)} wide><Entry label="Versão esperada do modelo" value="3.1.0-dev" /><Entry label="Fluxo de persistência" value="Startup → Scenario → Revision → Simulation" /><Entry label="Fonte do resultado" value="SimulationResult persistido pelo backend" /><Entry label="Rascunho" value="Local neste dispositivo até a API persistir o cenário" /></ReviewCard>
        </div>
        {submission.kind === "success" && <div className={`${styles.submitState} ${styles.success}`} role="status"><strong>Simulação persistida pelo backend.</strong>ID {submission.simulationId} · status {submission.status}{submission.resultHash ? ` · hash ${submission.resultHash.slice(0, 12)}` : ""}. Nenhum resultado foi fabricado no frontend.<div className={styles.submitActions}><Link className="button button-secondary" href={`/app/simulations/${submission.simulationId}`}>Abrir resultado</Link></div></div>}
        {submission.kind === "error" && <div className={`${styles.submitState} ${styles.errorState}`} role="alert"><strong>A execução não foi iniciada.</strong>{submission.message}</div>}
      </>
    );
  }

  return (
    <main id="main-content" className={styles.wizardPage}>
      <header className={styles.wizardHeader}>
        <div><p>{context === "company" ? "NOVA EMPRESA / PRIMEIRO CENÁRIO" : "NOVO CENÁRIO"}</p><h1>Construa uma análise auditável.</h1><span>Sete etapas, rascunho local e premissas visíveis antes de qualquer cálculo.</span></div>
        <div><div className={styles.modeSwitch} aria-label="Nível de configuração"><button type="button" className={draft.mode === "simple" ? styles.active : ""} onClick={() => changeMode("simple")}>SIMPLE MODE</button><button type="button" className={draft.mode === "professional" ? styles.active : ""} onClick={() => changeMode("professional")}>PROFESSIONAL</button></div><span className={styles.saveState} role="status">{saveState}</span></div>
      </header>
      <div className={styles.layout}>
        <aside className={styles.stepper} aria-label="Etapas da análise"><div className={styles.progress}><i style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} /></div><ol>{STEPS.map(([title, description], index) => { const position = index as WizardStep; const className = position === step ? styles.current : position < step ? styles.complete : ""; return <li key={title}><button type="button" className={className} onClick={() => goToStep(position)} disabled={position > maxVisited}><span className={styles.stepNumber}>{position < step ? "✓" : index + 1}</span><span><strong>{title}</strong><small>{description}</small></span></button></li>; })}</ol></aside>
        <section className={styles.panel}>
          <header className={styles.panelHead}><p className={styles.stepEyebrow}>ETAPA {step + 1} DE 7 · {draft.mode === "simple" ? "SIMPLE MODE" : "PROFESSIONAL MODE"}</p><h2>{STEPS[step][0]}</h2><p>{STEP_DESCRIPTIONS[step]}</p></header>
          <div className={styles.panelBody}>{panel}</div>
          <footer className={styles.actions}><div className={styles.draftTools}><button type="button" onClick={resetDraft}>Descartar rascunho</button></div><div>{step > 0 && <button type="button" className="button button-secondary" onClick={() => { setStep((step - 1) as WizardStep); setErrors({}); }}>Voltar</button>}{step < 6 ? <button type="button" className="button button-primary" onClick={nextStep}>Continuar</button> : <button type="button" className="button button-primary" onClick={submit} disabled={submission.kind === "loading"}>{submission.kind === "loading" ? "Enviando…" : `Rodar ${integer.format(draft.monteCarlo.simulationCount)} cenários`}</button>}</div></footer>
        </section>
      </div>
    </main>
  );
}
