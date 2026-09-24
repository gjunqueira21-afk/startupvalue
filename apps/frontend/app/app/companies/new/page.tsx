import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { ValuationWizard } from "@/components/wizard/valuation-wizard";

export const metadata: Metadata = { title: "Nova análise" };

export default function NewCompanyPage() {
  return (
    <AppShell active="/app#empresas">
      <ValuationWizard context="company" />
    </AppShell>
  );
}
