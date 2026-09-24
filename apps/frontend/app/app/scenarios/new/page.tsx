import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { ValuationWizard } from "@/components/wizard/valuation-wizard";

export const metadata: Metadata = { title: "Novo cenário" };

export default function NewScenarioPage() {
  return (
    <AppShell active="/app/simulations/demo">
      <ValuationWizard context="scenario" />
    </AppShell>
  );
}
