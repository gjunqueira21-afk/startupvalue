import type { ValidationErrors, ValuationWizardDraft, WizardStep } from "./types";

const required = (value: string) => value.trim().length > 0;
const percentage = (value: number) => Number.isFinite(value) && value >= 0 && value <= 100;

export function validateStep(draft: ValuationWizardDraft, step: WizardStep): ValidationErrors {
  const errors: ValidationErrors = {};

  if (step === 0) {
    if (!required(draft.company.name)) errors["company.name"] = "Informe o nome da empresa.";
    if (!required(draft.company.sector)) errors["company.sector"] = "Informe o setor.";
    if (!required(draft.company.scenarioName)) errors["company.scenarioName"] = "Nomeie o cenário.";
    const currentYear = new Date().getFullYear();
    if (draft.company.foundingYear < 1900 || draft.company.foundingYear > currentYear) {
      errors["company.foundingYear"] = `Use um ano entre 1900 e ${currentYear}.`;
    }
  }

  if (step === 1) {
    if (draft.revenue.years.some((value) => !Number.isFinite(value) || value < 0)) {
      errors["revenue.years"] = "A receita não pode ser negativa.";
    }
    if (draft.revenue.years.every((value) => value === 0)) {
      errors["revenue.years"] = "Informe receita em pelo menos um ano.";
    }
  }

  if (step === 2 && Object.values(draft.operatingCosts).some((value) => !Number.isFinite(value) || value < 0)) {
    errors.operatingCosts = "Custos e CAPEX devem ser zero ou positivos.";
  }

  if (step === 3) {
    if (draft.metrics.grossMargin === null || !percentage(draft.metrics.grossMargin)) {
      errors["metrics.grossMargin"] = "Informe a margem bruta usada no modelo (0% a 100%).";
    }
    const nullablePercentages = [draft.metrics.churnMonthly];
    if (nullablePercentages.some((value) => value !== null && !percentage(value))) {
      errors.metrics = "Margem e churn devem ficar entre 0% e 100%.";
    }
    const nullablePositive = [
      draft.metrics.arr,
      draft.metrics.mrr,
      draft.metrics.cac,
      draft.metrics.ltv,
      draft.metrics.burnMonthly,
      draft.metrics.runwayMonths,
    ];
    if (nullablePositive.some((value) => value !== null && value < 0)) {
      errors.metrics = "Métricas opcionais não podem ser negativas.";
    }
  }

  if (step === 4) {
    if (draft.valuation.wacc <= 0 || draft.valuation.wacc > 100) errors["valuation.wacc"] = "Use WACC entre 0% e 100%.";
    if (draft.valuation.terminalGrowth >= draft.valuation.wacc) {
      errors["valuation.terminalGrowth"] = "O crescimento terminal deve ser menor que o WACC.";
    }
    if (draft.valuation.exitMultiple <= 0) errors["valuation.exitMultiple"] = "O múltiplo deve ser maior que zero.";
    if (draft.valuation.vcTargetReturn <= 0) errors["valuation.vcTargetReturn"] = "O retorno-alvo deve ser maior que zero.";
    if (!percentage(draft.valuation.targetOwnership)) errors["valuation.targetOwnership"] = "A participação deve ficar entre 0% e 100%.";
  }

  if (step === 5) {
    if (!Number.isInteger(draft.monteCarlo.randomSeed) || draft.monteCarlo.randomSeed < 0) {
      errors["monteCarlo.randomSeed"] = "A seed deve ser um inteiro positivo.";
    }
    if (!percentage(draft.monteCarlo.failureProbability)) {
      errors["monteCarlo.failureProbability"] = "A probabilidade deve ficar entre 0% e 100%.";
    }
    if (draft.monteCarlo.serialCorrelation < 0 || draft.monteCarlo.serialCorrelation >= 1) {
      errors["monteCarlo.serialCorrelation"] = "Use correlação entre 0 e menor que 1.";
    }
    if (draft.monteCarlo.distribution === "student_t" && draft.monteCarlo.studentDegreesFreedom <= 2) {
      errors["monteCarlo.studentDegreesFreedom"] = "Use mais de 2 graus de liberdade para variância finita.";
    }
    if (
      draft.monteCarlo.distribution === "triangular" &&
      !(
        draft.monteCarlo.triangularMinimum <= draft.monteCarlo.triangularMode &&
        draft.monteCarlo.triangularMode <= draft.monteCarlo.triangularMaximum
      )
    ) {
      errors["monteCarlo.triangularMode"] = "A moda deve ficar entre o mínimo e o máximo.";
    }
  }

  return errors;
}

export function validateAll(draft: ValuationWizardDraft): ValidationErrors {
  return ([0, 1, 2, 3, 4, 5] as WizardStep[]).reduce(
    (all, step) => ({ ...all, ...validateStep(draft, step) }),
    {},
  );
}
